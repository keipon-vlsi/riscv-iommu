// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (PR-walker refactor)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: Thin wrapper that preserves the legacy rv_iommu_ptw_sv39x4_pc
//              interface. Internally instantiates:
//                  - rv_iommu_walk_ctrl : translation orchestrator
//                  - rv_iommu_pt_walker : pure single-PT walker
//
//              The walker owns the AXI master. The wrapper exposes the same
//              ports as the legacy PTW so that rv_iommu_tw_sv39x4_pc does not
//              need to change.

module rv_iommu_ptw_sv39x4_pc
    import rv_iommu::*;
#(
    parameter rv_iommu::msi_trans_t MSITrans    = rv_iommu::MSI_DISABLED,
    parameter type axi_req_t = logic,
    parameter type axi_rsp_t = logic
) (
    input  logic                                clk_i,
    input  logic                                rst_ni,

    // Trigger
    input  logic                                init_ptw_i,

    // Status / errors
    output logic                                ptw_active_o,
    output logic                                ptw_error_o,
    output logic                                ptw_error_2S_o,
    output logic                                ptw_error_2S_int_o,
    output logic [rv_iommu::CAUSE_LEN-1:0]      cause_code_o,

    // Translation params
    input  logic                                en_1S_i,
    input  logic                                en_2S_i,
    input  logic                                is_store_i,
    input  logic                                is_rx_i,
    input  logic                                priv_lvl_i,
    input  logic                                sum_i,

    // AXI master (owned by walker)
    input  axi_rsp_t                            mem_resp_i,
    output axi_req_t                            mem_req_o,

    // IOTLB update bus
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

    // IOTLB tags
    input  logic [riscv::VLEN-1:0]              req_iova_i,
    input  logic [19:0]                         pscid_i,
    input  logic [15:0]                         gscid_i,

    // MSI handoff
    input  logic                                msi_en_i,
    input  logic [riscv::GPPNW-1:0]             msi_addr_mask_i,
    input  logic [riscv::GPPNW-1:0]             msi_addr_pattern_i,
    output logic                                gpaddr_is_msi_o,
    output logic [riscv::GPPNW-1:0]             msi_vpn_o,
    output logic                                msi_1S_2M_o,
    output logic                                msi_1S_1G_o,
    output riscv::pte_t                         msi_gpte_o,

    // CDW implicit translations
    input  logic                                cdw_implicit_access_i,
    input  logic [riscv::GPPNW-1:0]             pdt_gppn_i,
    output logic                                cdw_done_o,
    output logic                                flush_cdw_o,

    // From DC/PC
    input  logic [riscv::PPNW-1:0]              iosatp_ppn_i,
    input  logic [riscv::PPNW-1:0]              iohgatp_ppn_i,

    // Bad GPA report
    output logic [riscv::GPLEN-1:0]             bad_gpaddr_o
);

    // ── Internal handshake wires (walk_ctrl ⇄ pt_walker) ─────────────
    logic                               walker_req_valid;
    logic                               walker_req_ready;
    logic                               walker_req_op;
    logic                               walker_req_is_sv39x4;
    logic [riscv::PPNW-1:0]             walker_req_root_ppn;
    logic [riscv::VLEN-1:0]             walker_req_va;
    logic [riscv::PLEN-1:0]             walker_req_pptr;

    logic                               walker_rsp_valid;
    riscv::pte_t                        walker_rsp_pte;
    logic [1:0]                         walker_rsp_lvl;
    logic                               walker_rsp_error;
    logic [rv_iommu::CAUSE_LEN-1:0]     walker_rsp_cause;

    logic                               walker_active;
    logic                               ctrl_active;

    assign ptw_active_o = walker_active | ctrl_active;

    // Edge-triggered init: convert init_ptw_i level signal to single-cycle pulse
    // (Matches legacy PTW behaviour where init_ptw_i may remain high beyond cycle 0)
    logic init_q;
    logic init_pulse;
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) init_q <= 1'b0;
        else         init_q <= init_ptw_i;
    end
    assign init_pulse = init_ptw_i & ~init_q;

    // ── Walk Controller ──────────────────────────────────────────────
    rv_iommu_walk_ctrl #(
        .MSITrans               (MSITrans  ),
        .axi_req_t              (axi_req_t ),
        .axi_rsp_t              (axi_rsp_t )
    ) i_walk_ctrl (
        .clk_i                  (clk_i              ),
        .rst_ni                 (rst_ni             ),

        .init_i                 (init_pulse | cdw_implicit_access_i),

        .active_o               (ctrl_active        ),
        .error_o                (ptw_error_o        ),
        .error_2S_o             (ptw_error_2S_o     ),
        .error_2S_int_o         (ptw_error_2S_int_o ),
        .cause_o                (cause_code_o       ),

        .en_1S_i                (en_1S_i            ),
        .en_2S_i                (en_2S_i            ),
        .is_store_i             (is_store_i         ),
        .is_rx_i                (is_rx_i            ),
        .priv_lvl_i             (priv_lvl_i         ),
        .sum_i                  (sum_i              ),
        .req_iova_i             (req_iova_i         ),
        .pscid_i                (pscid_i            ),
        .gscid_i                (gscid_i            ),
        .iosatp_ppn_i           (iosatp_ppn_i       ),
        .iohgatp_ppn_i          (iohgatp_ppn_i      ),

        .update_o               (update_o           ),
        .up_1S_2M_o             (up_1S_2M_o         ),
        .up_1S_1G_o             (up_1S_1G_o         ),
        .up_2S_2M_o             (up_2S_2M_o         ),
        .up_2S_1G_o             (up_2S_1G_o         ),
        .up_vpn_o               (up_vpn_o           ),
        .up_pscid_o             (up_pscid_o         ),
        .up_gscid_o             (up_gscid_o         ),
        .up_1S_content_o        (up_1S_content_o    ),
        .up_2S_content_o        (up_2S_content_o    ),

        .msi_en_i               (msi_en_i           ),
        .msi_addr_mask_i        (msi_addr_mask_i    ),
        .msi_addr_pattern_i     (msi_addr_pattern_i ),
        .gpaddr_is_msi_o        (gpaddr_is_msi_o    ),
        .msi_vpn_o              (msi_vpn_o          ),
        .msi_1S_2M_o            (msi_1S_2M_o        ),
        .msi_1S_1G_o            (msi_1S_1G_o        ),
        .msi_gpte_o             (msi_gpte_o         ),

        .cdw_implicit_access_i  (cdw_implicit_access_i),
        .pdt_gppn_i             (pdt_gppn_i         ),
        .cdw_done_o             (cdw_done_o         ),
        .flush_cdw_o            (flush_cdw_o        ),

        .bad_gpaddr_o           (bad_gpaddr_o       ),

        // Walker interface
        .walker_req_valid_o     (walker_req_valid       ),
        .walker_req_ready_i     (walker_req_ready       ),
        .walker_req_op_o        (walker_req_op          ),
        .walker_req_is_sv39x4_o (walker_req_is_sv39x4   ),
        .walker_req_root_ppn_o  (walker_req_root_ppn    ),
        .walker_req_va_o        (walker_req_va          ),
        .walker_req_pptr_o      (walker_req_pptr        ),
        .walker_rsp_valid_i     (walker_rsp_valid       ),
        .walker_rsp_pte_i       (walker_rsp_pte         ),
        .walker_rsp_lvl_i       (walker_rsp_lvl         ),
        .walker_rsp_error_i     (walker_rsp_error       ),
        .walker_rsp_cause_i     (walker_rsp_cause       )
    );

    // ── Pure PT Walker ───────────────────────────────────────────────
    rv_iommu_pt_walker #(
        .axi_req_t              (axi_req_t),
        .axi_rsp_t              (axi_rsp_t)
    ) i_pt_walker (
        .clk_i                  (clk_i),
        .rst_ni                 (rst_ni),

        .req_valid_i            (walker_req_valid       ),
        .req_ready_o            (walker_req_ready       ),
        .req_op_i               (walker_req_op          ),
        .req_is_sv39x4_i        (walker_req_is_sv39x4   ),
        .req_root_ppn_i         (walker_req_root_ppn    ),
        .req_va_i               (walker_req_va          ),
        .req_pptr_i             (walker_req_pptr        ),

        .rsp_valid_o            (walker_rsp_valid       ),
        .rsp_pte_o              (walker_rsp_pte         ),
        .rsp_lvl_o              (walker_rsp_lvl         ),
        .rsp_error_o            (walker_rsp_error       ),
        .rsp_cause_o            (walker_rsp_cause       ),

        .mem_resp_i             (mem_resp_i             ),
        .mem_req_o              (mem_req_o              ),

        .active_o               (walker_active          )
    );

endmodule