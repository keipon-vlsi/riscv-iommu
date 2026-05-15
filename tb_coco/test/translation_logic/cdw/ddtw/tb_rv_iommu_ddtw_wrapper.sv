// tb_rv_iommu_ddtw_wrapper.sv
// DDTW (rv_iommu_ddtw) を cocotb から触りやすくする flat-port wrapper。
// multi-beat AXI burst を扱うので ar.len / r.last も flat に露出。

`ifndef TB_RV_IOMMU_DDTW_WRAPPER_SV
`define TB_RV_IOMMU_DDTW_WRAPPER_SV

module tb_rv_iommu_ddtw_wrapper
import riscv::*;
import rv_iommu::*;
import lint_wrapper::*;
#(
    parameter int DC_WIDTH = 256   // MSI_DISABLED: 32 byte = 256 bit
)
(
    // Clock / reset
    input  logic        clk_i,
    input  logic        rst_ni,

    // Control inputs
    input  logic        init_i,
    input  logic [23:0] req_did_i,
    input  logic [43:0] ddtp_ppn_i,
    input  logic [3:0]  ddtp_mode_i,    // 1=BARE, 2=1lvl, 3=2lvl, 4=3lvl
    input  logic        en_stage2_i,
    input  logic        flush_i,

    // Capabilities (= happy path では caps_sv39 だけ立てれば OK)
    input  logic        caps_ats_i,
    input  logic        caps_t2gpa_i,
    input  logic        caps_pd20_i,
    input  logic        caps_pd17_i,
    input  logic        caps_pd8_i,
    input  logic        caps_sv39_i,
    input  logic        caps_sv39x4_i,
    input  logic        caps_msi_flat_i,
    input  logic        caps_amo_hwad_i,
    input  logic        caps_end_i,
    input  logic        fctl_be_i,

    // PTW simulation (= nested S2 walk の代わり)
    input  logic        ptw_done_i,
    input  logic [43:0] pdt_ppn_i,

    // AXI request (flat 出力)
    output logic        mem_ar_valid_o,
    output logic [63:0] mem_ar_addr_o,
    output logic [7:0]  mem_ar_len_o,
    output logic [2:0]  mem_ar_size_o,
    output logic [1:0]  mem_ar_burst_o,
    output logic [3:0]  mem_ar_id_o,
    output logic        mem_r_ready_o,
    input  logic        mem_ar_ready_i,
    input  logic        mem_r_valid_i,
    input  logic [63:0] mem_r_data_i,
    input  logic        mem_r_last_i,
    input  logic [1:0]  mem_r_resp_i,

    // Outputs
    output logic        active_o,
    output logic        error_o,
    output logic [11:0] cause_code_o,
    output logic        update_dc_o,
    output logic [23:0] up_did_o,
    output logic [DC_WIDTH-1:0]  up_dc_content_o,
    output logic        cdw_implicit_access_o,
    output logic [28:0] pdt_gppn_o,
    output logic [43:0] iohgatp_ppn_fw_o
);

    // Internal AXI structs (= DUT 接続用)
    lint_wrapper::req_t  axi_req;
    lint_wrapper::resp_t axi_resp;

    // Pack inputs into resp struct
    always_comb begin
        axi_resp           = '0;
        axi_resp.ar_ready  = mem_ar_ready_i;
        axi_resp.r_valid   = mem_r_valid_i;
        axi_resp.r.data    = mem_r_data_i;
        axi_resp.r.last    = mem_r_last_i;
        axi_resp.r.resp    = axi_pkg::resp_t'(mem_r_resp_i);
    end

    // Extract outputs
    assign mem_ar_valid_o = axi_req.ar_valid;
    assign mem_ar_addr_o  = axi_req.ar.addr;
    assign mem_ar_len_o   = axi_req.ar.len;
    assign mem_ar_size_o  = axi_req.ar.size;
    assign mem_ar_burst_o = axi_req.ar.burst;
    assign mem_ar_id_o    = axi_req.ar.id;
    assign mem_r_ready_o  = axi_req.r_ready;

    // DUT
    rv_iommu_ddtw #(
        .MSITrans  (rv_iommu::MSI_DISABLED),
        .axi_req_t (lint_wrapper::req_t),
        .axi_rsp_t (lint_wrapper::resp_t),
        .DC_WIDTH  (DC_WIDTH)
    ) i_dut (
        .clk_i                 (clk_i),
        .rst_ni                (rst_ni),
        .active_o              (active_o),
        .error_o               (error_o),
        .cause_code_o          (cause_code_o),
        .caps_ats_i            (caps_ats_i),
        .caps_t2gpa_i          (caps_t2gpa_i),
        .caps_pd20_i           (caps_pd20_i),
        .caps_pd17_i           (caps_pd17_i),
        .caps_pd8_i            (caps_pd8_i),
        .caps_sv39_i           (caps_sv39_i),
        .caps_sv39x4_i         (caps_sv39x4_i),
        .caps_msi_flat_i       (caps_msi_flat_i),
        .caps_amo_hwad_i       (caps_amo_hwad_i),
        .caps_end_i            (caps_end_i),
        .fctl_be_i             (fctl_be_i),
        .mem_resp_i            (axi_resp),
        .mem_req_o             (axi_req),
        .update_dc_o           (update_dc_o),
        .up_did_o              (up_did_o),
        .up_dc_content_o       (up_dc_content_o),
        .req_did_i             (req_did_i),
        .init_i                (init_i),
        .ddtp_ppn_i            (ddtp_ppn_i),
        .ddtp_mode_i           (ddtp_mode_i),
        .en_stage2_i           (en_stage2_i),
        .ptw_done_i            (ptw_done_i),
        .flush_i               (flush_i),
        .pdt_ppn_i             (pdt_ppn_i),
        .cdw_implicit_access_o (cdw_implicit_access_o),
        .pdt_gppn_o            (pdt_gppn_o),
        .iohgatp_ppn_fw_o      (iohgatp_ppn_fw_o)
    );

endmodule

`endif