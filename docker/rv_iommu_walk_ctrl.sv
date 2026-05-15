// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (PR-cdw-split v4.6: pdt_gppn_late_q defensive capture)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: Walk Controller (= PTW orchestrator), v4.6
//
//   v4.6 changes:
//     - `pdt_gppn_late_q` register を追加: cdw_pdt_gppn_i が非ゼロになった瞬間に
//       latch する防御的 register。 上位 (DDTW/PDTW → wrapper) で pdt_gppn の
//       valid タイミングが snapshot より遅れる場合の workaround。
//     - compute_s2_bad_gpaddr の WM_IMPLICIT_S2 で target_gppn=0 なら
//       pdt_gppn_late_q を fallback として使用。
//
//   v4.5 changes:
//     - compute_s2_bad_gpaddr で `impl_gppn_q` の代わりに `s2_target_gppn_q` を使用
//         (= 効かず、 v4.6 で更に defensive 化)
//
//   v4.4 changes:
//     - PH_S1 / PH_S2 leaf に R/W access permission check を追加
//         load access + !pte.r → fault (= execute-only leaf を data load する場合)
//         store access + !pte.w → fault (= read-only leaf に書く場合)
//     - ENABLE_PTE_PERM_CHECK で gating
//
//   v4.3 changes:
//     - PH_S1 leaf に U bit check を追加
//         IOMMU device 要求は user-mode 扱い、 U=0 PTE → fault
//     - PH_S2 leaf に U bit check を追加
//         G-stage は常に user-mode、 U=0 PTE → fault (= spec 準拠)
//     - ENABLE_PTE_U_CHECK で gating
//
//   v4.2 changes:
//     - PH_S2 leaf に A bit / D bit check を追加 (= HW A/D update 非サポート想定)
//     - PH_S1 は v4.1 で既に追加済み (= ENABLE_PTE_AD_CHECK で gating)
//     - bad_gpaddr 計算を関数 compute_s2_bad_gpaddr() に集約 (= 重複削減)
//
//   v4.1 changes (= 引き継ぎ doc §9.1 / §9.2 を反映):
//     - superpage output 4 本を commit 経路で driven (= 2M/1G page 翻訳の修正)
//     - PH_S2 fault 経路で bad_gpaddr_n を計算 (= iotval2 を正しく返す)
//     - leaf PTE で reserved bit / 補助 check を追加
//     - leaf PTE で superpage misaligned check を追加

module rv_iommu_walk_ctrl
    import rv_iommu::*;
