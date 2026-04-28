// tb_rv_iommu_ptw_sv39x4_pc_wrapper.sv
// Wraps rv_iommu_ptw_sv39x4_pc for cocotb/Verilator testing.
// Flattens AXI packed structs to individual logic signals for MockMemory.

`ifndef TB_RV_IOMMU_PTW_SV39X4_PC_WRAPPER_SV
`define TB_RV_IOMMU_PTW_SV39X4_PC_WRAPPER_SV

module tb_rv_iommu_ptw_sv39x4_pc_wrapper
import riscv::*;
import rv_iommu::*;
import lint_wrapper::*;
(
    // Clock / reset
    input  logic        clk_i,
    input  logic        rst_ni,

    // PTW control
    input  logic        init_ptw_i,
    input  logic        en_1S_i,
    input  logic        en_2S_i,
    input  logic        is_store_i,

    // AXI read channel – flat (MockMemory interface)
    output logic        mem_rd_req_valid_o,    // ar_valid
    output logic [63:0] mem_rd_req_addr_o,     // ar.addr
    output logic        mem_rd_resp_ready_o,   // r_ready
    input  logic        mem_ar_ready_i,        // ar_ready  (tie 1 for normal tests)
    input  logic        mem_rd_resp_valid_i,   // r_valid
    input  logic [63:0] mem_rd_resp_data_i,    // r.data
    input  logic [1:0]  mem_rd_resp_resp_i,    // r.resp (0=OKAY, 2=SLVERR)

    // PTW status outputs
    output logic        ptw_active_o,
    output logic        ptw_error_o,
    output logic        ptw_error_2S_o,
    output logic        ptw_error_2S_int_o,
    output logic [11:0] cause_code_o,

    // IOTLB update signals
    output logic        update_o,
    output logic        up_1S_2M_o,
    output logic        up_1S_1G_o,
    output logic        up_2S_2M_o,
    output logic        up_2S_1G_o,
    output logic [28:0] up_vpn_o,
    output logic [19:0] up_pscid_o,
    output logic [15:0] up_gscid_o,
    output logic [63:0] up_1S_content_o,   // riscv::pte_t (64-bit packed)
    output logic [63:0] up_2S_content_o,

    // IOTLB request tags
    input  logic [63:0] req_iova_i,
    input  logic [19:0] pscid_i,
    input  logic [15:0] gscid_i,

    // MSI (unused: MSITrans=DISABLED)
    input  logic        msi_en_i,
    input  logic [28:0] msi_addr_mask_i,
    input  logic [28:0] msi_addr_pattern_i,

    output logic        gpaddr_is_msi_o,
    output logic [28:0] msi_vpn_o,
    output logic        msi_1S_2M_o,
    output logic        msi_1S_1G_o,
    output logic [63:0] msi_gpte_o,

    // CDW implicit translation
    input  logic        cdw_implicit_access_i,
    input  logic [28:0] pdt_gppn_i,
    output logic        cdw_done_o,
    output logic        flush_cdw_o,

    // Page table root PPNs
    input  logic [43:0] iosatp_ppn_i,
    input  logic [43:0] iohgatp_ppn_i,

    // Bad GPA (on S2 fault)
    output logic [40:0] bad_gpaddr_o
);

    // Internal AXI struct signals
    lint_wrapper::req_t  axi_req;
    lint_wrapper::resp_t axi_resp;

    // Pack flat inputs → AXI response struct
    always_comb begin
        axi_resp          = '0;
        axi_resp.ar_ready = mem_ar_ready_i;
        axi_resp.r_valid  = mem_rd_resp_valid_i;
        axi_resp.r.data   = mem_rd_resp_data_i;
        axi_resp.r.resp   = axi_pkg::resp_t'(mem_rd_resp_resp_i);
        axi_resp.r.last   = 1'b1;
    end

    // Extract flat outputs ← AXI request struct
    assign mem_rd_req_valid_o  = axi_req.ar_valid;
    assign mem_rd_req_addr_o   = axi_req.ar.addr;
    assign mem_rd_resp_ready_o = axi_req.r_ready;

    // DUT
    rv_iommu_ptw_sv39x4_pc #(
        .MSITrans  (rv_iommu::MSI_DISABLED),
        .axi_req_t (lint_wrapper::req_t),
        .axi_rsp_t (lint_wrapper::resp_t)
    ) i_dut (
        .clk_i               (clk_i),
        .rst_ni              (rst_ni),
        .init_ptw_i          (init_ptw_i),
        .en_1S_i             (en_1S_i),
        .en_2S_i             (en_2S_i),
        .is_store_i          (is_store_i),
        .mem_resp_i          (axi_resp),
        .mem_req_o           (axi_req),
        .ptw_active_o        (ptw_active_o),
        .ptw_error_o         (ptw_error_o),
        .ptw_error_2S_o      (ptw_error_2S_o),
        .ptw_error_2S_int_o  (ptw_error_2S_int_o),
        .cause_code_o        (cause_code_o),
        .update_o            (update_o),
        .up_1S_2M_o          (up_1S_2M_o),
        .up_1S_1G_o          (up_1S_1G_o),
        .up_2S_2M_o          (up_2S_2M_o),
        .up_2S_1G_o          (up_2S_1G_o),
        .up_vpn_o            (up_vpn_o),
        .up_pscid_o          (up_pscid_o),
        .up_gscid_o          (up_gscid_o),
        .up_1S_content_o     (up_1S_content_o),
        .up_2S_content_o     (up_2S_content_o),
        .req_iova_i          (req_iova_i),
        .pscid_i             (pscid_i),
        .gscid_i             (gscid_i),
        .msi_en_i            (msi_en_i),
        .msi_addr_mask_i     (msi_addr_mask_i),
        .msi_addr_pattern_i  (msi_addr_pattern_i),
        .gpaddr_is_msi_o     (gpaddr_is_msi_o),
        .msi_vpn_o           (msi_vpn_o),
        .msi_1S_2M_o         (msi_1S_2M_o),
        .msi_1S_1G_o         (msi_1S_1G_o),
        .msi_gpte_o          (msi_gpte_o),
        .cdw_implicit_access_i (cdw_implicit_access_i),
        .pdt_gppn_i          (pdt_gppn_i),
        .cdw_done_o          (cdw_done_o),
        .flush_cdw_o         (flush_cdw_o),
        .iosatp_ppn_i        (iosatp_ppn_i),
        .iohgatp_ppn_i       (iohgatp_ppn_i),
        .bad_gpaddr_o        (bad_gpaddr_o)
    );

endmodule

`endif
