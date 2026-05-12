// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (PR-cdw-split: DDTW = DC walker のみ)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: Device Directory Table Walker (DDTW)
//              - 旧 rv_iommu_cdw_pc.sv から DC walk 部分だけを切り出した module
//              - DDT を walk して DC を fetch、 DDTC を update
//              - PDTV=1 + S2 enabled の場合、 DC.fsc.PPN (= pdtp.PPN) を
//                PTW 経由で S2 翻訳して SPA に変換して DDTC に格納
//              - AXI master を 1 本所有 (= 外部の cdw_axi_mux で PDTW と共有)

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

    // Status / Error
    output logic                                active_o,
    output logic                                error_o,
    output logic [rv_iommu::CAUSE_LEN-1:0]      cause_code_o,

    // ── DC config checks (capabilities) ──────────────────────────────
    input  logic        caps_ats_i,
    input  logic        caps_t2gpa_i,
    input  logic        caps_pd20_i, caps_pd17_i, caps_pd8_i,
    input  logic        caps_sv32_i, caps_sv39_i, caps_sv48_i, caps_sv57_i,
    input  logic        fctl_gxl_i, caps_sv32x4_i, caps_sv39x4_i, caps_sv48x4_i, caps_sv57x4_i,
    input  logic        caps_msi_flat_i,
    input  logic        caps_amo_hwad_i,
    input  logic        caps_end_i, fctl_be_i,

    // ── AXI master ───────────────────────────────────────────────────
    input  axi_rsp_t                            mem_resp_i,
    output axi_req_t                            mem_req_o,

    // ── Update DDTC ──────────────────────────────────────────────────
    output logic                                update_dc_o,
    output logic [23:0]                         up_did_o,
    output logic [DC_WIDTH-1:0]                 up_dc_content_o,

    // ── Trigger (DDTC miss) ──────────────────────────────────────────
    input  logic [23:0]                         req_did_i,
    input  logic                                init_i,

    // ── From regmap ──────────────────────────────────────────────────
    input  logic [riscv::PPNW-1:0]              ddtp_ppn_i,
    input  logic [3:0]                          ddtp_mode_i,

    // ── PTW implicit S2 translation for pdtp.PPN (DDTW → PTW) ────────
    input  logic                                en_stage2_i,
    input  logic                                ptw_done_i,
    input  logic                                flush_i,
    input  logic [riscv::PPNW-1:0]              pdt_ppn_i,
    output logic                                cdw_implicit_access_o,
    output logic [riscv::GPPNW-1:0]             pdt_gppn_o,
    output logic [riscv::PPNW-1:0]              iohgatp_ppn_fw_o
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

    // DC capture registers
    rv_iommu::tc_t                              dc_tc_q,      dc_tc_n;
    rv_iommu::iohgatp_t                         dc_iohgatp_q, dc_iohgatp_n;
    rv_iommu::dc_ta_t                           dc_ta_q,      dc_ta_n;
    rv_iommu::fsc_t                             dc_fsc_q,     dc_fsc_n;

    logic                                       is_last_cdw_lvl;
    logic [2:0]                                 entry_cnt_q, entry_cnt_n;
    logic                                       dc_fully_loaded;

    logic [rv_iommu::CAUSE_LEN-1:0]             cause_q,      cause_n;
    logic                                       wait_rlast_q, wait_rlast_n;
    logic                                       ptw_done_q;
    logic                                       edge_trigger_q, edge_trigger_n;

    // ── Casts (current memory data → typed views) ───────────────────
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

    // ── Status outputs ───────────────────────────────────────────────
    assign active_o        = (state_q != IDLE);
    assign is_last_cdw_lvl = (cdw_lvl_q == LVL1);
    assign dc_fully_loaded = (MSITrans != rv_iommu::MSI_DISABLED)
                             ? (entry_cnt_q == 3'b111) : (entry_cnt_q == 3'b100);
    assign up_did_o        = device_id_q;

    // ── Edge-triggered init ─────────────────────────────────────────
    always_comb begin : ddtw_init_control
        edge_trigger_n = edge_trigger_q;
        if (!edge_trigger_q && init_i) edge_trigger_n = 1'b1;
        if ( edge_trigger_q && !init_i) edge_trigger_n = 1'b0;
    end

    // ── MSI translation support (= generate 切替) ────────────────────
    logic                                       en_msi_check;
    logic                                       translate_pdtp;
    logic                                       msi_check_error;

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

        always_comb begin : msi_config_checks
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
                    3'b100: begin   // DC.msiptp
                        dc_msiptp_n = dc_msiptp_view;
                        if ((caps_msi_flat_i && |(dc_msiptp_view.mode & 4'b1110)) ||
                            (|dc_msiptp_view.reserved)) msi_check_error = 1'b1;
                    end
                    3'b101: begin   // DC.msi_addr_mask
                        dc_msi_mask_n = dc_mask_view;
                        if (|dc_mask_view.reserved) msi_check_error = 1'b1;
                    end
                    3'b110: begin   // DC.msi_addr_pattern
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

    // ── Main FSM ─────────────────────────────────────────────────────
    always_comb begin : ddtw_fsm

        // Defaults
        en_msi_check          = 1'b0;
        cdw_lvl_n             = cdw_lvl_q;
        cdw_pptr_n            = cdw_pptr_q;
        state_n               = state_q;
        entry_cnt_n           = entry_cnt_q;
        device_id_n           = device_id_q;
        cause_n               = cause_q;
        wait_rlast_n          = wait_rlast_q;
        dc_tc_n               = dc_tc_q;
        dc_iohgatp_n          = dc_iohgatp_q;
        dc_ta_n               = dc_ta_q;
        dc_fsc_n              = dc_fsc_q;

        // Outputs
        error_o               = 1'b0;
        cause_code_o          = '0;
        update_dc_o           = 1'b0;
        cdw_implicit_access_o = 1'b0;
        pdt_gppn_o            = '0;
        iohgatp_ppn_fw_o      = '0;

        // AXI defaults
        mem_req_o.aw          = '0;
        mem_req_o.aw_valid    = 1'b0;
        mem_req_o.w           = '0;
        mem_req_o.w_valid     = 1'b0;
        mem_req_o.b_ready     = 1'b0;
        mem_req_o.ar.id       = 4'b0001;
        mem_req_o.ar.addr     = {{riscv::XLEN-riscv::PLEN{1'b0}}, cdw_pptr_q};
        mem_req_o.ar.len      = (is_last_cdw_lvl) ? ar_len_dc : 8'd0;
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
                cdw_lvl_n    = level_t'(ddtp_mode_i);
                device_id_n  = req_did_i;
                entry_cnt_n  = '0;
                wait_rlast_n = 1'b0;

                if (init_i && !edge_trigger_q) begin
                    state_n = MEM_ACCESS;
                    // ddtp.MODE encoding: 4=3LVL, 3=2LVL, 2=1LVL
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

            // ─────────────────────────────────────────────────────────
            MEM_ACCESS: begin
                mem_req_o.ar_valid = 1'b1;
                if (mem_resp_i.ar_ready) begin
                    state_n = is_last_cdw_lvl ? LEAF : NON_LEAF;
                end
            end

            // ─────────────────────────────────────────────────────────
            NON_LEAF: begin
                if (mem_resp_i.r_valid) begin
                    mem_req_o.r_ready = 1'b1;

                    if (!nl_view.v) begin
                        state_n = ERROR_S;
                        cause_n = rv_iommu::DDT_ENTRY_INVALID;
                    end
                    else if ((|nl_view.reserved_1) || (|nl_view.reserved_2)) begin
                        state_n = ERROR_S;
                        cause_n = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                    end
                    else begin
                        case (cdw_lvl_q)
                            LVL3: begin
                                cdw_lvl_n  = LVL2;
                                cdw_pptr_n = {nl_view.ppn,
                                              (MSITrans == rv_iommu::MSI_DISABLED) ? device_id_q[15:7] : device_id_q[14:6],
                                              3'b0};
                            end
                            LVL2: begin
                                cdw_lvl_n  = LVL1;
                                cdw_pptr_n = {nl_view.ppn,
                                              (MSITrans == rv_iommu::MSI_DISABLED) ? {device_id_q[6:0], 5'b0} : {device_id_q[5:0], 6'b0}};
                            end
                            default: ;
                        endcase
                        state_n = MEM_ACCESS;
                    end
                end
            end

            // ─────────────────────────────────────────────────────────
            LEAF: begin
                // PTW がたった今 pdtp.PPN を翻訳完了したなら、 SPA に書き戻し
                if (ptw_done_i) dc_fsc_n.ppn = pdt_ppn_i;

                // Last DW 判定: DC を全部読み終わったか、 かつ S2 翻訳完了済みか
                if (dc_fully_loaded && (ptw_done_q || !en_stage2_i || !dc_tc_q.pdtv)) begin
                    state_n     = IDLE;
                    update_dc_o = 1'b1;
                end
                else if (mem_resp_i.r_valid) begin
                    mem_req_o.r_ready = 1'b1;
                    en_msi_check      = 1'b1;
                    entry_cnt_n       = entry_cnt_q + 1;

                    case (entry_cnt_q)
                        3'b000: begin   // DC.tc
                            dc_tc_n = dc_tc_view;
                            if (!dc_tc_view.v) begin
                                state_n      = ERROR_S;
                                cause_n      = rv_iommu::DDT_ENTRY_INVALID;
                                wait_rlast_n = 1'b1;
                            end
                            if ((|dc_tc_view.reserved_1) || (|dc_tc_view.reserved_2) ||
                                (!caps_ats_i && (dc_tc_view.en_ats || dc_tc_view.en_pri || dc_tc_view.prpr)) ||
                                (!dc_tc_view.en_ats && (dc_tc_view.t2gpa || dc_tc_view.en_pri)) ||
                                (!dc_tc_view.en_pri && dc_tc_view.prpr) ||
                                (!dc_tc_view.pdtv && dc_tc_view.dpe) ||
                                (!caps_amo_hwad_i && (dc_tc_view.sade || dc_tc_view.gade)) ||
                                (fctl_be_i != dc_tc_view.sbe) ||
                                (dc_tc_view.sxl != fctl_gxl_i)) begin
                                state_n      = ERROR_S;
                                cause_n      = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                                wait_rlast_n = 1'b1;
                            end
                        end

                        3'b001: begin   // DC.iohgatp
                            dc_iohgatp_n = dc_iohgatp_view;
                            if ((dc_tc_q.t2gpa && !(|dc_iohgatp_view.mode)) ||
                                (!(dc_iohgatp_view.mode inside {4'd0, 4'd8, 4'd9, 4'd10})) ||
                                (!fctl_gxl_i && ((!caps_sv39x4_i && dc_iohgatp_view.mode == 4'd8) ||
                                                 (!caps_sv48x4_i && dc_iohgatp_view.mode == 4'd9) ||
                                                 (!caps_sv57x4_i && dc_iohgatp_view.mode == 4'd10))) ||
                                ( fctl_gxl_i && (!caps_sv32x4_i && dc_iohgatp_view.mode == 4'd8)) ||
                                (|dc_iohgatp_view.mode && |dc_iohgatp_view.ppn[1:0])) begin
                                state_n      = ERROR_S;
                                cause_n      = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                                wait_rlast_n = 1'b1;
                            end
                        end

                        3'b010: begin   // DC.ta
                            dc_ta_n = dc_ta_view;
                            if ((|dc_ta_view.reserved_1) || (|dc_ta_view.reserved_2)) begin
                                state_n      = ERROR_S;
                                cause_n      = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                                wait_rlast_n = 1'b1;
                            end
                        end

                        3'b011: begin   // DC.fsc (last DW if MSI disabled)
                            dc_fsc_n = dc_fsc_view;
                            if ((dc_tc_q.pdtv && ((dc_fsc_view.mode inside {[4:15]}) ||
                                                  (!caps_pd20_i && dc_fsc_view.mode == 4'b0011) ||
                                                  (!caps_pd17_i && dc_fsc_view.mode == 4'b0010) ||
                                                  (!caps_pd8_i  && dc_fsc_view.mode == 4'b0001))) ||
                                (!dc_tc_q.pdtv && !dc_tc_q.sxl && (!(dc_fsc_view.mode inside {4'd0, 4'd8, 4'd9, 4'd10}) ||
                                                                    (!caps_sv39_i && dc_fsc_view.mode == 4'd8) ||
                                                                    (!caps_sv48_i && dc_fsc_view.mode == 4'd9) ||
                                                                    (!caps_sv57_i && dc_fsc_view.mode == 4'd10))) ||
                                (!dc_tc_q.pdtv &&  dc_tc_q.sxl && (!(dc_fsc_view.mode inside {4'd0, 4'd8}) ||
                                                                   (!caps_sv32_i && dc_fsc_view.mode == 4'd8))) ||
                                (|dc_fsc_view.reserved)) begin
                                wait_rlast_n = (MSITrans == rv_iommu::MSI_DISABLED) ? 1'b0 : 1'b1;
                                state_n      = ERROR_S;
                                cause_n      = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                            end
                            else if (MSITrans == rv_iommu::MSI_DISABLED) begin
                                // MSI 無効のとき、 ここで pdtp.PPN 翻訳をトリガ
                                if (dc_iohgatp_q.mode != 4'b0000 && dc_tc_q.pdtv)
                                    state_n = GUEST_TR;
                            end
                        end

                        // DC MSI fields (MSI 有効時のみ意味あり)
                        3'b100, 3'b101, 3'b110: begin
                            if (translate_pdtp) state_n = GUEST_TR;
                            if (msi_check_error) begin
                                wait_rlast_n = (entry_cnt_q != 3'b110);
                                state_n      = ERROR_S;
                                cause_n      = rv_iommu::DDT_ENTRY_MISCONFIGURED;
                            end
                        end

                        default: ;
                    endcase
                end

                if (flush_i) state_n = IDLE;
            end

            // ─────────────────────────────────────────────────────────
            // GUEST_TR: pdtp.PPN を PTW で S2 翻訳依頼
            // ─────────────────────────────────────────────────────────
            GUEST_TR: begin
                pdt_gppn_o            = dc_fsc_q.ppn[riscv::GPPNW-1:0];
                iohgatp_ppn_fw_o      = dc_iohgatp_q.ppn;
                cdw_implicit_access_o = 1'b1;
                state_n               = LEAF;
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
            update_dc_o  = 1'b0;
            wait_rlast_n = ~mem_resp_i.r.last;
            cause_n      = rv_iommu::DDT_DATA_CORRUPTION;
            state_n      = ERROR_S;
        end
    end

    // ── Sequential ───────────────────────────────────────────────────
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            state_q         <= IDLE;
            cdw_lvl_q       <= LVL1;
            cdw_pptr_q      <= '0;
            entry_cnt_q     <= '0;
            device_id_q     <= '0;
            cause_q         <= '0;
            dc_tc_q         <= '0;
            dc_iohgatp_q    <= '0;
            dc_ta_q         <= '0;
            dc_fsc_q        <= '0;
            ptw_done_q      <= 1'b0;
            wait_rlast_q    <= 1'b0;
            edge_trigger_q  <= 1'b0;
        end else begin
            state_q         <= state_n;
            cdw_pptr_q      <= cdw_pptr_n;
            cdw_lvl_q       <= cdw_lvl_n;
            entry_cnt_q     <= entry_cnt_n;
            device_id_q     <= device_id_n;
            cause_q         <= cause_n;
            dc_tc_q         <= dc_tc_n;
            dc_iohgatp_q    <= dc_iohgatp_n;
            dc_ta_q         <= dc_ta_n;
            dc_fsc_q        <= dc_fsc_n;
            ptw_done_q      <= ptw_done_i;
            wait_rlast_q    <= wait_rlast_n;
            edge_trigger_q  <= edge_trigger_n;
        end
    end

endmodule