#(
    // ── Debug parameters (= 段階的に check を切って bug を切り分ける用) ────
    // 1 で有効、 0 で無効
    parameter logic ENABLE_PTE_RESERVED_CHECK = 1'b1,
    parameter logic ENABLE_PTE_MISALIGN_CHECK = 1'b1,
    // A/D check: HW A/D update 非サポート前提で walk 中に fault を上げる。
    // 1 で有効 (= spec 準拠 / libiommu と一致)、 0 で無効 (= IOTLB hit path で判定する旧設計)
    parameter logic ENABLE_PTE_AD_CHECK       = 1'b1,
    // U bit check: IOMMU device 要求は user-mode 扱い、 U=0 PTE で fault。
    // S1 / S2 両方に適用。 G-stage (S2) は spec で「U=1 必須」 と規定されている。
    parameter logic ENABLE_PTE_U_CHECK        = 1'b1,
    // R/W access permission check: access type と PTE 権限の整合性
    //   load + !R  → fault (= 例: execute-only leaf を data load)
    //   store + !W → fault (= 例: read-only leaf に書き込み)
    parameter logic ENABLE_PTE_PERM_CHECK     = 1'b1
)
(
    input  logic                                clk_i,
    input  logic                                rst_ni,

    // ── Triggers ────────────────────────────────────────────────────
    input  logic                                init_i,
    input  logic                                cdw_implicit_access_i,
    input  logic                                flush_i,

    // ── Translation request inputs ──────────────────────────────────
    input  logic [riscv::VLEN-1:0]              iova_i,
    input  logic                                is_store_i,
    input  logic                                is_rx_i,
    input  logic                                priv_lvl_i,
    input  logic                                sum_i,
    input  logic                                en_stage1_i,
    input  logic                                en_stage2_i,

    // ── PT root pointers ────────────────────────────────────────────
    input  logic [riscv::PPNW-1:0]              iosatp_ppn_i,
    input  logic [3:0]                          iosatp_mode_i,
    input  logic [riscv::PPNW-1:0]              iohgatp_ppn_i,
    input  logic [3:0]                          iohgatp_mode_i,

    // ── Implicit S2 GPPN ────────────────────────────────────────────
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

    // ── To DDTW/PDTW ────────────────────────────────────────────────
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
        WM_IMPLICIT_S2
    } walk_mode_t;
    walk_mode_t walk_mode_q, walk_mode_n;

    // ── Level ───────────────────────────────────────────────────────
    logic [1:0]                                 s1_lvl_q, s1_lvl_n;
    logic [1:0]                                 s2_lvl_q, s2_lvl_n;

    // ── PT pointers ─────────────────────────────────────────────────
    logic [riscv::PLEN-1:0]                     s1_pptr_q, s1_pptr_n;
    logic [riscv::PLEN-1:0]                     s2_pptr_q, s2_pptr_n;

    // ── Captured PTEs ───────────────────────────────────────────────
    riscv::pte_t                             pte_pending_q, pte_pending_n;
    riscv::pte_t                             s1_leaf_q,     s1_leaf_n;
    riscv::pte_t                             s2_leaf_q,     s2_leaf_n;

    // ── Snapshot at init ────────────────────────────────────────────
    logic [riscv::VLEN-1:0]                     iova_q;
    logic                                       is_store_q, is_rx_q, priv_lvl_q, sum_q;
    logic                                       en_s1_q, en_s2_q;
    logic [riscv::GPPNW-1:0]                    impl_gppn_q;

    // ── 防御的 late capture: cdw_pdt_gppn_i を非ゼロ時に latch ──────
    //   v4.6: upstream で pdt_gppn が snapshot タイミングより遅れて valid に
    //   なるケースの workaround。 PROC/ERROR 以外の state で cdw_pdt_gppn_i
    //   が非ゼロになった瞬間に latch、 walk 中保持する。
    logic [riscv::GPPNW-1:0]                    pdt_gppn_late_q;

    // ── S2 walk 中の「翻訳対象 gppn」 を保持 ─────────────────────────
    //   S2 walk は root → mid → leaf と 3 段降りるが、 全 level で同じ gppn
    //   の異なる bit segment (= [28:18] / [17:9] / [8:0]) を index に使う。
    //   なので「降下中の gppn」 を register で保持する必要がある。
    //   - WM_SINGLE_S2:   iova 由来 → S2 walk 開始時に snapshot
    //   - WM_IMPLICIT_S2: cdw_pdt_gppn_i 由来 → 同上
    //   - WM_NESTED:      毎回の S1 PTE.ppn → S1→S2 遷移時に更新
    logic [riscv::GPPNW-1:0]                    s2_target_gppn_q, s2_target_gppn_n;

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

    // ── VPN segment extractors ──────────────────────────────────────
    function automatic logic [8:0] vpn_seg_s1(input logic [riscv::VLEN-1:0] va, input logic [1:0] lvl);
        case (lvl)
            2'd2: return va[38:30];
            2'd1: return va[29:21];
            2'd0: return va[20:12];
            default: return '0;
        endcase
    endfunction

    // ── Helper: PTE misaligned at superpage level ───────────────────
    //   1G page (lvl=2) → PPN[17:0] must be 0
    //   2M page (lvl=1) → PPN[ 8:0] must be 0
    //   4K page (lvl=0) → no constraint
    function automatic logic pte_misaligned(input riscv::pte_t pte, input logic [1:0] lvl);
        case (lvl)
            2'd2: return |pte.ppn[17:0];
            2'd1: return |pte.ppn[8:0];
            default: return 1'b0;
        endcase
    endfunction

    // ── Helper: Sv39x4 S2 PT entry address ──────────────────────────
    //   bit ぴったり 56 bit (= riscv::PLEN) になるよう lvl ごとに concat:
    //
    //   root (lvl=2): 16 KiB PT、 2048 entries (= 11-bit index)
    //     - iohgatp.PPN[1:0] = 0 が DDTW で保証 → 下位 2 bit を捨ててよい
    //     - {base_ppn[43:2] (42)  ,  gppn[28:18] (11)  ,  3'b0 (3)} = 56 bit ✓
    //     - PA[13:12] = gppn[28:27]  (= 元の base_ppn[1:0] と重なる場所だが 0 なので問題なし)
    //
    //   mid / leaf (lvl=1, 0): 4 KiB PT、 512 entries (= 9-bit index)
    //     - 4K aligned なので base_ppn[43:0] を全部使う
    //     - {base_ppn[43:0] (44)  ,  gppn segment (9)  ,  3'b0 (3)} = 56 bit ✓
    function automatic logic [riscv::PLEN-1:0] make_s2_pptr(
        input logic [riscv::PPNW-1:0]  base_ppn,
        input logic [riscv::GPPNW-1:0] gppn,
        input logic [1:0]              lvl
    );
        case (lvl)
            // root: ppn[1:0]=0 保証で drop、 11-bit gppn と合体
            2'd2: return {base_ppn[riscv::PPNW-1:2], gppn[28:18], 3'b0};
            // mid: 9-bit gppn を入れる
            2'd1: return {base_ppn,                  gppn[17: 9], 3'b0};
            // leaf: 同上
            2'd0: return {base_ppn,                  gppn[ 8: 0], 3'b0};
            default: return '0;
        endcase
    endfunction

    // ── Helper: S2 fault 時の bad_gpaddr (= iotval2) を計算 ──────────
    //   PH_S2 の各 fault パス (= V/reserved/misalign/A/D/non-leaf-bottom) で
    //   重複していたロジックを 1 ヶ所に集約。 walk_mode と s1_lvl に応じて
    //   「失敗した S2 access が指す GPA」 を返す。
    //
    //   ★ v4.5: WM_IMPLICIT_S2 で target_gppn (= s2_target_gppn_q) を使う。
    //           impl_gppn_q ではなく s2_target_gppn_q を使う理由:
    //           - 両者とも cdw_pdt_gppn_i から latch されるが、 s2_target_gppn_q は
    //             全 walk_mode で統一されている canonical 「現在 S2 翻訳中の GPPN」
    //           - impl_gppn_q が 0 になる upstream timing issue 回避
    function automatic logic [riscv::SVX-1:0] compute_s2_bad_gpaddr(
        input walk_mode_t                walk_mode,
        input logic [1:0]                s1_lvl,
        input riscv::pte_t               s1_leaf,
        input logic [riscv::GPPNW-1:0]   target_gppn,   // ★ s2_target_gppn_q を渡す
        input logic [riscv::VLEN-1:0]    iova
    );
        case (walk_mode)
            WM_SINGLE_S2:   return iova[riscv::SVX-1:0];
            WM_NESTED: begin
                case (s1_lvl)
                    2'd0:    return {s1_leaf.ppn[riscv::GPPNW-1:0],   iova[11:0]};
                    2'd1:    return {s1_leaf.ppn[riscv::GPPNW-1:9],   iova[20:0]};
                    2'd2:    return {s1_leaf.ppn[riscv::GPPNW-1:18],  iova[29:0]};
                    default: return '0;
                endcase
            end
            // v4.6: target_gppn (= s2_target_gppn_q) が 0 なら pdt_gppn_late_q を
            // fallback として使う。 後者は cdw_pdt_gppn_i を非ゼロ時に late latch
            // した値で、 upstream の timing skew に対応する。
            WM_IMPLICIT_S2: return {(target_gppn != '0 ? target_gppn : pdt_gppn_late_q), 12'b0};
            default:        return '0;
        endcase
    endfunction

    // ── Status outputs ──────────────────────────────────────────────
    assign active_o = (state_q != ST_IDLE);

    // ── walker hand-shake ───────────────────────────────────────────
    assign walker_req_addr_o  = (phase_q == PH_S1) ? s1_pptr_q : s2_pptr_q;
    assign walker_req_valid_o = (state_q == ST_ISSUE);
    assign walker_rsp_ready_o = (state_q == ST_WAIT);

    // ── pte_view ────────────────────────────────────────────────────
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
        s2_target_gppn_n = s2_target_gppn_q;

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
                        walk_mode_n      = WM_IMPLICIT_S2;
                        s2_lvl_n         = 2'd2;
                        s2_pptr_n        = make_s2_pptr(iohgatp_ppn_i, cdw_pdt_gppn_i, 2'd2);
                        s2_target_gppn_n = cdw_pdt_gppn_i;     // ★ S2 walk 中保持
                        phase_n          = PH_S2;
                    end
                    else if (en_stage1_i && en_stage2_i) begin
                        walk_mode_n = WM_NESTED;
                        s1_lvl_n    = 2'd2;
                        s1_pptr_n   = {iosatp_ppn_i, vpn_seg_s1(iova_i, 2'd2), 3'b0};
                        phase_n     = PH_S1;
                        // s2_target_gppn は S1→S2 遷移時に設定 (= まだ S2 walk 開始してない)
                    end
                    else if (en_stage1_i) begin
                        walk_mode_n = WM_SINGLE_S1;
                        s1_lvl_n    = 2'd2;
                        s1_pptr_n   = {iosatp_ppn_i, vpn_seg_s1(iova_i, 2'd2), 3'b0};
                        phase_n     = PH_S1;
                    end
                    else if (en_stage2_i) begin
                        walk_mode_n      = WM_SINGLE_S2;
                        s2_lvl_n         = 2'd2;
                        s2_pptr_n        = make_s2_pptr(iohgatp_ppn_i,
                                                        iova_i[riscv::SVX-1:12], 2'd2);
                        s2_target_gppn_n = iova_i[riscv::SVX-1:12];   // ★ S2 walk 中保持
                        phase_n          = PH_S2;
                    end
                    state_n = ST_ISSUE;
                end
            end

            // ─────────────────────────────────────────────────────────
            ST_ISSUE: begin
                if (walker_req_ready_i) begin
                    state_n = ST_WAIT;
                end
            end

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

                    // ─────────────────────────────────────────────────
                    // PH_S1
                    // ─────────────────────────────────────────────────
                    PH_S1: begin
                        // (a) 基本 fault: V=0 or (R=0 & W=1)
                        if (!pte_pending_q.v || (!pte_pending_q.r && pte_pending_q.w)) begin
                            cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT : rv_iommu::LOAD_PAGE_FAULT;
                            state_n = ST_ERROR;
                        end
                        // (b) reserved bit fault (= pte_reserved_s1 カテゴリ用)
                        else if (ENABLE_PTE_RESERVED_CHECK && |pte_pending_q.reserved) begin
                            cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT : rv_iommu::LOAD_PAGE_FAULT;
                            state_n = ST_ERROR;
                        end
                        // (c) leaf detection
                        else if (pte_pending_q.r || pte_pending_q.x) begin
                            // (c-1) superpage misaligned check
                            if (ENABLE_PTE_MISALIGN_CHECK && pte_misaligned(pte_pending_q, s1_lvl_q)) begin
                                cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT : rv_iommu::LOAD_PAGE_FAULT;
                                state_n = ST_ERROR;
                            end
                            // ★ (c-2) U bit check (S1)
                            // IOMMU device 要求は user-mode 扱い、 U=0 PTE で fault
                            // (= access_matrix_s1 など、 S1 U=0 で fault が期待されるテスト用)
                            else if (ENABLE_PTE_U_CHECK && !pte_pending_q.u) begin
                                cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT : rv_iommu::LOAD_PAGE_FAULT;
                                state_n = ST_ERROR;
                            end
                            // ★ (c-3) R access check (S1)
                            // load access で R=0 (= 実行のみ leaf) は fault
                            else if (ENABLE_PTE_PERM_CHECK && !is_store_q && !pte_pending_q.r) begin
                                cause_n = rv_iommu::LOAD_PAGE_FAULT;
                                state_n = ST_ERROR;
                            end
                            // ★ (c-4) W access check (S1)
                            // store access で W=0 (= read-only leaf) は fault
                            else if (ENABLE_PTE_PERM_CHECK && is_store_q && !pte_pending_q.w) begin
                                cause_n = rv_iommu::STORE_PAGE_FAULT;
                                state_n = ST_ERROR;
                            end
                            // ★ (c-5) A bit check (S1)
                            // HW A/D update 非サポートのため、 A=0 は任意 access で fault
                            else if (ENABLE_PTE_AD_CHECK && !pte_pending_q.a) begin
                                cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT : rv_iommu::LOAD_PAGE_FAULT;
                                state_n = ST_ERROR;
                            end
                            // ★ (c-6) D bit check (S1)
                            // store access で D=0 は fault
                            else if (ENABLE_PTE_AD_CHECK && is_store_q && !pte_pending_q.d) begin
                                cause_n = rv_iommu::STORE_PAGE_FAULT;
                                state_n = ST_ERROR;
                            end
                            else begin
                                // ── Valid leaf S1 PTE ──
                                s1_leaf_n = pte_pending_q;
                                if (walk_mode_q == WM_NESTED) begin
                                    // S2 walk on leaf PPN
                                    s2_lvl_n         = 2'd2;
                                    s2_pptr_n        = make_s2_pptr(iohgatp_ppn_i,
                                                                     pte_pending_q.ppn[riscv::GPPNW-1:0], 2'd2);
                                    s2_target_gppn_n = pte_pending_q.ppn[riscv::GPPNW-1:0];  // ★
                                    phase_n          = PH_S2;
                                    state_n          = ST_ISSUE;
                                end
                                else begin
                                    // single S1: commit
                                    update_iotlb_o      = 1'b1;
                                    update_vpn_o        = iova_q[riscv::SVX-1:12];
                                    update_1S_content_o = pte_pending_q;
                                    update_1S_2M_o      = (s1_lvl_q == 2'd1);
                                    update_1S_1G_o      = (s1_lvl_q == 2'd2);
                                    state_n             = ST_IDLE;
                                end
                            end
                        end
                        // (d) non-leaf
                        else begin
                            // (d-0) ★ 共通: bottom level (s1_lvl=0) で leaf じゃない = S1 page-fault
                            //         WM_NESTED でも例外なし (= spec 通り)
                            if (s1_lvl_q == 2'd0) begin
                                cause_n = is_store_q ? rv_iommu::STORE_PAGE_FAULT : rv_iommu::LOAD_PAGE_FAULT;
                                state_n = ST_ERROR;
                            end
                            // (d-1) WM_NESTED: 中間 NL の PPN を GPA として S2 翻訳
                            else if (walk_mode_q == WM_NESTED) begin
                                s2_lvl_n         = 2'd2;
                                s2_pptr_n        = make_s2_pptr(iohgatp_ppn_i,
                                                                 pte_pending_q.ppn[riscv::GPPNW-1:0], 2'd2);
                                s2_target_gppn_n = pte_pending_q.ppn[riscv::GPPNW-1:0];  // ★
                                phase_n          = PH_S2;
                                state_n          = ST_ISSUE;
                            end
                            // (d-2) SINGLE_S1: 次レベルへ
                            else begin
                                s1_lvl_n  = s1_lvl_q - 1;
                                s1_pptr_n = {pte_pending_q.ppn,
                                             vpn_seg_s1(iova_q, s1_lvl_q - 1), 3'b0};
                                state_n   = ST_ISSUE;
                            end
                        end
                    end

                    // ─────────────────────────────────────────────────
                    // PH_S2
                    // ─────────────────────────────────────────────────
                    PH_S2: begin
                        // (a) 基本 fault: V=0 or (R=0 & W=1)
                        if (!pte_pending_q.v || (!pte_pending_q.r && pte_pending_q.w)) begin
                            cause_n = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                            is_2S_n = 1'b1;
                            bad_gpaddr_n = compute_s2_bad_gpaddr(walk_mode_q, s1_lvl_q, s1_leaf_q, s2_target_gppn_q, iova_q);
                            state_n = ST_ERROR;
                        end
                        // (b) reserved bit fault
                        else if (ENABLE_PTE_RESERVED_CHECK && |pte_pending_q.reserved) begin
                            cause_n = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                            is_2S_n = 1'b1;
                            bad_gpaddr_n = compute_s2_bad_gpaddr(walk_mode_q, s1_lvl_q, s1_leaf_q, s2_target_gppn_q, iova_q);
                            state_n = ST_ERROR;
                        end
                        // (c) leaf detection
                        else if (pte_pending_q.r || pte_pending_q.x) begin
                            // (c-1) superpage misaligned
                            if (ENABLE_PTE_MISALIGN_CHECK && pte_misaligned(pte_pending_q, s2_lvl_q)) begin
                                cause_n = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                                is_2S_n = 1'b1;
                                bad_gpaddr_n = compute_s2_bad_gpaddr(walk_mode_q, s1_lvl_q, s1_leaf_q, s2_target_gppn_q, iova_q);
                                state_n = ST_ERROR;
                            end
                            // ★ (c-2) U bit check (S2)
                            // G-stage は spec で「U=1 必須」 と規定 (= 全アクセス user-mode 扱い)
                            // U=0 の S2 PTE で fault
                            else if (ENABLE_PTE_U_CHECK && !pte_pending_q.u) begin
                                cause_n = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                                is_2S_n = 1'b1;
                                bad_gpaddr_n = compute_s2_bad_gpaddr(walk_mode_q, s1_lvl_q, s1_leaf_q, s2_target_gppn_q, iova_q);
                                state_n = ST_ERROR;
                            end
                            // ★ (c-3) R access check (S2)
                            // load access で R=0 (= 実行のみ leaf) は fault
                            else if (ENABLE_PTE_PERM_CHECK && !is_store_q && !pte_pending_q.r) begin
                                cause_n = rv_iommu::LOAD_GUEST_PAGE_FAULT;
                                is_2S_n = 1'b1;
                                bad_gpaddr_n = compute_s2_bad_gpaddr(walk_mode_q, s1_lvl_q, s1_leaf_q, s2_target_gppn_q, iova_q);
                                state_n = ST_ERROR;
                            end
                            // ★ (c-4) W access check (S2)
                            // store access で W=0 (= read-only leaf) は fault
                            else if (ENABLE_PTE_PERM_CHECK && is_store_q && !pte_pending_q.w) begin
                                cause_n = rv_iommu::STORE_GUEST_PAGE_FAULT;
                                is_2S_n = 1'b1;
                                bad_gpaddr_n = compute_s2_bad_gpaddr(walk_mode_q, s1_lvl_q, s1_leaf_q, s2_target_gppn_q, iova_q);
                                state_n = ST_ERROR;
                            end
                            // ★ (c-5) A bit check (S2)
                            // HW A/D update 非サポートのため、 A=0 は任意 access で fault
                            else if (ENABLE_PTE_AD_CHECK && !pte_pending_q.a) begin
                                cause_n = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                                is_2S_n = 1'b1;
                                bad_gpaddr_n = compute_s2_bad_gpaddr(walk_mode_q, s1_lvl_q, s1_leaf_q, s2_target_gppn_q, iova_q);
                                state_n = ST_ERROR;
                            end
                            // ★ (c-6) D bit check (S2)
                            // store access で D=0 は fault
                            else if (ENABLE_PTE_AD_CHECK && is_store_q && !pte_pending_q.d) begin
                                cause_n = rv_iommu::STORE_GUEST_PAGE_FAULT;
                                is_2S_n = 1'b1;
                                bad_gpaddr_n = compute_s2_bad_gpaddr(walk_mode_q, s1_lvl_q, s1_leaf_q, s2_target_gppn_q, iova_q);
                                state_n = ST_ERROR;
                            end
                            else begin
                                // ── Valid leaf S2 PTE ──
                                s2_leaf_n = pte_pending_q;
                                case (walk_mode_q)
                                    WM_IMPLICIT_S2: begin
                                        ptw_done_o          = 1'b1;
                                        pdt_ppn_o           = pte_pending_q.ppn;
                                        update_2S_content_o = pte_pending_q;
                                        state_n             = ST_IDLE;
                                    end
                                    WM_NESTED: begin
                                        if (s1_leaf_q.r || s1_leaf_q.x) begin
                                            // 両 leaf → commit (= 最終 SPA)
                                            update_iotlb_o      = 1'b1;
                                            update_vpn_o        = iova_q[riscv::SVX-1:12];
                                            update_1S_content_o = s1_leaf_q;
                                            update_2S_content_o = pte_pending_q;
                                            update_1S_2M_o      = (s1_lvl_q == 2'd1);
                                            update_1S_1G_o      = (s1_lvl_q == 2'd2);
                                            update_2S_2M_o      = (s2_lvl_q == 2'd1);
                                            update_2S_1G_o      = (s2_lvl_q == 2'd2);
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
                                        update_2S_2M_o      = (s2_lvl_q == 2'd1);
                                        update_2S_1G_o      = (s2_lvl_q == 2'd2);
                                        state_n             = ST_IDLE;
                                    end
                                    default: state_n = ST_IDLE;
                                endcase
                            end
                        end
                        // (d) non-leaf
                        else begin
                            if (s2_lvl_q > 0) begin
                                s2_lvl_n = s2_lvl_q - 1;
                                // ★ FIX: 全 walk_mode で同一 gppn (= s2_target_gppn_q) を使う
                                //   旧: WM_NESTED で pte_pending_q.ppn を gppn として再翻訳しに行く bug
                                //   新: S2 walk 開始時に snapshot した gppn を保持して使い回す
                                s2_pptr_n = make_s2_pptr(pte_pending_q.ppn,
                                                         s2_target_gppn_q,
                                                         s2_lvl_q - 1);
                                state_n = ST_ISSUE;
                            end
                            else begin
                                cause_n = is_store_q ? rv_iommu::STORE_GUEST_PAGE_FAULT : rv_iommu::LOAD_GUEST_PAGE_FAULT;
                                is_2S_n = 1'b1;
                                bad_gpaddr_n = compute_s2_bad_gpaddr(walk_mode_q, s1_lvl_q, s1_leaf_q, s2_target_gppn_q, iova_q);
                                state_n = ST_ERROR;
                            end
                        end
                    end

                    default: state_n = ST_IDLE;
                endcase
            end

            // ─────────────────────────────────────────────────────────
            ST_ERROR: begin
                ptw_error_o    = 1'b1;
                ptw_error_2S_o = is_2S_q;
                cause_code_o   = cause_q;
                // iotval2 (= bad_gpaddr) は spec section 6.7 で「 bits [1:0] = 0」
                // と規定されているので、 出力段で常に下位 2 bit をマスク
                bad_gpaddr_o   = {bad_gpaddr_q[riscv::SVX-1:2], 2'b00};
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
            impl_gppn_q       <= '0;
            pdt_gppn_late_q   <= '0;
            s2_target_gppn_q  <= '0;
            cause_q           <= '0;
            is_2S_q           <= 1'b0;
            bad_gpaddr_q      <= '0;
            edge_trigger_q    <= 1'b0;
        end else begin
            state_q           <= state_n;
            phase_q           <= phase_n;
            walk_mode_q       <= walk_mode_n;
            s1_lvl_q          <= s1_lvl_n;
            s2_lvl_q          <= s2_lvl_n;
            s1_pptr_q         <= s1_pptr_n;
            s2_pptr_q         <= s2_pptr_n;
            pte_pending_q     <= pte_pending_n;
            s1_leaf_q         <= s1_leaf_n;
            s2_leaf_q         <= s2_leaf_n;
            cause_q           <= cause_n;
            is_2S_q           <= is_2S_n;
            bad_gpaddr_q      <= bad_gpaddr_n;
            s2_target_gppn_q  <= s2_target_gppn_n;
            edge_trigger_q    <= edge_trigger_n;
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

            // ★ v4.6: 防御的 late capture
            //   cdw_pdt_gppn_i が PROC/ERROR 以外の state で非ゼロになったら
            //   pdt_gppn_late_q に latch。 何度でも上書き可能 (= 最新値を保持)。
            //   walk 開始直後に cdw_pdt_gppn_i が valid になった場合、 snapshot
            //   時には 0 で取れていても late_q には正しい値が入る。
            if (cdw_pdt_gppn_i != '0
                  && state_q != ST_PROC
                  && state_q != ST_ERROR) begin
                pdt_gppn_late_q <= cdw_pdt_gppn_i;
            end
        end
    end

endmodule
