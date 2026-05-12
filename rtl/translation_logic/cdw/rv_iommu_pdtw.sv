// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (PR-cdw-split: PDTW = PC walker のみ)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: Process Directory Table Walker (PDTW)
//              - 旧 rv_iommu_cdw_pc.sv から PC walk 部分だけを切り出した module
//              - PDT を walk して PC を fetch、 PDTC を update
//              - S2 enabled の場合、 各 non-leaf PDT entry の PPN を PTW で
//                S2 翻訳してから次レベル pptr に使う
//              - AXI master を 1 本所有 (= 外部の cdw_axi_mux で DDTW と共有)
//              - PC は常に 16-byte (2 DW)、 非 leaf は 8-byte (1 DW)

module rv_iommu_pdtw
    import rv_iommu::*;
#(
    parameter type axi_req_t                    = logic,
    parameter type axi_rsp_t                    = logic
) (
    input  logic                                clk_i,
    input  logic                                rst_ni,

    // Status / Error
    output logic                                active_o,
    output logic                                error_o,
    output logic [rv_iommu::CAUSE_LEN-1:0]      cause_code_o,

    // ── PC config checks ─────────────────────────────────────────────
    input  logic                                dc_sxl_i,
    input  logic                                caps_sv32_i, caps_sv39_i, caps_sv48_i, caps_sv57_i,

    // ── AXI master ───────────────────────────────────────────────────
    input  axi_rsp_t                            mem_resp_i,
    output axi_req_t                            mem_req_o,

    // ── Update PDTC ──────────────────────────────────────────────────
    output logic                                update_pc_o,
    output logic [23:0]                         up_did_o,
    output logic [19:0]                         up_pid_o,
    output rv_iommu::pc_t                       up_pc_content_o,

    // ── Trigger (PDTC miss) ──────────────────────────────────────────
    input  logic [23:0]                         req_did_i,
    input  logic [19:0]                         req_pid_i,
    input  logic                                init_i,

    // ── From DC (in DDTC) ────────────────────────────────────────────
    input  logic                                en_stage2_i,
    input  logic [riscv::PPNW-1:0]              pdtp_ppn_i,           // = DC.fsc.PPN
    input  logic [3:0]                          pdtp_mode_i,           // = DC.fsc.MODE

    // ── PTW implicit S2 translation for non-leaf PDT entries ─────────
    input  logic                                ptw_done_i,
    input  logic                                flush_i,
    input  logic [riscv::PPNW-1:0]              pdt_ppn_i,
    output logic                                cdw_implicit_access_o,
    output logic [riscv::GPPNW-1:0]             pdt_gppn_o
);

    // ── States (旧 CDW と同じ構成) ───────────────────────────────────
    typedef enum logic [2:0] {
        IDLE,
        MEM_ACCESS,
        NON_LEAF,
        LEAF,
        GUEST_TR,
        ERROR_S
    } state_t;
    state_t state_q, state_n;

    typedef enum logic [2:0] {
        OFF, BARE, LVL1, LVL2, LVL3
    } level_t;
    level_t cdw_lvl_q, cdw_lvl_n;

    logic [riscv::PLEN-1:0]                     cdw_pptr_q, cdw_pptr_n;
    logic [23:0]                                device_id_q, device_id_n;
    logic [19:0]                                process_id_q, process_id_n;

    // PC capture registers
    rv_iommu::pc_ta_t                           pc_ta_q,  pc_ta_n;
    rv_iommu::fsc_t                             pc_fsc_q, pc_fsc_n;

    logic                                       is_last_cdw_lvl;
    logic [2:0]                                 entry_cnt_q, entry_cnt_n;
    logic                                       pc_fully_loaded;

    logic [rv_iommu::CAUSE_LEN-1:0]             cause_q,      cause_n;
    logic                                       wait_rlast_q, wait_rlast_n;

    // ── Casts ────────────────────────────────────────────────────────
    rv_iommu::pc_ta_t       pc_ta_view;
    rv_iommu::fsc_t         pc_fsc_view;
    rv_iommu::nl_entry_t    nl_view;
    assign pc_ta_view  = rv_iommu::pc_ta_t'(mem_resp_i.r.data);
    assign pc_fsc_view = rv_iommu::fsc_t'(mem_resp_i.r.data);
    assign nl_view     = rv_iommu::nl_entry_t'(mem_resp_i.r.data);

    // ── Status outputs ───────────────────────────────────────────────
    assign active_o        = (state_q != IDLE);
    assign is_last_cdw_lvl = (cdw_lvl_q == LVL1);
    assign pc_fully_loaded = (entry_cnt_q == 3'b010);
    assign up_did_o        = device_id_q;
    assign up_pid_o        = process_id_q;
    assign up_pc_content_o.ta  = pc_ta_q;
    assign up_pc_content_o.fsc = pc_fsc_q;

    // ── Main FSM ─────────────────────────────────────────────────────
    always_comb begin : pdtw_fsm

        // Defaults
        cdw_lvl_n             = cdw_lvl_q;
        cdw_pptr_n            = cdw_pptr_q;
        state_n               = state_q;
        entry_cnt_n           = entry_cnt_q;
        device_id_n           = device_id_q;
        process_id_n          = process_id_q;
        cause_n               = cause_q;
        wait_rlast_n          = wait_rlast_q;
        pc_ta_n               = pc_ta_q;
        pc_fsc_n              = pc_fsc_q;

        error_o               = 1'b0;
        cause_code_o          = '0;
        update_pc_o           = 1'b0;
        cdw_implicit_access_o = 1'b0;
        pdt_gppn_o            = '0;

        // AXI defaults
        mem_req_o.aw          = '0;
        mem_req_o.aw_valid    = 1'b0;
        mem_req_o.w           = '0;
        mem_req_o.w_valid     = 1'b0;
        mem_req_o.b_ready     = 1'b0;
        mem_req_o.ar.id       = 4'b0010;        // DDTW と区別するため id=2
        mem_req_o.ar.addr     = {{riscv::XLEN-riscv::PLEN{1'b0}}, cdw_pptr_q};
        mem_req_o.ar.len      = (is_last_cdw_lvl) ? 8'd1 : 8'd0;  // PC=2 beats, NL=1 beat
        mem_req_o.ar.size     = 3'b011;
        mem_req_o.ar.burst    = axi_pkg::BURST_INCR;
        mem_req_o.ar.lock     = '0;
        mem_req_o.ar.cache    = '0;
        mem_req_o.ar.prot     = '0;
        mem_req_o.ar.qos      = '0;
        mem_req_o.ar.region   = '0;
        mem_req_o.ar.user     = '0;
        mem_req_o.ar_valid    = 1'b0;
        mem_req_o.r_ready     = 1'b0;

        case (state_q)
            // ─────────────────────────────────────────────────────────
            IDLE: begin
                device_id_n  = req_did_i;
                entry_cnt_n  = '0;
                wait_rlast_n = 1'b0;

                if (init_i) begin
                    process_id_n = req_pid_i;
                    state_n      = MEM_ACCESS;
                    cdw_lvl_n    = level_t'(pdtp_mode_i + 4'd1);  // PDT mode 別 encoding

                    // pdtp.MODE: 1=PD8 → LVL1, 2=PD17 → LVL2, 3=PD20 → LVL3
                    if (pdtp_mode_i == 4'b0011)            // PD20
                        cdw_pptr_n = {pdtp_ppn_i, 6'b0, req_pid_i[19:17], 3'b0};
                    else if (pdtp_mode_i == 4'b0010)       // PD17
                        cdw_pptr_n = {pdtp_ppn_i, req_pid_i[16:8], 3'b0};
                    else if (pdtp_mode_i == 4'b0001)       // PD8
                        cdw_pptr_n = {pdtp_ppn_i, req_pid_i[7:0], 4'b0};
                end
            end

            // ─────────────────────────────────────────────────────────
            MEM_ACCESS: begin
                mem_req_o.ar_valid = 1'b1;
                if (mem_resp_i.ar_ready) begin
                    // S2 enabled で non-leaf なら nl.PPN を翻訳要 (GUEST_TR)
                    // それ以外 (last lvl = LEAF、 または S2 disabled の non-leaf) は直接
                    if (en_stage2_i && !is_last_cdw_lvl) state_n = GUEST_TR;
                    else if (is_last_cdw_lvl)            state_n = LEAF;
                    else                                  state_n = NON_LEAF;
                end
            end

            // ─────────────────────────────────────────────────────────
            // NON_LEAF: 受け取った nl entry を解釈、 次の pptr を計算
            //   - S2 enabled で来た場合は、 GUEST_TR で nl.ppn が翻訳済み
            //   - そうでなければ nl.ppn を直接使う
            // ─────────────────────────────────────────────────────────
            NON_LEAF: begin
                if (mem_resp_i.r_valid || ptw_done_i || flush_i) begin
                    if (mem_resp_i.r_valid) mem_req_o.r_ready = 1'b1;

                    if (!nl_view.v && mem_resp_i.r_valid) begin
                        state_n = ERROR_S;
                        cause_n = rv_iommu::PDT_ENTRY_INVALID;
                    end
                    else if (mem_resp_i.r_valid && ((|nl_view.reserved_1) || (|nl_view.reserved_2))) begin
                        state_n = ERROR_S;
                        cause_n = rv_iommu::PDT_ENTRY_MISCONFIGURED;
                    end
                    else begin
                        case (cdw_lvl_q)
                            LVL3: begin
                                cdw_lvl_n  = LVL2;
                                if (!en_stage2_i) cdw_pptr_n = {nl_view.ppn, process_id_q[16:8], 3'b0};
                                else              cdw_pptr_n = {pdt_ppn_i,  process_id_q[16:8], 3'b0};
                            end
                            LVL2: begin
                                cdw_lvl_n  = LVL1;
                                if (!en_stage2_i) cdw_pptr_n = {nl_view.ppn, process_id_q[7:0], 4'b0};
                                else              cdw_pptr_n = {pdt_ppn_i,  process_id_q[7:0], 4'b0};
                            end
                            default: ;
                        endcase
                        state_n = MEM_ACCESS;
                    end

                    if (flush_i) state_n = IDLE;
                end
            end

            // ─────────────────────────────────────────────────────────
            // LEAF: PC の 2 DW を fetch して PDTC update
            // ─────────────────────────────────────────────────────────
            LEAF: begin
                if (pc_fully_loaded) begin
                    state_n     = IDLE;
                    update_pc_o = 1'b1;
                end
                else if (mem_resp_i.r_valid) begin
                    mem_req_o.r_ready = 1'b1;
                    entry_cnt_n       = entry_cnt_q + 1;

                    case (entry_cnt_q)
                        3'b000: begin   // PC.ta
                            pc_ta_n = pc_ta_view;
                            if (!pc_ta_view.v) begin
                                state_n      = ERROR_S;
                                cause_n      = rv_iommu::PDT_ENTRY_INVALID;
                                wait_rlast_n = 1'b1;
                            end
                            if ((|pc_ta_view.reserved_1) || (|pc_ta_view.reserved_2)) begin
                                state_n      = ERROR_S;
                                cause_n      = rv_iommu::PDT_ENTRY_MISCONFIGURED;
                                wait_rlast_n = 1'b1;
                            end
                        end
                        3'b001: begin   // PC.fsc (last DW)
                            pc_fsc_n = pc_fsc_view;
                            if ((|pc_fsc_view.reserved) ||
                                (!(pc_fsc_view.mode inside {4'd0, 4'd8, 4'd9, 4'd10})) ||
                                (!dc_sxl_i && ((!caps_sv39_i && pc_fsc_view.mode == 4'd8) ||
                                               (!caps_sv48_i && pc_fsc_view.mode == 4'd9) ||
                                               (!caps_sv57_i && pc_fsc_view.mode == 4'd10))) ||
                                ( dc_sxl_i && (!caps_sv32_i && pc_fsc_view.mode == 4'd8))) begin
                                state_n = ERROR_S;
                                cause_n = rv_iommu::PDT_ENTRY_MISCONFIGURED;
                            end
                        end
                        default: ;
                    endcase
                end

                if (flush_i) state_n = IDLE;
            end

            // ─────────────────────────────────────────────────────────
            // GUEST_TR: 非 leaf PDT entry の PPN を PTW で S2 翻訳依頼
            // ─────────────────────────────────────────────────────────
            GUEST_TR: begin
                if (mem_resp_i.r_valid) begin
                    mem_req_o.r_ready = 1'b1;
                    if (!nl_view.v) begin
                        state_n = ERROR_S;
                        cause_n = rv_iommu::PDT_ENTRY_INVALID;
                    end
                    else if ((|nl_view.reserved_1) || (|nl_view.reserved_2)) begin
                        state_n = ERROR_S;
                        cause_n = rv_iommu::PDT_ENTRY_MISCONFIGURED;
                    end
                    else begin
                        pdt_gppn_o            = nl_view.ppn[riscv::GPPNW-1:0];
                        cdw_implicit_access_o = 1'b1;
                        state_n               = NON_LEAF;   // PTW 完了を待つ
                    end
                end
            end

            // ─────────────────────────────────────────────────────────
            ERROR_S: begin
                mem_req_o.r_ready = 1'b1;
                cause_code_o      = cause_q;
                if ((wait_rlast_q && mem_resp_i.r.last) || !wait_rlast_q) begin
                    error_o = 1'b1;
                    state_n = IDLE;
                end
            end

            default: state_n = IDLE;
        endcase

        // AXI transmission error
        if (mem_resp_i.r_valid && mem_resp_i.r.resp != axi_pkg::RESP_OKAY) begin
            update_pc_o  = 1'b0;
            wait_rlast_n = ~mem_resp_i.r.last;
            cause_n      = rv_iommu::PDT_DATA_CORRUPTION;
            state_n      = ERROR_S;
        end
    end

    // ── Sequential ───────────────────────────────────────────────────
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            state_q       <= IDLE;
            cdw_lvl_q     <= LVL1;
            cdw_pptr_q    <= '0;
            entry_cnt_q   <= '0;
            device_id_q   <= '0;
            process_id_q  <= '0;
            cause_q       <= '0;
            pc_ta_q       <= '0;
            pc_fsc_q      <= '0;
            wait_rlast_q  <= 1'b0;
        end else begin
            state_q       <= state_n;
            cdw_pptr_q    <= cdw_pptr_n;
            cdw_lvl_q     <= cdw_lvl_n;
            entry_cnt_q   <= entry_cnt_n;
            device_id_q   <= device_id_n;
            process_id_q  <= process_id_n;
            cause_q       <= cause_n;
            pc_ta_q       <= pc_ta_n;
            pc_fsc_q      <= pc_fsc_n;
            wait_rlast_q  <= wait_rlast_n;
        end
    end

endmodule