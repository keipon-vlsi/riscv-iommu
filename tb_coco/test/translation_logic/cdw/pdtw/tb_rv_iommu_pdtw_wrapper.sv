// tb_rv_iommu_pdtw_wrapper.sv
// PDTW (rv_iommu_pdtw) を cocotb から触りやすくする flat-port wrapper。

`ifndef TB_RV_IOMMU_PDTW_WRAPPER_SV
`define TB_RV_IOMMU_PDTW_WRAPPER_SV

module tb_rv_iommu_pdtw_wrapper
import riscv::*;
import rv_iommu::*;
import lint_wrapper::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    // Control inputs
    input  logic        init_i,
    input  logic [23:0] req_did_i,
    input  logic [19:0] req_pid_i,
    input  logic [43:0] pdtp_ppn_i,
    input  logic [3:0]  pdtp_mode_i,   // 1=PD8, 2=PD17, 3=PD20
    input  logic        en_stage2_i,
    input  logic        flush_i,

    // PTW simulation
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
    output logic                       active_o,
    output logic                       error_o,
    output logic [11:0]                cause_code_o,
    output logic                       update_pc_o,
    output logic [23:0]                up_did_o,
    output logic [19:0]                up_pid_o,
    output rv_iommu::pc_t              up_pc_content_o,
    output logic                       cdw_implicit_access_o,
    output logic [28:0]                pdt_gppn_o
);

    lint_wrapper::req_t  axi_req;
    lint_wrapper::resp_t axi_resp;

    always_comb begin
        axi_resp           = '0;
        axi_resp.ar_ready  = mem_ar_ready_i;
        axi_resp.r_valid   = mem_r_valid_i;
        axi_resp.r.data    = mem_r_data_i;
        axi_resp.r.last    = mem_r_last_i;
        axi_resp.r.resp    = axi_pkg::resp_t'(mem_r_resp_i);
    end

    assign mem_ar_valid_o = axi_req.ar_valid;
    assign mem_ar_addr_o  = axi_req.ar.addr;
    assign mem_ar_len_o   = axi_req.ar.len;
    assign mem_ar_size_o  = axi_req.ar.size;
    assign mem_ar_burst_o = axi_req.ar.burst;
    assign mem_ar_id_o    = axi_req.ar.id;
    assign mem_r_ready_o  = axi_req.r_ready;

    rv_iommu_pdtw #(
        .axi_req_t (lint_wrapper::req_t),
        .axi_rsp_t (lint_wrapper::resp_t)
    ) i_dut (
        .clk_i                 (clk_i),
        .rst_ni                (rst_ni),
        .active_o              (active_o),
        .error_o               (error_o),
        .cause_code_o          (cause_code_o),
        .mem_resp_i            (axi_resp),
        .mem_req_o             (axi_req),
        .update_pc_o           (update_pc_o),
        .up_did_o              (up_did_o),
        .up_pid_o              (up_pid_o),
        .up_pc_content_o       (up_pc_content_o),
        .req_did_i             (req_did_i),
        .req_pid_i             (req_pid_i),
        .init_i                (init_i),
        .en_stage2_i           (en_stage2_i),
        .pdtp_ppn_i            (pdtp_ppn_i),
        .pdtp_mode_i           (pdtp_mode_i),
        .ptw_done_i            (ptw_done_i),
        .flush_i               (flush_i),
        .pdt_ppn_i             (pdt_ppn_i),
        .cdw_implicit_access_o (cdw_implicit_access_o),
        .pdt_gppn_o            (pdt_gppn_o)
    );

endmodule

`endif