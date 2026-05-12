// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (PR-cdw-split v4: PROC state added)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: Device Directory Table Walker (DDTW), v4
//
//   v4 changes:
//     - ST_PROC state を追加
//     - sv39/sv39x4 限定
//     - DDT 非リーフは S2 翻訳不要 (= PH_NL_S2 なし), leaf の dc.fsc.PPN だけ S2

module rv_iommu_ddtw
    import rv_iommu::*;
#(
    parameter rv_iommu::msi_trans_t MSITrans    = rv_iommu::MSI_DISABLED,
    parameter type axi_req_t                    = logic,
    parameter type axi_rsp_t                    = logic,
    parameter int  DC_WIDTH                     = -1,
    parameter logic [7:0] ar_len_dc             = ((MSITrans != rv_iommu::MSI_DISABLED) ? 8'd6 : 8'd3)
) (
    input  logic                                clk_i,
    input  logic                                rst_ni,

    output logic                                active_o,
    output logic                                error_o,
    output logic [rv_iommu::CAUSE_LEN-1:0]      cause_code_o,

    input  logic        caps_ats_i,
    input  logic        caps_t2gpa_i,
    input  logic        caps_pd20_i, caps_pd17_i, caps_pd8_i,
    input  logic        caps_sv39_i,
    input  logic        caps_sv39x4_i,
    input  logic        caps_msi_flat_i,
    input  logic        caps_amo_hwad_i,
    input  logic        caps_end_i, fctl_be_i,

    input  axi_rsp_t                            mem_resp_i,
    output axi_req_t                            mem_req_o,

    output logic                                update_dc_o,
    output logic [23:0]                         up_did_o,
    output logic [DC_WIDTH-1:0]                 up_dc_content_o,

    input  logic [23:0]                         req_did_i,
    input  logic                                init_i,

    input  logic [riscv::PPNW-1:0]              ddtp_ppn_i,
    input  logic [3:0]                          ddtp_mode_i,

    input  logic                                en_stage2_i,
    input  logic                                ptw_done_i,
    input  logic                                flush_i,
    input  logic [riscv::PPNW-1:0]              pdt_ppn_i,
    output logic                                cdw_implicit_access_o,
    output logic [riscv::GPPNW-1:0]             pdt_gppn_o,
    output logic [riscv::PPNW-1:0]              iohgatp_ppn_fw_o
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

    // ── Phases (= PH_NL_S2 なし) ────────────────────────────────────
    typedef enum logic [1:0] {
        PH_NL_S1,
        PH_LEAF_S1,
        PH_LEAF_S2
    } phase_t;
    phase_t phase_q, phase_n;

    typedef enum logic [2:0] {
        OFF, BARE, LVL1, LVL2, LVL3
    } level_t;
    level_t cdw_lvl_q, cdw_lvl_n;

    logic [riscv::PLEN-1:0]                     cdw_pptr_q, cdw_pptr_n;
    logic [23:0]                                device_id_q, device_id_n;

    rv_iommu::tc_t                              dc_tc_q,      dc_tc_n;
    rv_iommu::iohgatp_t                         dc_iohgatp_q, dc_iohgatp_n;
    rv_iommu::dc_ta_t                           dc_ta_q,      dc_ta_n;
    rv_iommu::fsc_t                             dc_fsc_q,     dc_fsc_n;

    rv_iommu::nl_entry_t                        nl_pending_q, nl_pending_n;

    logic [2:0]                                 entry_cnt_q, entry_cnt_n;
    logic                                       dc_fully_loaded;

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

    rv_iommu::tc_t          dc_tc_view;
    rv_iommu::iohgatp_t     dc_iohgatp_view;
    rv_iommu::dc_ta_t       dc_ta_view;
    rv_iommu::fsc_t         dc_fsc_view;
    rv_iommu::nl_entry_t    nl_view;
    assign dc_tc_view      = rv_iommu::tc_t'(mem_resp_i.r.data);
    assign dc_iohgatp_view = rv_iommu::iohgatp_t'(mem_resp_i.r.data);
    assign dc_ta_view      = rv_iommu::dc_ta_t'(mem_resp_i.r.data);
    assign dc_fsc_view     = rv_iommu::fsc_t'(mem_resp_i.r.data);
    assign nl_view         = rv_iommu::nl_entry_t'(mem_resp_i.r.data);

    assign active_o        = (state_q != ST_IDLE);
    assign dc_fully_loaded = (MSITrans != rv_iommu::MSI_DISABLED)
                             ? (entry_cnt_q == 3'b111) : (entry_cnt_q == 3'b100);
    assign up_did_o        = device_id_q;

    logic need_leaf_s2;
    assign need_leaf_s2 = en_stage2_i && dc_tc_q.pdtv && (dc_iohgatp_q.mode != 4'b0000);

    function automatic logic [riscv::PLEN-1:0] next_pptr_nl(
        input logic [riscv::PPNW-1:0] base_ppn,
        input level_t                 curr_lvl,
        input logic [23:0]            did
    );
        case (curr_lvl)
            LVL3:    return {base_ppn,
                             (MSITrans == rv_iommu::MSI_DISABLED) ? did[15:7] : did[14:6],
                             3'b0};
            LVL2:    return {base_ppn,
                             (MSITrans == rv_iommu::MSI_DISABLED) ? {did[6:0], 5'b0} : {did[5:0], 6'b0}};
            default: return '0;
        endcase
    endfunction

    // ── MSI generate (= 既存のまま) ─────────────────────────────────
    logic en_msi_check, translate_pdtp, msi_check_error;
    generate
    if (MSITrans != rv_iommu::MSI_DISABLED) begin : gen_ddtw_msi
        rv_iommu::msiptp_t              dc_msiptp_q, dc_msiptp_n;
        rv_iommu::msi_addr_mask_t       dc_msi_mask_q, dc_msi_mask_n;
        rv_iommu::msi_addr_pattern_t    dc_msi_patt_q, dc_msi_patt_n;
        rv_iommu::dc_ext_t              up_dc_ext;
        rv_iommu::msiptp_t              dc_msiptp_view;
        rv_iommu::msi_addr_mask_t       dc_mask_view;
        rv_iommu::msi_addr_pattern_t    dc_patt_view;

        assign dc_msiptp_view = rv_iommu::msiptp_t'(mem_resp_i.r.data);
        assign dc_mask_view   = rv_iommu::msi_addr_mask_t'(mem_resp_i.r.data);
        assign dc_patt_view   = rv_iommu::msi_addr_pattern_t'(mem_resp_i.r.data);

        always_comb begin
            msi_check_error    = 1'b0;
            translate_pdtp     = 1'b0;
            dc_msiptp_n        = dc_msiptp_q;
            dc_msi_mask_n      = dc_msi_mask_q;
            dc_msi_patt_n      = dc_msi_patt_q;

            up_dc_ext.tc               = dc_tc_q;
            up_dc_ext.iohgatp          = dc_iohgatp_q;
            up_dc_ext.ta               = dc_ta_q;
            up_dc_ext.fsc              = dc_fsc_q;
            up_dc_ext.msi_addr_pattern = dc_msi_patt_q;
            up_dc_ext.msi_addr_mask    = dc_msi_mask_q;
            up_dc_ext.msiptp           = dc_msiptp_q;
            up_dc_ext.reserved         = '0;
            up_dc_content_o            = up_dc_ext;

            if (en_msi_check) begin
                case (entry_cnt_q)
                    3'b100: begin
                        dc_msiptp_n = dc_msiptp_view;
                        if ((caps_msi_flat_i && |(dc_msiptp_view.mode & 4'b1110)) ||
                            (|dc_msiptp_view.reserved)) msi_check_error = 1'b1;
                    end
                    3'b101: begin
                        dc_msi_mask_n = dc_mask_view;
                        if (|dc_mask_view.reserved) msi_check_error = 1'b1;
                    end
                    3'b110: begin
                        dc_msi_patt_n = dc_patt_view;
                        if (en_stage2_i && dc_tc_q.pdtv) translate_pdtp = 1'b1;
                        if (|dc_patt_view.reserved) msi_check_error = 1'b1;
                    end
                    default: ;
                endcase
            end
        end

        always_ff @(posedge clk_i or negedge rst_ni) begin
            if (~rst_ni) begin
                dc_msiptp_q   <= '0;
                dc_msi_mask_q <= '0;
                dc_msi_patt_q <= '0;
            end else begin
                dc_msiptp_q   <= dc_msiptp_n;
                dc_msi_mask_q <= dc_msi_mask_n;
                dc_msi_patt_q <= dc_msi_patt_n;
            end
        end
    end : gen_ddtw_msi
    else begin : gen_ddtw_no_msi
        rv_iommu::dc_base_t up_dc_base;
        assign up_dc_base.tc      = dc_tc_q;
        assign up_dc_base.iohgatp = dc_iohgatp_q;
        assign up_dc_base.ta      = dc_ta_q;
        assign up_dc_base.fsc     = dc_fsc_q;
        assign up_dc_content_o    = up_dc_base;
        assign msi_check_error    = 1'b0;
        assign translate_pdtp     = 1'b0;
    end : gen_ddtw_no_msi
    endgenerate

    // ──────────────────────────────────────────────────────────────────
    // Main FSM
    // ──────────────────────────────────────────────────────────────────
    always_comb begin : ddtw_fsm
        state_n      = state_q;
        phase_n      = phase_q;
        cdw_lvl_n    = cdw_lvl_q;
        cdw_pptr_n   = cdw_pptr_q;
        device_id_n  = device_id_q;
        entry_cnt_n  = entry_cnt_q;
        dc_tc_n      = dc_tc_q;
        dc_iohgatp_n = dc_iohgatp_q;
        dc_ta_n      = dc_ta_q;
        dc_fsc_n     = dc_fsc_q;
        nl_pending_n = nl_pending_q;
        cause_n      = cause_q;
        wait_rlast_n = wait_rlast_q;

        en_msi_check          = 1'b0;
        error_o               = 1'b0;
        cause_code_o          = '0;
        update_dc_o           = 1'b0;
        cdw_implicit_access_o = 1'b0;
        pdt_gppn_o            = '0;
        iohgatp_ppn_fw_o      = '0;

        mem_req_o          = '0;
        mem_req_o.ar.id    = 4'b0001;
        mem_req_o.ar.addr  = {{riscv::XLEN-riscv::PLEN{1'b0}}, cdw_pptr_q};
        mem_req_o.ar.len   = (phase_q == PH_LEAF_S1) ? ar_len_dc : 8'd0;
        mem_req_o.ar.size  = 3'b011;
        mem_req_o.ar.burst = axi_pkg::BURST_INCR;
        mem_req_o.ar_valid = 1'b0;
        mem_req_o.r_ready  = 1'b0;

        case (state_q)

            ST_IDLE: begin
                cdw_lvl_n    = level_t'(ddtp_mode_i);
                device_id_n  = req_did_i;
                entry_cnt_n  = '0;
                wait_rlast_n = 1'b0;

                if (init_rising_edge) begin
                    state_n = ST_ISSUE;
                    phase_n = (ddtp_mode_i == 4'b0010) ? PH_LEAF_S1 : PH_NL_S1;

                    if (ddtp_mode_i == 4'b0100)
                        cdw_pptr_n = {ddtp_ppn_i,
                                      ((MSITrans == rv_iommu::MSI_DISABLED) ? {1'b0, req_did_i[23:16]} : req_did_i[23:15]),
                                      3'b0};
                    else if (ddtp_mode_i == 4'b0011)
                        cdw_pptr_n = {ddtp_ppn_i,
                                      ((MSITrans == rv_iommu::MSI_DISABLED) ? req_did_i[15:7] : req_did_i[14:6]),
                                      3'b0};
                    else if (ddtp_mode_i == 4'b0010)
                        cdw_pptr_n = {ddtp_ppn_i,
                                      (MSITrans == rv_iommu::MSI_DISABLED) ? {req_did_i[6:0], 5'b0} : {req_did_i[5:0], 6'b0}};
                end
            end

            ST_ISSUE: begin
                case (phase_q)
                    PH_NL_S1, PH_LEAF_S1: begin
                        mem_req_o.ar_valid = 1'b1;
                        if (mem_resp_i.ar_ready) state_n = ST_WAIT;
                    end
                    PH_LEAF_S2: begin
                        pdt_gppn_o            = dc_fsc_q.ppn[riscv::GPPNW-1:0];
                        iohgatp_ppn_fw_o      = dc_iohgatp_q.ppn;
                        cdw_implicit_access_o = 1'b1;
                        state_n               = ST_WAIT;
                    end
                    default: state_n = ST_IDLE;
                endcase
            end

            ST_WAIT: begin
                case (phase_q)

                    PH_NL_S1: begin
                        if (mem_resp_i.r_valid) begin
                            mem_req_o.r_ready = 1'b1;
                            if (mem_resp_i.r.resp != axi_pkg::RESP_OKAY) begin
                                cause_n      = rv_iommu::DDT_DATA_CORRUPTION;
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
                                cause_n      = rv_iommu::DDT_DATA_CORRUPTION;
                                wait_rlast_n = ~mem_resp_i.r.last;
                                state_n      = ST_ERROR;
                            end
                            else begin
                                entry_cnt_n  = entry_cnt_q + 1;
                                en_msi_check = 1'b1;
                                case (entry_cnt_q)
                                    3'b000: dc_tc_n      = dc_tc_view;
                                    3'b001: dc_iohgatp_n = dc_iohgatp_view;
                                    3'b010: dc_ta_n      = dc_ta_view;
                                    3'b011: dc_fsc_n     = dc_fsc_view;
                                    default: ;
                                endcase
                                if (mem_resp_i.r.last) state_n = ST_PROC;
                            end
                        end
                    end

                    PH_LEAF_S2: begin
                        if (ptw_done_i) begin
                            dc_fsc_n.ppn = pdt_ppn_i;
                            state_n      = ST_PROC;
                        end
                    end

                    default: ;
                endcase

                if (flush_i) state_n = ST_IDLE;
            end

            ST_PROC: begin
                case (phase_q)

                    PH_NL_S1: begin
                        if (!nl_pending_q.v) begin
                            cause_n = rv_iommu::DDT_ENTRY_INVALID;
                            state_n = ST_ERROR;
                        end
                        else if ((|nl_pending_q.reserved_1) || (|nl_pending_q.reserved_2)) begin
                            cause_n = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                            state_n = ST_ERROR;
                        end
                        else begin
                            cdw_pptr_n  = next_pptr_nl(nl_pending_q.ppn, cdw_lvl_q, device_id_q);
                            cdw_lvl_n   = (cdw_lvl_q == LVL3) ? LVL2 : LVL1;
                            phase_n     = (cdw_lvl_q == LVL2) ? PH_LEAF_S1 : PH_NL_S1;
                            entry_cnt_n = '0;
                            state_n     = ST_ISSUE;
                        end
                    end

                    PH_LEAF_S1: begin
                        // 検査群 (= 元 LEAF state の case ベース検査を統合)
                        // dc.tc
                        if (!dc_tc_q.v) begin
                            cause_n = rv_iommu::DDT_ENTRY_INVALID;
                            state_n = ST_ERROR;
                        end
                        else if ((|dc_tc_q.reserved_1) || (|dc_tc_q.reserved_2) ||
                                 (!caps_ats_i && (dc_tc_q.en_ats || dc_tc_q.en_pri || dc_tc_q.prpr)) ||
                                 (!dc_tc_q.en_ats && (dc_tc_q.t2gpa || dc_tc_q.en_pri)) ||
                                 (!dc_tc_q.en_pri && dc_tc_q.prpr) ||
                                 (!dc_tc_q.pdtv && dc_tc_q.dpe) ||
                                 (!caps_amo_hwad_i && (dc_tc_q.sade || dc_tc_q.gade)) ||
                                 (fctl_be_i != dc_tc_q.sbe) ||
                                 (dc_tc_q.sxl != 1'b0)) begin
                            cause_n = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                            state_n = ST_ERROR;
                        end
                        // dc.iohgatp (sv39x4 only)
                        else if ((dc_tc_q.t2gpa && !(|dc_iohgatp_q.mode)) ||
                                 !(dc_iohgatp_q.mode inside {4'd0, 4'd8}) ||
                                 (!caps_sv39x4_i && dc_iohgatp_q.mode == 4'd8) ||
                                 (|dc_iohgatp_q.mode && |dc_iohgatp_q.ppn[1:0])) begin
                            cause_n = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                            state_n = ST_ERROR;
                        end
                        // dc.ta
                        else if ((|dc_ta_q.reserved_1) || (|dc_ta_q.reserved_2)) begin
                            cause_n = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                            state_n = ST_ERROR;
                        end
                        // dc.fsc (sv39 only for non-pdtv, PD8/17/20 for pdtv)
                        else if ((dc_tc_q.pdtv && ((dc_fsc_q.mode inside {[4:15]}) ||
                                                    (!caps_pd20_i && dc_fsc_q.mode == 4'b0011) ||
                                                    (!caps_pd17_i && dc_fsc_q.mode == 4'b0010) ||
                                                    (!caps_pd8_i  && dc_fsc_q.mode == 4'b0001))) ||
                                 (!dc_tc_q.pdtv && (!(dc_fsc_q.mode inside {4'd0, 4'd8}) ||
                                                     (!caps_sv39_i && dc_fsc_q.mode == 4'd8))) ||
                                 (|dc_fsc_q.reserved)) begin
                            cause_n = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                            state_n = ST_ERROR;
                        end
                        // MSI 検査エラー (translate_pdtp は generate 内で算定済)
                        else if (msi_check_error) begin
                            cause_n = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                            state_n = ST_ERROR;
                        end
                        // pdtp.PPN を S2 翻訳する必要があるか
                        else if (need_leaf_s2) begin
                            phase_n = PH_LEAF_S2;
                            state_n = ST_ISSUE;
                        end
                        // 直接 commit
                        else begin
                            update_dc_o = 1'b1;
                            state_n     = ST_IDLE;
                        end
                    end

                    PH_LEAF_S2: begin
                        update_dc_o = 1'b1;
                        state_n     = ST_IDLE;
                    end

                    default: state_n = ST_IDLE;
                endcase
            end

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
            cause_q        <= '0;
            dc_tc_q        <= '0;
            dc_iohgatp_q   <= '0;
            dc_ta_q        <= '0;
            dc_fsc_q       <= '0;
            nl_pending_q   <= '0;
            wait_rlast_q   <= 1'b0;
            edge_trigger_q <= 1'b0;
        end else begin
            state_q        <= state_n;
            phase_q        <= phase_n;
            cdw_lvl_q      <= cdw_lvl_n;
            cdw_pptr_q     <= cdw_pptr_n;
            entry_cnt_q    <= entry_cnt_n;
            device_id_q    <= device_id_n;
            cause_q        <= cause_n;
            dc_tc_q        <= dc_tc_n;
            dc_iohgatp_q   <= dc_iohgatp_n;
            dc_ta_q        <= dc_ta_n;
            dc_fsc_q       <= dc_fsc_n;
            nl_pending_q   <= nl_pending_n;
            wait_rlast_q   <= wait_rlast_n;
            edge_trigger_q <= edge_trigger_n;
        end
    end

endmodule
