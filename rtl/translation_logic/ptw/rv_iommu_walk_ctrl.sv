// Copyright © 2026 (PR-walker v3: state を 5 個に集約 + phase レジスタで分類)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Design philosophy:
//   - state は「今 cycle 何をやっているか」だけを表す:
//       IDLE   : 入力待ち
//       ISSUE  : walker に request を渡している cycle
//       WAIT   : walker からの response を待っている cycle
//       PROC   : 受信した PTE を解釈する cycle
//       ERROR  : エラー出力 1 cycle
//   - phase は「翻訳プロセスのどのフェーズにいるか」を表す:
//       PH_SINGLE       : 単段翻訳 (S1-only / S2-only / CDW implicit)
//       PH_NEST_S2_INT  : nested の中間 S2 walk
//       PH_NEST_S1_RD   : nested の S1 PTE 単発読み
//       PH_NEST_S2_FIN  : nested の最終 S2 walk
//   - 5 × 4 で見ると 20 ケースだが、 各 case の動作は orthogonal で読みやすい
//   - MSI check は PROC の PH_NEST_S1_RD leaf-OK 分岐に inline
//   - S1 leaf perm check と最終 perm check は PROC で集約

module rv_iommu_walk_ctrl
    import rv_iommu::*;
#(
    parameter rv_iommu::msi_trans_t MSITrans    = rv_iommu::MSI_DISABLED,
    parameter type axi_req_t = logic,
    parameter type axi_rsp_t = logic
) (
    input  logic                                clk_i,
    input  logic                                rst_ni,

    input  logic                                init_i,
    output logic                                active_o,
    output logic                                error_o,
    output logic                                error_2S_o,
    output logic                                error_2S_int_o,
    output logic [rv_iommu::CAUSE_LEN-1:0]      cause_o,

    input  logic                                en_1S_i,
    input  logic                                en_2S_i,
    input  logic                                is_store_i,
    input  logic                                is_rx_i,
    input  logic                                priv_lvl_i,
    input  logic                                sum_i,
    input  logic [riscv::VLEN-1:0]              req_iova_i,
    input  logic [19:0]                         pscid_i,
    input  logic [15:0]                         gscid_i,
    input  logic [riscv::PPNW-1:0]              iosatp_ppn_i,
    input  logic [riscv::PPNW-1:0]              iohgatp_ppn_i,

    output logic                                update_o,
    output logic                                up_1S_2M_o,
    output logic                                up_1S_1G_o,
    output logic                                up_2S_2M_o,
    output logic                                up_2S_1G_o,
    output logic [riscv::GPPNW-1:0]             up_vpn_o,
    output logic [19:0]                         up_pscid_o,
    output logic [15:0]                         up_gscid_o,
    output riscv::pte_t                         up_1S_content_o,
    output riscv::pte_t                         up_2S_content_o,

    input  logic                                msi_en_i,
    input  logic [riscv::GPPNW-1:0]             msi_addr_mask_i,
    input  logic [riscv::GPPNW-1:0]             msi_addr_pattern_i,
    output logic                                gpaddr_is_msi_o,
    output logic [riscv::GPPNW-1:0]             msi_vpn_o,
    output logic                                msi_1S_2M_o,
    output logic                                msi_1S_1G_o,
    output riscv::pte_t                         msi_gpte_o,

    input  logic                                cdw_implicit_access_i,
    input  logic [riscv::GPPNW-1:0]             pdt_gppn_i,
    output logic                                cdw_done_o,
    output logic                                flush_cdw_o,

    output logic [riscv::GPLEN-1:0]             bad_gpaddr_o,

    output logic                                walker_req_valid_o,
    input  logic                                walker_req_ready_i,
    output logic                                walker_req_op_o,
    output logic                                walker_req_is_sv39x4_o,
    output logic [riscv::PPNW-1:0]              walker_req_root_ppn_o,
    output logic [riscv::VLEN-1:0]              walker_req_va_o,
    output logic [riscv::PLEN-1:0]              walker_req_pptr_o,

    input  logic                                walker_rsp_valid_i,
    input  riscv::pte_t                         walker_rsp_pte_i,
    input  logic [1:0]                          walker_rsp_lvl_i,
    input  logic                                walker_rsp_error_i,
    input  logic [rv_iommu::CAUSE_LEN-1:0]      walker_rsp_cause_i
);

    // ── State (5 states) ─────────────────────────────────────────────
    typedef enum logic [2:0] {
        ST_IDLE,
        ST_ISSUE,    // walker に request を発行中
        ST_WAIT,     // walker の response を待ち中
        ST_PROC,     // 受信した PTE を解釈中
        ST_ERROR
    } state_t;
    state_t state_q, state_n;

    // ── Phase (4 phases) ─────────────────────────────────────────────
    typedef enum logic [1:0] {
        PH_SINGLE,         // 単段 (S1-only / S2-only / CDW implicit)
        PH_NEST_S2_INT,    // nested 中間 S2 walk
        PH_NEST_S1_RD,     // nested の S1 PTE 単発 read
        PH_NEST_S2_FIN     // nested 最終 S2 walk
    } phase_t;
    phase_t phase_q, phase_n;

    // ── Mode ─────────────────────────────────────────────────────────
    typedef enum logic [1:0] {
        MODE_S1_ONLY,
        MODE_S2_ONLY,
        MODE_NESTED,
        MODE_CDW_IMPL
    } mode_t;
    mode_t mode_q, mode_n;

    // ── Nested S1 walk level ─────────────────────────────────────────
    logic [1:0]                     s1_lvl_q,     s1_lvl_n;

    // ── Latched translation context ──────────────────────────────────
    logic [riscv::VLEN-1:0]         iova_q,       iova_n;
    logic [19:0]                    pscid_q,      pscid_n;
    logic [15:0]                    gscid_q,      gscid_n;
    logic                           is_store_q,   is_store_n;
    logic                           is_rx_q,      is_rx_n;
    logic                           priv_q,       priv_n;
    logic                           sum_q,        sum_n;
    logic [riscv::PPNW-1:0]         iosatp_q,     iosatp_n;
    logic [riscv::PPNW-1:0]         iohgatp_q,    iohgatp_n;
    logic                           en_1S_q,      en_1S_n;
    logic                           en_2S_q,      en_2S_n;
    logic [riscv::GPPNW-1:0]        msi_mask_q,   msi_mask_n;
    logic [riscv::GPPNW-1:0]        msi_patt_q,   msi_patt_n;
    logic                           msi_en_q,     msi_en_n;
    logic                           cdw_implicit_q, cdw_implicit_n;
    logic [riscv::GPPNW-1:0]        pdt_gppn_q,   pdt_gppn_n;

    // ── Per-step intermediate state ──────────────────────────────────
    logic [riscv::GPLEN-1:0]        s1_pt_gpa_q,  s1_pt_gpa_n;
    logic [riscv::PLEN-1:0]         s1_pt_spa_q,  s1_pt_spa_n;
    logic [riscv::GPLEN-1:0]        final_gpa_q,  final_gpa_n;

    // ── Captured walker response (latched in ST_WAIT) ────────────────
    riscv::pte_t                    rsp_pte_q,    rsp_pte_n;
    logic [1:0]                     rsp_lvl_q,    rsp_lvl_n;
    logic                           rsp_error_q,  rsp_error_n;
    logic [rv_iommu::CAUSE_LEN-1:0] rsp_cause_q,  rsp_cause_n;

    // ── Accumulated final results ────────────────────────────────────
    riscv::pte_t                    s1_leaf_q,    s1_leaf_n;
    logic [1:0]                     s1_leaf_lvl_q, s1_leaf_lvl_n;
    riscv::pte_t                    s2_leaf_q,    s2_leaf_n;
    logic [1:0]                     s2_leaf_lvl_q, s2_leaf_lvl_n;

    // ── Error tracking ───────────────────────────────────────────────
    logic                           error_in_s2_q,     error_in_s2_n;
    logic                           error_in_s2_int_q, error_in_s2_int_n;
    logic [rv_iommu::CAUSE_LEN-1:0] cause_q,           cause_n;
    logic [riscv::GPLEN-1:0]        bad_gpaddr_q,      bad_gpaddr_n;
    logic                           s1_leaf_is_msi_q,  s1_leaf_is_msi_n;

    // ── Public outputs ───────────────────────────────────────────────
    assign active_o       = (state_q != ST_IDLE);
    assign error_o        = (state_q == ST_ERROR);
    assign error_2S_o     = error_in_s2_q;
    assign error_2S_int_o = error_in_s2_int_q;
    assign cause_o        = cause_q;
    assign bad_gpaddr_o   = bad_gpaddr_q;

    // ── Helper functions (= v2 と同じ) ───────────────────────────────
    function automatic logic [riscv::GPLEN-1:0] init_s1_pt_gpa(
        logic [riscv::PPNW-1:0]   iosatp,
        logic [riscv::VLEN-1:0]   iova
    );
        init_s1_pt_gpa = {iosatp[riscv::GPPNW-1:0], iova[riscv::SV-1:30], 3'b0};
    endfunction

    function automatic logic [riscv::GPLEN-1:0] next_s1_pt_gpa(
        riscv::pte_t              prev_pte,
        logic [riscv::VLEN-1:0]   iova,
        logic [1:0]               new_level
    );
        case (new_level)
            2'd1:    next_s1_pt_gpa = {prev_pte.ppn[riscv::GPPNW-1:0], iova[29:21], 3'b0};
            2'd0:    next_s1_pt_gpa = {prev_pte.ppn[riscv::GPPNW-1:0], iova[20:12], 3'b0};
            default: next_s1_pt_gpa = '0;
        endcase
    endfunction

    function automatic logic [riscv::GPLEN-1:0] compute_final_gpa(
        riscv::pte_t              pte,
        logic [riscv::VLEN-1:0]   iova,
        logic [1:0]               leaf_lvl
    );
        case (leaf_lvl)
            2'd2:    compute_final_gpa = {pte.ppn[riscv::GPPNW-1:18], iova[29:0]};
            2'd1:    compute_final_gpa = {pte.ppn[riscv::GPPNW-1:9],  iova[20:0]};
            default: compute_final_gpa = {pte.ppn[riscv::GPPNW-1:0],  iova[11:0]};
        endcase
    endfunction

    function automatic logic [riscv::PLEN-1:0] s2_to_spa(
        riscv::pte_t              s2_pte,
        logic [riscv::GPLEN-1:0]  gpa,
        logic [1:0]               leaf_lvl
    );
        case (leaf_lvl)
            2'd2:    s2_to_spa = {s2_pte.ppn[riscv::PPNW-1:18], gpa[29:0]};
            2'd1:    s2_to_spa = {s2_pte.ppn[riscv::PPNW-1:9],  gpa[20:0]};
            default: s2_to_spa = {s2_pte.ppn,                    gpa[11:0]};
        endcase
    endfunction

    function automatic logic is_misaligned_s1_super(
        riscv::pte_t  p,
        logic [1:0]   lvl
    );
        case (lvl)
            2'd2:    is_misaligned_s1_super = (p.r || p.x) && (|p.ppn[17:0]);
            2'd1:    is_misaligned_s1_super = (p.r || p.x) && (|p.ppn[8:0]);
            default: is_misaligned_s1_super = 1'b0;
        endcase
    endfunction

    function automatic logic is_msi_gpa(
        logic [riscv::GPLEN-1:0]  gpa,
        logic [riscv::GPPNW-1:0]  mask,
        logic [riscv::GPPNW-1:0]  pattern,
        logic                     enabled,
        logic                     is_store
    );
        is_msi_gpa = enabled && is_store &&
                     ((gpa[riscv::GPLEN-1:12] & ~mask) == (pattern & ~mask));
    endfunction

    function automatic logic s1_perm_fault(
        riscv::pte_t  pte,
        logic         is_store,
        logic         is_rx,
        logic         priv,
        logic         sum
    );
        s1_perm_fault = ((!is_store && !is_rx && !pte.r))               ||
                        (is_store && !pte.w)                            ||
                        (is_rx && !pte.x)                               ||
                        (!priv && !pte.u)                               ||
                        (priv && pte.u && (!sum || pte.x));
    endfunction

    // ── Main FSM ─────────────────────────────────────────────────────
    always_comb begin : ctrl_fsm

        // === Defaults: registers preserve ===
        state_n             = state_q;
        phase_n             = phase_q;
        mode_n              = mode_q;
        s1_lvl_n            = s1_lvl_q;
        iova_n              = iova_q;
        pscid_n             = pscid_q;
        gscid_n             = gscid_q;
        is_store_n          = is_store_q;
        is_rx_n             = is_rx_q;
        priv_n              = priv_q;
        sum_n               = sum_q;
        iosatp_n            = iosatp_q;
        iohgatp_n           = iohgatp_q;
        en_1S_n             = en_1S_q;
        en_2S_n             = en_2S_q;
        msi_mask_n          = msi_mask_q;
        msi_patt_n          = msi_patt_q;
        msi_en_n            = msi_en_q;
        cdw_implicit_n      = cdw_implicit_q;
        pdt_gppn_n          = pdt_gppn_q;
        s1_pt_gpa_n         = s1_pt_gpa_q;
        s1_pt_spa_n         = s1_pt_spa_q;
        final_gpa_n         = final_gpa_q;
        rsp_pte_n           = rsp_pte_q;
        rsp_lvl_n           = rsp_lvl_q;
        rsp_error_n         = rsp_error_q;
        rsp_cause_n         = rsp_cause_q;
        s1_leaf_n           = s1_leaf_q;
        s1_leaf_lvl_n       = s1_leaf_lvl_q;
        s2_leaf_n           = s2_leaf_q;
        s2_leaf_lvl_n       = s2_leaf_lvl_q;
        error_in_s2_n       = error_in_s2_q;
        error_in_s2_int_n   = error_in_s2_int_q;
        cause_n             = cause_q;
        bad_gpaddr_n        = bad_gpaddr_q;
        s1_leaf_is_msi_n    = s1_leaf_is_msi_q;

        // === Defaults: walker idle ===
        walker_req_valid_o     = 1'b0;
        walker_req_op_o        = 1'b0;
        walker_req_is_sv39x4_o = 1'b0;
        walker_req_root_ppn_o  = '0;
        walker_req_va_o        = '0;
        walker_req_pptr_o      = '0;

        // === Defaults: outputs ===
        update_o            = 1'b0;
        up_1S_2M_o          = 1'b0;
        up_1S_1G_o          = 1'b0;
        up_2S_2M_o          = 1'b0;
        up_2S_1G_o          = 1'b0;
        up_vpn_o            = iova_q[riscv::SVX-1:12];
        up_pscid_o          = pscid_q;
        up_gscid_o          = gscid_q;
        up_1S_content_o     = s1_leaf_q;
        up_2S_content_o     = s2_leaf_q;
        gpaddr_is_msi_o     = 1'b0;
        msi_vpn_o           = iova_q[riscv::SVX-1:12];
        msi_1S_2M_o         = (s1_leaf_lvl_q == 2'd1);
        msi_1S_1G_o         = (s1_leaf_lvl_q == 2'd2);
        msi_gpte_o          = s1_leaf_q;
        cdw_done_o          = 1'b0;
        flush_cdw_o         = 1'b0;

        case (state_q)

            // ═════════════════════════════════════════════════════════
            // ST_IDLE: init_i 待ち、 context latch、 mode + phase 決定
            // ═════════════════════════════════════════════════════════
            ST_IDLE: begin
                // Sticky な error / msi 状態をクリア
                error_in_s2_n     = 1'b0;
                error_in_s2_int_n = 1'b0;
                s1_leaf_is_msi_n  = 1'b0;
                cause_n           = '0;
                bad_gpaddr_n      = '0;
                final_gpa_n       = '0;

                if (init_i) begin
                    iova_n          = req_iova_i;
                    pscid_n         = pscid_i;
                    gscid_n         = gscid_i;
                    is_store_n      = is_store_i;
                    is_rx_n         = is_rx_i;
                    priv_n          = priv_lvl_i;
                    sum_n           = sum_i;
                    iosatp_n        = iosatp_ppn_i;
                    iohgatp_n       = iohgatp_ppn_i;
                    en_1S_n         = en_1S_i;
                    en_2S_n         = en_2S_i;
                    msi_mask_n      = msi_addr_mask_i;
                    msi_patt_n      = msi_addr_pattern_i;
                    msi_en_n        = msi_en_i;
                    cdw_implicit_n  = cdw_implicit_access_i;
                    pdt_gppn_n      = pdt_gppn_i;

                    // mode と初期 phase を決定
                    if (cdw_implicit_access_i) begin
                        mode_n  = MODE_CDW_IMPL;
                        phase_n = PH_SINGLE;
                    end else if (en_1S_i && en_2S_i) begin
                        mode_n      = MODE_NESTED;
                        phase_n     = PH_NEST_S2_INT;
                        s1_lvl_n    = 2'd2;           // L1 から開始
                        s1_pt_gpa_n = init_s1_pt_gpa(iosatp_ppn_i, req_iova_i);
                    end else if (en_1S_i) begin
                        mode_n  = MODE_S1_ONLY;
                        phase_n = PH_SINGLE;
                    end else begin
                        mode_n  = MODE_S2_ONLY;
                        phase_n = PH_SINGLE;
                    end

                    state_n = ST_ISSUE;
                end
            end

            // ═════════════════════════════════════════════════════════
            // ST_ISSUE: phase に応じた walker request を発行
            // ═════════════════════════════════════════════════════════
            ST_ISSUE: begin
                walker_req_valid_o = 1'b1;

                case (phase_q)
                    PH_SINGLE: begin
                        walker_req_op_o = 1'b0;        // WALK
                        case (mode_q)
                            MODE_S1_ONLY: begin
                                walker_req_is_sv39x4_o = 1'b0;
                                walker_req_root_ppn_o  = iosatp_q;
                                walker_req_va_o        = iova_q;
                            end
                            MODE_S2_ONLY: begin
                                walker_req_is_sv39x4_o = 1'b1;
                                walker_req_root_ppn_o  = iohgatp_q;
                                walker_req_va_o        = iova_q;
                            end
                            MODE_CDW_IMPL: begin
                                walker_req_is_sv39x4_o = 1'b1;
                                walker_req_root_ppn_o  = iohgatp_q;
                                walker_req_va_o        = {{(riscv::VLEN-riscv::GPLEN){1'b0}},
                                                          pdt_gppn_q, 12'b0};
                            end
                            default: ;
                        endcase
                    end
                    PH_NEST_S2_INT: begin
                        walker_req_op_o        = 1'b0;
                        walker_req_is_sv39x4_o = 1'b1;
                        walker_req_root_ppn_o  = iohgatp_q;
                        walker_req_va_o        = {{(riscv::VLEN-riscv::GPLEN){1'b0}}, s1_pt_gpa_q};
                    end
                    PH_NEST_S1_RD: begin
                        walker_req_op_o   = 1'b1;       // READ
                        walker_req_pptr_o = s1_pt_spa_q;
                    end
                    PH_NEST_S2_FIN: begin
                        walker_req_op_o        = 1'b0;
                        walker_req_is_sv39x4_o = 1'b1;
                        walker_req_root_ppn_o  = iohgatp_q;
                        walker_req_va_o        = {{(riscv::VLEN-riscv::GPLEN){1'b0}}, final_gpa_q};
                    end
                endcase

                if (walker_req_ready_i) state_n = ST_WAIT;
            end

            // ═════════════════════════════════════════════════════════
            // ST_WAIT: walker の response を待つだけ。 phase 依存ロジック無し。
            //           response を generic register に latch して PROC へ。
            // ═════════════════════════════════════════════════════════
            ST_WAIT: begin
                if (walker_rsp_valid_i) begin
                    rsp_pte_n   = walker_rsp_pte_i;
                    rsp_lvl_n   = walker_rsp_lvl_i;
                    rsp_error_n = walker_rsp_error_i;
                    rsp_cause_n = walker_rsp_cause_i;
                    state_n     = ST_PROC;
                end
            end

            // ═════════════════════════════════════════════════════════
            // ST_PROC: 受信した PTE を phase に応じて解釈、 次の action を決定
            // ═════════════════════════════════════════════════════════
            ST_PROC: begin
                // ─────────────────────────────────────────────────────
                // Error 処理は phase に依らず先に分岐
                // ─────────────────────────────────────────────────────
                if (rsp_error_q) begin
                    case (phase_q)
                        PH_SINGLE: begin
                            error_in_s2_n = (mode_q != MODE_S1_ONLY);
                            if (mode_q == MODE_S1_ONLY)
                                cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT
                                                     : rv_iommu::LOAD_PAGE_FAULT;
                            else
                                cause_n = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT
                                                     : rv_iommu::LOAD_GUEST_PAGE_FAULT;

                            if (mode_q == MODE_S2_ONLY)
                                bad_gpaddr_n = iova_q[riscv::GPLEN-1:0];
                            else if (mode_q == MODE_CDW_IMPL)
                                bad_gpaddr_n = {pdt_gppn_q, 12'b0};
                            else
                                bad_gpaddr_n = '0;
                        end
                        PH_NEST_S2_INT: begin
                            cause_n           = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT
                                                           : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                            error_in_s2_n     = 1'b1;
                            error_in_s2_int_n = 1'b1;
                            bad_gpaddr_n      = s1_pt_gpa_q;
                        end
                        PH_NEST_S1_RD: begin
                            // READ 中の AXI error など
                            cause_n       = rsp_cause_q;
                            error_in_s2_n = 1'b0;
                            bad_gpaddr_n  = '0;
                        end
                        PH_NEST_S2_FIN: begin
                            cause_n           = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT
                                                           : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                            error_in_s2_n     = 1'b1;
                            error_in_s2_int_n = 1'b0;
                            bad_gpaddr_n      = final_gpa_q;
                        end
                    endcase
                    state_n = ST_ERROR;
                end
                // ─────────────────────────────────────────────────────
                // 正常 case: phase に応じた処理 + 次 action
                // ─────────────────────────────────────────────────────
                else begin
                    case (phase_q)

                        // ── 単段翻訳の leaf 受信 ─────────────────────
                        PH_SINGLE: begin
                            automatic logic s1_fault;
                            automatic logic s2_fault;
                            s1_fault = 1'b0;
                            s2_fault = 1'b0;

                            // 受信した leaf を適切な register に latch
                            if (mode_q == MODE_S1_ONLY) begin
                                s1_leaf_n     = rsp_pte_q;
                                s1_leaf_lvl_n = rsp_lvl_q;
                                // S1 perm check
                                if (!rsp_pte_q.a)                                  s1_fault = 1'b1;
                                else if (is_store_q && !rsp_pte_q.d)              s1_fault = 1'b1;
                                else if (s1_perm_fault(rsp_pte_q, is_store_q, is_rx_q, priv_q, sum_q))
                                                                                  s1_fault = 1'b1;
                            end else begin
                                s2_leaf_n     = rsp_pte_q;
                                s2_leaf_lvl_n = rsp_lvl_q;
                                // S2 perm check (= S2_ONLY、 CDW implicit は perm check スキップ)
                                if (mode_q == MODE_S2_ONLY) begin
                                    if (!rsp_pte_q.a)                              s2_fault = 1'b1;
                                    else if (is_store_q && !rsp_pte_q.d)          s2_fault = 1'b1;
                                    else if (!rsp_pte_q.u)                         s2_fault = 1'b1;
                                end
                            end

                            // 結果 dispatch
                            if (s1_fault) begin
                                cause_n       = is_store_q ? rv_iommu::STORE_PAGE_FAULT
                                                           : rv_iommu::LOAD_PAGE_FAULT;
                                error_in_s2_n = 1'b0;
                                bad_gpaddr_n  = '0;
                                state_n       = ST_ERROR;
                            end else if (s2_fault) begin
                                cause_n       = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT
                                                           : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                                error_in_s2_n = 1'b1;
                                bad_gpaddr_n  = iova_q[riscv::GPLEN-1:0];
                                state_n       = ST_ERROR;
                            end else if (mode_q == MODE_CDW_IMPL) begin
                                // CDW: 完了通知のみ (IOTLB update は出さない)
                                cdw_done_o = 1'b1;
                                up_2S_content_o = rsp_pte_q;
                                state_n    = ST_IDLE;
                            end else begin
                                update_o    = 1'b1;
                                
                                if (mode_q == MODE_S1_ONLY) begin
                                    up_1S_content_o = rsp_pte_q;          // ← FIX: fresh value from latched response
                                    up_1S_2M_o      = (rsp_lvl_q == 2'd1);
                                    up_1S_1G_o      = (rsp_lvl_q == 2'd2);
                                end else begin   // MODE_S2_ONLY
                                    up_2S_content_o = rsp_pte_q;          // ← FIX: fresh
                                    up_2S_2M_o      = (rsp_lvl_q == 2'd1);
                                    up_2S_1G_o      = (rsp_lvl_q == 2'd2);
                                end
                                state_n     = ST_IDLE;
                            end
                        end

                        // ── nested 中間 S2 walk の leaf 受信 ─────────
                        PH_NEST_S2_INT: begin
                            // S2 leaf を latch、 S1 PT entry の SPA を計算
                            s2_leaf_n     = rsp_pte_q;
                            s2_leaf_lvl_n = rsp_lvl_q;
                            s1_pt_spa_n   = s2_to_spa(rsp_pte_q, s1_pt_gpa_q, rsp_lvl_q);

                            // 次は S1 PTE 読み
                            phase_n = PH_NEST_S1_RD;
                            state_n = ST_ISSUE;
                        end

                        // ── nested S1 PTE 受信 (= 旧 S1_PROC の中身) ─
                        PH_NEST_S1_RD: begin
                            automatic riscv::pte_t pte;
                            automatic logic        misaligned;
                            pte        = rsp_pte_q;
                            misaligned = is_misaligned_s1_super(pte, s1_lvl_q);

                            // (1) Invalid → S1 fault
                            if (!pte.v || (!pte.r && pte.w) || (|pte.reserved)) begin
                                cause_n       = is_store_q ? rv_iommu::STORE_PAGE_FAULT
                                                           : rv_iommu::LOAD_PAGE_FAULT;
                                error_in_s2_n = 1'b0;
                                bad_gpaddr_n  = '0;
                                state_n       = ST_ERROR;
                            end
                            // (2) Misaligned superpage → S1 fault
                            else if (misaligned) begin
                                cause_n       = is_store_q ? rv_iommu::STORE_PAGE_FAULT
                                                           : rv_iommu::LOAD_PAGE_FAULT;
                                error_in_s2_n = 1'b0;
                                bad_gpaddr_n  = '0;
                                state_n       = ST_ERROR;
                            end
                            // (3) Leaf
                            else if (pte.r || pte.x) begin
                                s1_leaf_n     = pte;
                                s1_leaf_lvl_n = s1_lvl_q;

                                // (3a) GPPN upper-bits non-zero → guest fault
                                if (en_2S_q && (|pte.ppn[riscv::PPNW-1:riscv::GPPNW])) begin
                                    cause_n           = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT
                                                                   : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                                    error_in_s2_n     = 1'b1;
                                    error_in_s2_int_n = 1'b1;
                                    bad_gpaddr_n      = compute_final_gpa(pte, iova_q, s1_lvl_q);
                                    state_n           = ST_ERROR;
                                end
                                else if (!pte.a) begin
                                    cause_n       = is_store_q ? rv_iommu::STORE_PAGE_FAULT
                                                               : rv_iommu::LOAD_PAGE_FAULT;
                                    error_in_s2_n = 1'b0;
                                    bad_gpaddr_n  = '0;
                                    state_n       = ST_ERROR;
                                end
                                else if (is_store_q && !pte.d) begin
                                    cause_n       = rv_iommu::STORE_PAGE_FAULT;
                                    error_in_s2_n = 1'b0;
                                    bad_gpaddr_n  = '0;
                                    state_n       = ST_ERROR;
                                end
                                else if (s1_perm_fault(pte, is_store_q, is_rx_q, priv_q, sum_q)) begin
                                    cause_n       = is_store_q ? rv_iommu::STORE_PAGE_FAULT
                                                               : rv_iommu::LOAD_PAGE_FAULT;
                                    error_in_s2_n = 1'b0;
                                    bad_gpaddr_n  = '0;
                                    state_n       = ST_ERROR;
                                end
                                // (3e) S1 leaf OK → MSI check inline、 続いて最終 S2 walk
                                else begin
                                    automatic logic [riscv::GPLEN-1:0] fgpa;
                                    fgpa = compute_final_gpa(pte, iova_q, s1_lvl_q);
                                    final_gpa_n = fgpa;

                                    // ★ MSI check は専用 state 不要、 ここで判定
                                    if ((MSITrans != rv_iommu::MSI_DISABLED) &&
                                        is_msi_gpa(fgpa, msi_mask_q, msi_patt_q, msi_en_q, is_store_q)) begin
                                        // MSI handoff → IDLE (= TW が catch、 MSIPTW kick)
                                        s1_leaf_is_msi_n = 1'b1;
                                        gpaddr_is_msi_o  = 1'b1;
                                        state_n          = ST_IDLE;
                                    end else begin
                                        // 最終 S2 walk へ
                                        phase_n = PH_NEST_S2_FIN;
                                        state_n = ST_ISSUE;
                                    end
                                end
                            end
                            // (4) Non-leaf at deepest → S1 fault
                            else if (s1_lvl_q == 2'd0) begin
                                cause_n       = is_store_q ? rv_iommu::STORE_PAGE_FAULT
                                                           : rv_iommu::LOAD_PAGE_FAULT;
                                error_in_s2_n = 1'b0;
                                bad_gpaddr_n  = '0;
                                state_n       = ST_ERROR;
                            end
                            // (5) Non-leaf A/D/U set → S1 fault
                            else if (pte.a || pte.d || pte.u) begin
                                cause_n       = is_store_q ? rv_iommu::STORE_PAGE_FAULT
                                                           : rv_iommu::LOAD_PAGE_FAULT;
                                error_in_s2_n = 1'b0;
                                bad_gpaddr_n  = '0;
                                state_n       = ST_ERROR;
                            end
                            // (6) Non-leaf valid → descend (= 次レベル中間 S2 walk)
                            else begin
                                s1_pt_gpa_n = next_s1_pt_gpa(pte, iova_q, s1_lvl_q - 2'd1);
                                s1_lvl_n    = s1_lvl_q - 2'd1;
                                phase_n     = PH_NEST_S2_INT;
                                state_n     = ST_ISSUE;
                            end
                        end

                        // ── 最終 S2 walk の leaf 受信 (= 旧 PERMCHECK) ─
                        PH_NEST_S2_FIN: begin
                            automatic logic s2_fault;
                            s2_leaf_n     = rsp_pte_q;
                            s2_leaf_lvl_n = rsp_lvl_q;

                            s2_fault = (!rsp_pte_q.a)                          ||
                                       (is_store_q && !rsp_pte_q.d)            ||
                                       (!rsp_pte_q.u);

                            if (s2_fault) begin
                                cause_n       = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT
                                                           : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                                error_in_s2_n = 1'b1;
                                bad_gpaddr_n  = final_gpa_q;
                                state_n       = ST_ERROR;
                            end else begin
                                // nested 翻訳完了 → IOTLB update
                                update_o    = 1'b1;
                                up_1S_content_o = s1_leaf_q;
                                up_2S_content_o = rsp_pte_q;
                                up_1S_2M_o  = en_1S_q && (s1_leaf_lvl_q == 2'd1);
                                up_1S_1G_o  = en_1S_q && (s1_leaf_lvl_q == 2'd2);
                                up_2S_2M_o  = en_2S_q && (rsp_lvl_q == 2'd1);
                                up_2S_1G_o  = en_2S_q && (rsp_lvl_q == 2'd2);
                                state_n     = ST_IDLE;
                            end
                        end

                    endcase
                end
            end

            // ═════════════════════════════════════════════════════════
            // ST_ERROR: 1 cycle で error を伝える
            // ═════════════════════════════════════════════════════════
            ST_ERROR: begin
                flush_cdw_o = cdw_implicit_q;
                state_n     = ST_IDLE;
            end

            default: state_n = ST_IDLE;
        endcase
    end

    // ── Sequential ───────────────────────────────────────────────────
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            state_q             <= ST_IDLE;
            phase_q             <= PH_SINGLE;
            mode_q              <= MODE_S1_ONLY;
            s1_lvl_q            <= 2'd2;
            iova_q              <= '0;
            pscid_q             <= '0;
            gscid_q             <= '0;
            is_store_q          <= 1'b0;
            is_rx_q             <= 1'b0;
            priv_q              <= 1'b0;
            sum_q               <= 1'b0;
            iosatp_q            <= '0;
            iohgatp_q           <= '0;
            en_1S_q             <= 1'b0;
            en_2S_q             <= 1'b0;
            msi_mask_q          <= '0;
            msi_patt_q          <= '0;
            msi_en_q            <= 1'b0;
            cdw_implicit_q      <= 1'b0;
            pdt_gppn_q          <= '0;
            s1_pt_gpa_q         <= '0;
            s1_pt_spa_q         <= '0;
            final_gpa_q         <= '0;
            rsp_pte_q           <= '0;
            rsp_lvl_q           <= 2'd0;
            rsp_error_q         <= 1'b0;
            rsp_cause_q         <= '0;
            s1_leaf_q           <= '0;
            s1_leaf_lvl_q       <= 2'd0;
            s2_leaf_q           <= '0;
            s2_leaf_lvl_q       <= 2'd0;
            error_in_s2_q       <= 1'b0;
            error_in_s2_int_q   <= 1'b0;
            cause_q             <= '0;
            bad_gpaddr_q        <= '0;
            s1_leaf_is_msi_q    <= 1'b0;
        end else begin
            state_q             <= state_n;
            phase_q             <= phase_n;
            mode_q              <= mode_n;
            s1_lvl_q            <= s1_lvl_n;
            iova_q              <= iova_n;
            pscid_q             <= pscid_n;
            gscid_q             <= gscid_n;
            is_store_q          <= is_store_n;
            is_rx_q             <= is_rx_n;
            priv_q              <= priv_n;
            sum_q               <= sum_n;
            iosatp_q            <= iosatp_n;
            iohgatp_q           <= iohgatp_n;
            en_1S_q             <= en_1S_n;
            en_2S_q             <= en_2S_n;
            msi_mask_q          <= msi_mask_n;
            msi_patt_q          <= msi_patt_n;
            msi_en_q            <= msi_en_n;
            cdw_implicit_q      <= cdw_implicit_n;
            pdt_gppn_q          <= pdt_gppn_n;
            s1_pt_gpa_q         <= s1_pt_gpa_n;
            s1_pt_spa_q         <= s1_pt_spa_n;
            final_gpa_q         <= final_gpa_n;
            rsp_pte_q           <= rsp_pte_n;
            rsp_lvl_q           <= rsp_lvl_n;
            rsp_error_q         <= rsp_error_n;
            rsp_cause_q         <= rsp_cause_n;
            s1_leaf_q           <= s1_leaf_n;
            s1_leaf_lvl_q       <= s1_leaf_lvl_n;
            s2_leaf_q           <= s2_leaf_n;
            s2_leaf_lvl_q       <= s2_leaf_lvl_n;
            error_in_s2_q       <= error_in_s2_n;
            error_in_s2_int_q   <= error_in_s2_int_n;
            cause_q             <= cause_n;
            bad_gpaddr_q        <= bad_gpaddr_n;
            s1_leaf_is_msi_q    <= s1_leaf_is_msi_n;
        end
    end

endmodule