// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (PR-cdw-split v4: PROC state added)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: Process Directory Table Walker (PDTW), v4
//
//   v4 changes (vs v3):
//     - ST_PROC state を追加 (= 検査・分岐・次動作決定の中心地)
//     - ST_WAIT は「捕捉」のみ、 検査は ST_PROC で
//     - ST_ERROR は drain + error pulse のみ
//
//   State machine: IDLE / ISSUE / WAIT / PROC / ERROR (5 states)
//   Phase: PH_NL_S1 / PH_NL_S2 / PH_LEAF_S1 / PH_LEAF_S2

module rv_iommu_pdtw
    import rv_iommu::*;
#(
    parameter type axi_req_t                    = logic,
    parameter type axi_rsp_t                    = logic
) (
    input  logic                                clk_i,
    input  logic                                rst_ni,

    output logic                                active_o,
    output logic                                error_o,
    output logic [rv_iommu::CAUSE_LEN-1:0]      cause_code_o,

    input  axi_rsp_t                            mem_resp_i,
    output axi_req_t                            mem_req_o,

    output logic                                update_pc_o,
    output logic [23:0]                         up_did_o,
    output logic [19:0]                         up_pid_o,
    output rv_iommu::pc_t                       up_pc_content_o,

    input  logic [23:0]                         req_did_i,
    input  logic [19:0]                         req_pid_i,
    input  logic                                init_i,

    input  logic                                en_stage2_i,
    input  logic [riscv::PPNW-1:0]              pdtp_ppn_i,
    input  logic [3:0]                          pdtp_mode_i,

    input  logic                                ptw_done_i,
    input  logic                                flush_i,
    input  logic [riscv::PPNW-1:0]              pdt_ppn_i,
    output logic                                cdw_implicit_access_o,
    output logic [riscv::GPPNW-1:0]             pdt_gppn_o
);

    // ── States (= 5 種類) ────────────────────────────────────────────
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
        PH_NL_S1,
        PH_NL_S2,
        PH_LEAF_S1,
        PH_LEAF_S2
    } phase_t;
    phase_t phase_q, phase_n;

    // ── Level ───────────────────────────────────────────────────────
    typedef enum logic [2:0] {
        OFF, BARE, LVL1, LVL2, LVL3
    } level_t;
    level_t cdw_lvl_q, cdw_lvl_n;

    logic [riscv::PLEN-1:0]                     cdw_pptr_q, cdw_pptr_n;
    logic [23:0]                                device_id_q, device_id_n;
    logic [19:0]                                process_id_q, process_id_n;

    // PC captured registers
    rv_iommu::pc_ta_t                           pc_ta_q,  pc_ta_n;
    rv_iommu::fsc_t                             pc_fsc_q, pc_fsc_n;

    // NL captured register (= PROC で参照)
    rv_iommu::nl_entry_t                        nl_pending_q, nl_pending_n;

    // S2 walk request GPPN + response SPA
    logic [riscv::GPPNW-1:0]                    pdt_gppn_q, pdt_gppn_n;
    logic [riscv::PPNW-1:0]                     pdt_spa_q,  pdt_spa_n;

    logic [2:0]                                 entry_cnt_q, entry_cnt_n;
    logic                                       pc_fully_loaded;

    logic [rv_iommu::CAUSE_LEN-1:0]             cause_q, cause_n;
    logic                                       wait_rlast_q, wait_rlast_n;

    // ── Edge-triggered init ─────────────────────────────────────────
    logic edge_trigger_q, edge_trigger_n;
    always_comb begin : init_edge
        edge_trigger_n = edge_trigger_q;
        if (!edge_trigger_q &&  init_i) edge_trigger_n = 1'b1;
        if ( edge_trigger_q && !init_i) edge_trigger_n = 1'b0;
    end
    wire init_rising_edge = init_i && !edge_trigger_q;

    // ── Casts (= 受信中の data の view) ─────────────────────────────
    rv_iommu::pc_ta_t       pc_ta_view;
    rv_iommu::fsc_t         pc_fsc_view;
    rv_iommu::nl_entry_t    nl_view;
    assign pc_ta_view  = rv_iommu::pc_ta_t'(mem_resp_i.r.data);
    assign pc_fsc_view = rv_iommu::fsc_t'(mem_resp_i.r.data);
    assign nl_view     = rv_iommu::nl_entry_t'(mem_resp_i.r.data);

    // ── Status ──────────────────────────────────────────────────────
    assign active_o        = (state_q != ST_IDLE);
    assign pc_fully_loaded = (entry_cnt_q == 3'b010);
    assign up_did_o        = device_id_q;
    assign up_pid_o        = process_id_q;
    assign up_pc_content_o.ta  = pc_ta_q;
    assign up_pc_content_o.fsc = pc_fsc_q;

    // ── Need leaf S2 翻訳? ───────────────────────────────────────────
    logic need_leaf_s2;
    assign need_leaf_s2 = en_stage2_i && (pc_fsc_q.mode != 4'b0000);

    // ── Helper: next pptr ───────────────────────────────────────────
    function automatic logic [riscv::PLEN-1:0] next_pptr(
        input logic [riscv::PPNW-1:0] base_ppn,
        input level_t                 curr_lvl,
        input logic [19:0]            pid
    );
        case (curr_lvl)
            LVL3:    return {base_ppn, pid[16:8], 3'b0};
            LVL2:    return {base_ppn, pid[7:0],  4'b0};
            default: return '0;
        endcase
    endfunction

    // ──────────────────────────────────────────────────────────────────
    // Main FSM
    // ──────────────────────────────────────────────────────────────────
    always_comb begin : pdtw_fsm
        state_n               = state_q;
        phase_n               = phase_q;
        cdw_lvl_n             = cdw_lvl_q;
        cdw_pptr_n            = cdw_pptr_q;
        device_id_n           = device_id_q;
        process_id_n          = process_id_q;
        entry_cnt_n           = entry_cnt_q;
        pc_ta_n               = pc_ta_q;
        pc_fsc_n              = pc_fsc_q;
        nl_pending_n          = nl_pending_q;
        pdt_gppn_n            = pdt_gppn_q;
        pdt_spa_n             = pdt_spa_q;
        cause_n               = cause_q;
        wait_rlast_n          = wait_rlast_q;

        error_o               = 1'b0;
        cause_code_o          = '0;
        update_pc_o           = 1'b0;
        cdw_implicit_access_o = 1'b0;
        pdt_gppn_o            = '0;

        mem_req_o          = '0;
        mem_req_o.ar.id    = 4'b0010;
        mem_req_o.ar.addr  = {{riscv::XLEN-riscv::PLEN{1'b0}}, cdw_pptr_q};
        mem_req_o.ar.len   = (phase_q == PH_LEAF_S1) ? 8'd1 : 8'd0;
        mem_req_o.ar.size  = 3'b011;
        mem_req_o.ar.burst = axi_pkg::BURST_INCR;
        mem_req_o.ar_valid = 1'b0;
        mem_req_o.r_ready  = 1'b0;

        case (state_q)

            // ─────────────────────────────────────────────────────────
            ST_IDLE: begin
                device_id_n  = req_did_i;
                entry_cnt_n  = '0;
                wait_rlast_n = 1'b0;

                if (init_rising_edge) begin
                    process_id_n = req_pid_i;
                    cdw_lvl_n    = level_t'(pdtp_mode_i + 4'd1);
                    phase_n      = (pdtp_mode_i == 4'b0001) ? PH_LEAF_S1 : PH_NL_S1;
                    state_n      = ST_ISSUE;

                    if (pdtp_mode_i == 4'b0011)
                        cdw_pptr_n = {pdtp_ppn_i, 6'b0, req_pid_i[19:17], 3'b0};
                    else if (pdtp_mode_i == 4'b0010)
                        cdw_pptr_n = {pdtp_ppn_i, req_pid_i[16:8], 3'b0};
                    else if (pdtp_mode_i == 4'b0001)
                        cdw_pptr_n = {pdtp_ppn_i, req_pid_i[7:0], 4'b0};
                end
            end

            // ─────────────────────────────────────────────────────────
            // ST_ISSUE: phase に応じた信号発行
            // ─────────────────────────────────────────────────────────
            ST_ISSUE: begin
                case (phase_q)
                    PH_NL_S1, PH_LEAF_S1: begin
                        mem_req_o.ar_valid = 1'b1;
                        if (mem_resp_i.ar_ready) state_n = ST_WAIT;
                    end
                    PH_NL_S2, PH_LEAF_S2: begin
                        cdw_implicit_access_o = 1'b1;
                        pdt_gppn_o            = pdt_gppn_q;
                        state_n               = ST_WAIT;
                    end
                    default: state_n = ST_IDLE;
                endcase
            end

            // ─────────────────────────────────────────────────────────
            // ST_WAIT: 「受信して捕捉」のみ。 検査は PROC で
            // ─────────────────────────────────────────────────────────
            ST_WAIT: begin
                case (phase_q)

                    PH_NL_S1: begin
                        if (mem_resp_i.r_valid) begin
                            mem_req_o.r_ready = 1'b1;
                            // AXI bus error は ここで即 ERROR
                            if (mem_resp_i.r.resp != axi_pkg::RESP_OKAY) begin
                                cause_n      = rv_iommu::PDT_DATA_CORRUPTION;
                                wait_rlast_n = ~mem_resp_i.r.last;
                                state_n      = ST_ERROR;
                            end
                            else begin
                                nl_pending_n = nl_view;
                                state_n      = ST_PROC;
                            end
                        end
                    end

                    PH_LEAF_S1: begin
                        if (mem_resp_i.r_valid) begin
                            mem_req_o.r_ready = 1'b1;
                            if (mem_resp_i.r.resp != axi_pkg::RESP_OKAY) begin
                                cause_n      = rv_iommu::PDT_DATA_CORRUPTION;
                                wait_rlast_n = ~mem_resp_i.r.last;
                                state_n      = ST_ERROR;
                            end
                            else begin
                                entry_cnt_n = entry_cnt_q + 1;
                                case (entry_cnt_q)
                                    3'b000: pc_ta_n  = pc_ta_view;
                                    3'b001: pc_fsc_n = pc_fsc_view;
                                    default: ;
                                endcase
                                // 最終 beat (r.last) 到着で PROC へ
                                if (mem_resp_i.r.last) state_n = ST_PROC;
                            end
                        end
                    end

                    PH_NL_S2, PH_LEAF_S2: begin
                        if (ptw_done_i) begin
                            if (phase_q == PH_NL_S2) pdt_spa_n = pdt_ppn_i;
                            else                    pc_fsc_n.ppn = pdt_ppn_i;
                            state_n = ST_PROC;
                        end
                    end

                    default: ;
                endcase

                if (flush_i) state_n = ST_IDLE;
            end

            // ─────────────────────────────────────────────────────────
            // ST_PROC: 検査と次動作決定
            // ─────────────────────────────────────────────────────────
            ST_PROC: begin
                case (phase_q)

                    PH_NL_S1: begin
                        if (!nl_pending_q.v) begin
                            cause_n = rv_iommu::PDT_ENTRY_INVALID;
                            state_n = ST_ERROR;
                        end
                        else if ((|nl_pending_q.reserved_1) ||
                                 (|nl_pending_q.reserved_2)) begin
                            cause_n = rv_iommu::PDT_ENTRY_MISCONFIGURED;
                            state_n = ST_ERROR;
                        end
                        else if (en_stage2_i) begin
                            // nested: nl.ppn を S2 翻訳依頼
                            pdt_gppn_n = nl_pending_q.ppn[riscv::GPPNW-1:0];
                            phase_n    = PH_NL_S2;
                            state_n    = ST_ISSUE;
                        end
                        else begin
                            // direct: nl.ppn を SPA として使用
                            cdw_pptr_n  = next_pptr(nl_pending_q.ppn, cdw_lvl_q, process_id_q);
                            cdw_lvl_n   = (cdw_lvl_q == LVL3) ? LVL2 : LVL1;
                            phase_n     = (cdw_lvl_q == LVL2) ? PH_LEAF_S1 : PH_NL_S1;
                            entry_cnt_n = '0;
                            state_n     = ST_ISSUE;
                        end
                    end

                    PH_NL_S2: begin
                        // pdt_spa_q = 翻訳済 SPA
                        cdw_pptr_n  = next_pptr(pdt_spa_q, cdw_lvl_q, process_id_q);
                        cdw_lvl_n   = (cdw_lvl_q == LVL3) ? LVL2 : LVL1;
                        phase_n     = (cdw_lvl_q == LVL2) ? PH_LEAF_S1 : PH_NL_S1;
                        entry_cnt_n = '0;
                        state_n     = ST_ISSUE;
                    end

                    PH_LEAF_S1: begin
                        // pc_ta_q, pc_fsc_q 確定済
                        if (!pc_ta_q.v) begin
                            cause_n = rv_iommu::PDT_ENTRY_INVALID;
                            state_n = ST_ERROR;
                        end
                        else if ((|pc_ta_q.reserved_1) || (|pc_ta_q.reserved_2)) begin
                            cause_n = rv_iommu::PDT_ENTRY_MISCONFIGURED;
                            state_n = ST_ERROR;
                        end
                        // sv39 only: accept fsc.mode in {0 (BARE), 8 (Sv39)}
                        else if ((|pc_fsc_q.reserved) ||
                                 !(pc_fsc_q.mode inside {4'd0, 4'd8})) begin
                            cause_n = rv_iommu::PDT_ENTRY_MISCONFIGURED;
                            state_n = ST_ERROR;
                        end
                        else if (need_leaf_s2) begin
                            pdt_gppn_n = pc_fsc_q.ppn[riscv::GPPNW-1:0];
                            phase_n    = PH_LEAF_S2;
                            state_n    = ST_ISSUE;
                        end
                        else begin
                            // commit pulse → IDLE
                            update_pc_o = 1'b1;
                            state_n     = ST_IDLE;
                        end
                    end

                    PH_LEAF_S2: begin
                        // pc_fsc_q.ppn 既に翻訳済 (= WAIT で _n に書いて _q 確定)
                        update_pc_o = 1'b1;
                        state_n     = ST_IDLE;
                    end

                    default: state_n = ST_IDLE;
                endcase
            end

            // ─────────────────────────────────────────────────────────
            // ST_ERROR: drain + error pulse
            // ─────────────────────────────────────────────────────────
            ST_ERROR: begin
                cause_code_o = cause_q;
                if (wait_rlast_q) begin
                    mem_req_o.r_ready = 1'b1;
                    if (mem_resp_i.r_valid && mem_resp_i.r.last) begin
                        error_o = 1'b1;
                        state_n = ST_IDLE;
                    end
                end
                else begin
                    error_o = 1'b1;
                    state_n = ST_IDLE;
                end
            end

            default: state_n = ST_IDLE;
        endcase
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            state_q        <= ST_IDLE;
            phase_q        <= PH_NL_S1;
            cdw_lvl_q      <= LVL1;
            cdw_pptr_q     <= '0;
            entry_cnt_q    <= '0;
            device_id_q    <= '0;
            process_id_q   <= '0;
            cause_q        <= '0;
            pc_ta_q        <= '0;
            pc_fsc_q       <= '0;
            nl_pending_q   <= '0;
            pdt_gppn_q     <= '0;
            pdt_spa_q      <= '0;
            wait_rlast_q   <= 1'b0;
            edge_trigger_q <= 1'b0;
        end else begin
            state_q        <= state_n;
            phase_q        <= phase_n;
            cdw_lvl_q      <= cdw_lvl_n;
            cdw_pptr_q     <= cdw_pptr_n;
            entry_cnt_q    <= entry_cnt_n;
            device_id_q    <= device_id_n;
            process_id_q   <= process_id_n;
            cause_q        <= cause_n;
            pc_ta_q        <= pc_ta_n;
            pc_fsc_q       <= pc_fsc_n;
            nl_pending_q   <= nl_pending_n;
            pdt_gppn_q     <= pdt_gppn_n;
            pdt_spa_q      <= pdt_spa_n;
            wait_rlast_q   <= wait_rlast_n;
            edge_trigger_q <= edge_trigger_n;
        end
    end

endmodule
