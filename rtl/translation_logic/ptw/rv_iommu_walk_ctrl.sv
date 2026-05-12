// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (PR-cdw-split v4: PROC state, pt_walker separated)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: Walk Controller (= PTW orchestrator), v4
//
//   v4 changes:
//     - ST_PROC state を追加 (= PTE 解釈と次動作決定をここに集約)
//     - pt_walker.sv を sub-module として使う (= 自前 AXI master 廃止)
//     - sv39 / sv39x4 限定
//     - iosatp_ppn_i は SPA 前提 (= 初期 S2 walk 廃止)
//
//   Walk orchestration:
//     - 各 PTE read は pt_walker への req/rsp ハンドシェイク 1 回
//     - walk_ctrl は req_addr_o を計算、 rsp_data_i を解釈して次の addr を決める

module rv_iommu_walk_ctrl
    import rv_iommu::*;
(
    input  logic                                clk_i,
    input  logic                                rst_ni,

    // ── Triggers ────────────────────────────────────────────────────
    input  logic                                init_i,                 // 通常 translation
    input  logic                                cdw_implicit_access_i,  // DDTW/PDTW から
    input  logic                                flush_i,

    // ── Translation request inputs ──────────────────────────────────
    input  logic [riscv::VLEN-1:0]              iova_i,
    input  logic                                is_store_i,
    input  logic                                is_rx_i,
    input  logic                                priv_lvl_i,
    input  logic                                sum_i,
    input  logic                                en_stage1_i,
    input  logic                                en_stage2_i,

    // ── PT root pointers (= 常に SPA) ───────────────────────────────
    input  logic [riscv::PPNW-1:0]              iosatp_ppn_i,
    input  logic [3:0]                          iosatp_mode_i,
    input  logic [riscv::PPNW-1:0]              iohgatp_ppn_i,
    input  logic [3:0]                          iohgatp_mode_i,

    // ── Implicit S2 GPPN (= DDTW/PDTW からの翻訳依頼 input) ─────────
    input  logic [riscv::GPPNW-1:0]             cdw_pdt_gppn_i,

    // ── To pt_walker ────────────────────────────────────────────────
    output logic                                walker_req_valid_o,
    input  logic                                walker_req_ready_i,
    output logic [riscv::PLEN-1:0]              walker_req_addr_o,
    input  logic                                walker_rsp_valid_i,
    output logic                                walker_rsp_ready_o,
    input  logic [63:0]                         walker_rsp_data_i,
    input  logic                                walker_rsp_error_i,

    // ── IOTLB update ────────────────────────────────────────────────
    output logic                                update_iotlb_o,
    output logic [riscv::GPPNW-1:0]             update_vpn_o,
    output riscv::pte_t                         update_1S_content_o,
    output riscv::pte_t                         update_2S_content_o,
    output logic                                update_1S_2M_o, update_1S_1G_o,
    output logic                                update_2S_2M_o, update_2S_1G_o,
    output logic                                update_is_msi_o,

    // ── To DDTW/PDTW (= S2 翻訳結果) ───────────────────────────────
    output logic                                ptw_done_o,
    output logic [riscv::PPNW-1:0]              pdt_ppn_o,

    // ── Error / status ──────────────────────────────────────────────
    output logic                                ptw_error_o,
    output logic                                ptw_error_2S_o,
    output logic [rv_iommu::CAUSE_LEN-1:0]      cause_code_o,
    output logic [riscv::SVX-1:0]               bad_gpaddr_o,
    output logic                                active_o
);

    // ── States ──────────────────────────────────────────────────────
    typedef enum logic [2:0] {
        ST_IDLE,
        ST_ISSUE,
        ST_WAIT,
        ST_PROC,
        ST_ERROR
    } state_t;
    state_t state_q, state_n;

    // ── Phases ──────────────────────────────────────────────────────
    typedef enum logic [1:0] {
        PH_S1,
        PH_S2
    } phase_t;
    phase_t phase_q, phase_n;

    // ── Walk mode ───────────────────────────────────────────────────
    typedef enum logic [1:0] {
        WM_SINGLE_S1,
        WM_SINGLE_S2,
        WM_NESTED,
        WM_IMPLICIT_S2     // DDTW/PDTW からの GPA→SPA 依頼
    } walk_mode_t;
    walk_mode_t walk_mode_q, walk_mode_n;

    // ── Level ───────────────────────────────────────────────────────
    logic [1:0]                                 s1_lvl_q, s1_lvl_n;
    logic [1:0]                                 s2_lvl_q, s2_lvl_n;

    // ── PT pointers ─────────────────────────────────────────────────
    logic [riscv::PLEN-1:0]                     s1_pptr_q, s1_pptr_n;
    logic [riscv::PLEN-1:0]                     s2_pptr_q, s2_pptr_n;

    // ── Captured PTEs (= PROC で参照) ───────────────────────────────
    riscv::pte_t                             pte_pending_q, pte_pending_n;
    riscv::pte_t                             s1_leaf_q,     s1_leaf_n;
    riscv::pte_t                             s2_leaf_q,     s2_leaf_n;

    // ── Snapshot at init ────────────────────────────────────────────
    logic [riscv::VLEN-1:0]                     iova_q;
    logic                                       is_store_q, is_rx_q, priv_lvl_q, sum_q;
    logic                                       en_s1_q, en_s2_q;
    logic [riscv::GPPNW-1:0]                    impl_gppn_q;

    // ── Cause / error ───────────────────────────────────────────────
    logic [rv_iommu::CAUSE_LEN-1:0]             cause_q, cause_n;
    logic                                       is_2S_q, is_2S_n;
    logic [riscv::SVX-1:0]                      bad_gpaddr_q, bad_gpaddr_n;

    // ── Edge-triggered init ─────────────────────────────────────────
    logic edge_trigger_q, edge_trigger_n;
    logic any_init_w;
    assign any_init_w = init_i || cdw_implicit_access_i;
    always_comb begin : init_edge
        edge_trigger_n = edge_trigger_q;
        if (!edge_trigger_q &&  any_init_w) edge_trigger_n = 1'b1;
        if ( edge_trigger_q && !any_init_w) edge_trigger_n = 1'b0;
    end
    wire init_rising_edge = any_init_w && !edge_trigger_q;

    // ── VPN segment extractors (sv39 / sv39x4) ───────────────────────
    function automatic logic [8:0] vpn_seg_s1(input logic [riscv::VLEN-1:0] va, input logic [1:0] lvl);
        case (lvl)
            2'd2: return va[38:30];
            2'd1: return va[29:21];
            2'd0: return va[20:12];
            default: return '0;
        endcase
    endfunction

    function automatic logic [10:0] vpn_seg_s2(input logic [riscv::GPPNW-1:0] gppn, input logic [1:0] lvl);
        case (lvl)
            2'd2: return gppn[28:18];      // top: 11 bits in sv39x4
            2'd1: return {2'b0, gppn[17:9]};
            2'd0: return {2'b0, gppn[8:0]};
            default: return '0;
        endcase
    endfunction

    // ── Status outputs ──────────────────────────────────────────────
    assign active_o = (state_q != ST_IDLE);

    // ── Helper: AXI request to walker ───────────────────────────────
    // walker_req_addr_o は phase に応じて s1 or s2 pptr
    assign walker_req_addr_o  = (phase_q == PH_S1) ? s1_pptr_q : s2_pptr_q;
    assign walker_req_valid_o = (state_q == ST_ISSUE);
    assign walker_rsp_ready_o = (state_q == ST_WAIT);

    // ── pte_view (rsp_data から typed) ──────────────────────────────
    riscv::pte_t pte_view;
    assign pte_view = riscv::pte_t'(walker_rsp_data_i);

    // ──────────────────────────────────────────────────────────────────
    // Main FSM
    // ──────────────────────────────────────────────────────────────────
    always_comb begin : walk_ctrl_fsm

        state_n       = state_q;
        phase_n       = phase_q;
        walk_mode_n   = walk_mode_q;
        s1_lvl_n      = s1_lvl_q;
        s2_lvl_n      = s2_lvl_q;
        s1_pptr_n     = s1_pptr_q;
        s2_pptr_n     = s2_pptr_q;
        pte_pending_n = pte_pending_q;
        s1_leaf_n     = s1_leaf_q;
        s2_leaf_n     = s2_leaf_q;
        cause_n       = cause_q;
        is_2S_n       = is_2S_q;
        bad_gpaddr_n  = bad_gpaddr_q;

        ptw_done_o          = 1'b0;
        pdt_ppn_o           = '0;
        ptw_error_o         = 1'b0;
        ptw_error_2S_o      = 1'b0;
        cause_code_o        = '0;
        bad_gpaddr_o        = '0;
        update_iotlb_o      = 1'b0;
        update_is_msi_o     = 1'b0;
        update_vpn_o        = '0;
        update_1S_content_o = '0;
        update_2S_content_o = '0;
        update_1S_2M_o      = 1'b0;
        update_1S_1G_o      = 1'b0;
        update_2S_2M_o      = 1'b0;
        update_2S_1G_o      = 1'b0;

        case (state_q)

            // ─────────────────────────────────────────────────────────
            ST_IDLE: begin
                cause_n      = '0;
                is_2S_n      = 1'b0;
                bad_gpaddr_n = '0;

                if (init_rising_edge) begin
                    if (cdw_implicit_access_i) begin
                        walk_mode_n = WM_IMPLICIT_S2;
                        s2_lvl_n    = 2'd2;
                        s2_pptr_n   = {iohgatp_ppn_i, vpn_seg_s2(cdw_pdt_gppn_i, 2'd2), 3'b0};
                        phase_n     = PH_S2;
                    end
                    else if (en_stage1_i && en_stage2_i) begin
                        walk_mode_n = WM_NESTED;
                        s1_lvl_n    = 2'd2;
                        s1_pptr_n   = {iosatp_ppn_i, vpn_seg_s1(iova_i, 2'd2), 3'b0};
                        phase_n     = PH_S1;
                    end
                    else if (en_stage1_i) begin
                        walk_mode_n = WM_SINGLE_S1;
                        s1_lvl_n    = 2'd2;
                        s1_pptr_n   = {iosatp_ppn_i, vpn_seg_s1(iova_i, 2'd2), 3'b0};
                        phase_n     = PH_S1;
                    end
                    else if (en_stage2_i) begin
                        walk_mode_n = WM_SINGLE_S2;
                        s2_lvl_n    = 2'd2;
                        s2_pptr_n   = {iohgatp_ppn_i,
                                       vpn_seg_s2(iova_i[riscv::SVX-1:12], 2'd2), 3'b0};
                        phase_n     = PH_S2;
                    end
                    state_n = ST_ISSUE;
                end
            end

            // ─────────────────────────────────────────────────────────
            // ST_ISSUE: pt_walker に req を投げる
            // ─────────────────────────────────────────────────────────
            ST_ISSUE: begin
                if (walker_req_ready_i) begin
                    state_n = ST_WAIT;
                end
            end

            // ─────────────────────────────────────────────────────────
            // ST_WAIT: pt_walker から rsp 受信 → 捕捉して PROC へ
            // ─────────────────────────────────────────────────────────
            ST_WAIT: begin
                if (walker_rsp_valid_i) begin
                    if (walker_rsp_error_i) begin
                        cause_n = rv_iommu::PT_DATA_CORRUPTION;
                        state_n = ST_ERROR;
                    end
                    else begin
                        pte_pending_n = pte_view;
                        state_n       = ST_PROC;
                    end
                end
                if (flush_i) state_n = ST_IDLE;
            end

            // ─────────────────────────────────────────────────────────
            // ST_PROC: PTE 検査 + 次動作決定
            // ─────────────────────────────────────────────────────────
            ST_PROC: begin
                case (phase_q)

                    PH_S1: begin
                        if (!pte_pending_q.v || (!pte_pending_q.r && pte_pending_q.w)) begin
                            cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT : rv_iommu::LOAD_PAGE_FAULT;
                            state_n = ST_ERROR;
                        end
                        else if (pte_pending_q.r || pte_pending_q.x) begin
                            // ── Leaf S1 PTE ──
                            s1_leaf_n = pte_pending_q;
                            if (walk_mode_q == WM_NESTED) begin
                                // S2 walk on leaf PPN
                                s2_lvl_n  = 2'd2;
                                s2_pptr_n = {iohgatp_ppn_i,
                                             vpn_seg_s2(pte_pending_q.ppn[riscv::GPPNW-1:0], 2'd2), 3'b0};
                                phase_n   = PH_S2;
                                state_n   = ST_ISSUE;
                            end
                            else begin
                                // single S1: commit
                                update_iotlb_o      = 1'b1;
                                update_vpn_o        = iova_q[riscv::SVX-1:12];
                                update_1S_content_o = pte_pending_q;
                                state_n             = ST_IDLE;
                            end
                        end
                        else begin
                            // ── Non-leaf S1 PTE ──
                            if (walk_mode_q == WM_NESTED) begin
                                // 非 leaf NL PPN も GPA → S2 翻訳
                                s2_lvl_n  = 2'd2;
                                s2_pptr_n = {iohgatp_ppn_i,
                                             vpn_seg_s2(pte_pending_q.ppn[riscv::GPPNW-1:0], 2'd2), 3'b0};
                                phase_n   = PH_S2;
                                state_n   = ST_ISSUE;
                            end
                            else if (s1_lvl_q > 0) begin
                                s1_lvl_n  = s1_lvl_q - 1;
                                s1_pptr_n = {pte_pending_q.ppn,
                                             vpn_seg_s1(iova_q, s1_lvl_q - 1), 3'b0};
                                state_n   = ST_ISSUE;
                            end
                            else begin
                                cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT : rv_iommu::LOAD_PAGE_FAULT;
                                state_n = ST_ERROR;
                            end
                        end
                    end

                    PH_S2: begin
                        if (!pte_pending_q.v || (!pte_pending_q.r && pte_pending_q.w)) begin
                            cause_n = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                            is_2S_n = 1'b1;
                            state_n = ST_ERROR;
                        end
                        else if (pte_pending_q.r || pte_pending_q.x) begin
                            // ── Leaf S2 PTE ── (= SPA を得た)
                            s2_leaf_n = pte_pending_q;
                            case (walk_mode_q)
                                WM_IMPLICIT_S2: begin
                                    // DDTW/PDTW に翻訳結果を返す
                                    ptw_done_o = 1'b1;
                                    pdt_ppn_o  = pte_pending_q.ppn;
                                    update_2S_content_o = pte_pending_q;  // DDTW/PDTW が IOTLB update に使うため
                                    state_n    = ST_IDLE;
                                end
                                WM_NESTED: begin
                                    if (s1_leaf_q.r || s1_leaf_q.x) begin
                                        // S1 も leaf だった: 最終 SPA 取得 → commit
                                        update_iotlb_o      = 1'b1;
                                        update_vpn_o        = iova_q[riscv::SVX-1:12];
                                        update_1S_content_o = s1_leaf_q;
                                        update_2S_content_o = pte_pending_q;
                                        state_n             = ST_IDLE;
                                    end
                                    else if (s1_lvl_q > 0) begin
                                        // S1 中間 NL の SPA → 次 S1 level へ
                                        s1_lvl_n  = s1_lvl_q - 1;
                                        s1_pptr_n = {pte_pending_q.ppn,
                                                     vpn_seg_s1(iova_q, s1_lvl_q - 1), 3'b0};
                                        phase_n   = PH_S1;
                                        state_n   = ST_ISSUE;
                                    end
                                    else begin
                                        cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT : rv_iommu::LOAD_PAGE_FAULT;
                                        state_n = ST_ERROR;
                                    end
                                end
                                WM_SINGLE_S2: begin
                                    update_iotlb_o      = 1'b1;
                                    update_vpn_o        = iova_q[riscv::SVX-1:12];
                                    update_2S_content_o = pte_pending_q;
                                    state_n             = ST_IDLE;
                                end
                                default: state_n = ST_IDLE;
                            endcase
                        end
                        else begin
                            // ── Non-leaf S2 PTE ──
                            if (s2_lvl_q > 0) begin
                                s2_lvl_n = s2_lvl_q - 1;
                                case (walk_mode_q)
                                    WM_IMPLICIT_S2:
                                        s2_pptr_n = {pte_pending_q.ppn,
                                                     vpn_seg_s2(impl_gppn_q, s2_lvl_q - 1), 3'b0};
                                    WM_NESTED:
                                        s2_pptr_n = {pte_pending_q.ppn,
                                                     vpn_seg_s2(pte_pending_q.ppn[riscv::GPPNW-1:0],
                                                                s2_lvl_q - 1), 3'b0};
                                    WM_SINGLE_S2:
                                        s2_pptr_n = {pte_pending_q.ppn,
                                                     vpn_seg_s2(iova_q[riscv::SVX-1:12],
                                                                s2_lvl_q - 1), 3'b0};
                                    default: ;
                                endcase
                                state_n = ST_ISSUE;
                            end
                            else begin
                                cause_n = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                                is_2S_n = 1'b1;
                                state_n = ST_ERROR;
                            end
                        end
                    end

                    default: state_n = ST_IDLE;
                endcase
            end

            // ─────────────────────────────────────────────────────────
            // ST_ERROR: PTE error pulse → IDLE
            //   walker からの drain は不要 (= walker は 1 PTE 単位)
            // ─────────────────────────────────────────────────────────
            ST_ERROR: begin
                ptw_error_o    = 1'b1;
                ptw_error_2S_o = is_2S_q;
                cause_code_o   = cause_q;
                bad_gpaddr_o   = bad_gpaddr_q;
                state_n        = ST_IDLE;
            end

            default: state_n = ST_IDLE;
        endcase
    end

    // ── Snapshot inputs at init edge ─────────────────────────────────
    logic snapshot_en;
    assign snapshot_en = (state_q == ST_IDLE) && init_rising_edge;

    // ── Sequential ───────────────────────────────────────────────────
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            state_q        <= ST_IDLE;
            phase_q        <= PH_S1;
            walk_mode_q    <= WM_SINGLE_S1;
            s1_lvl_q       <= '0;
            s2_lvl_q       <= '0;
            s1_pptr_q      <= '0;
            s2_pptr_q      <= '0;
            pte_pending_q  <= '0;
            s1_leaf_q      <= '0;
            s2_leaf_q      <= '0;
            iova_q         <= '0;
            is_store_q     <= 1'b0;
            is_rx_q        <= 1'b0;
            priv_lvl_q     <= 1'b0;
            sum_q          <= 1'b0;
            en_s1_q        <= 1'b0;
            en_s2_q        <= 1'b0;
            impl_gppn_q    <= '0;
            cause_q        <= '0;
            is_2S_q        <= 1'b0;
            bad_gpaddr_q   <= '0;
            edge_trigger_q <= 1'b0;
        end else begin
            state_q        <= state_n;
            phase_q        <= phase_n;
            walk_mode_q    <= walk_mode_n;
            s1_lvl_q       <= s1_lvl_n;
            s2_lvl_q       <= s2_lvl_n;
            s1_pptr_q      <= s1_pptr_n;
            s2_pptr_q      <= s2_pptr_n;
            pte_pending_q  <= pte_pending_n;
            s1_leaf_q      <= s1_leaf_n;
            s2_leaf_q      <= s2_leaf_n;
            cause_q        <= cause_n;
            is_2S_q        <= is_2S_n;
            bad_gpaddr_q   <= bad_gpaddr_n;
            edge_trigger_q <= edge_trigger_n;
            if (snapshot_en) begin
                iova_q      <= iova_i;
                is_store_q  <= is_store_i;
                is_rx_q     <= is_rx_i;
                priv_lvl_q  <= priv_lvl_i;
                sum_q       <= sum_i;
                en_s1_q     <= en_stage1_i;
                en_s2_q     <= en_stage2_i;
                impl_gppn_q <= cdw_pdt_gppn_i;
            end
        end
    end

endmodule