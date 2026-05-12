// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (PR1: IOTLB split refactor)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1

// Licensed under the Solderpad Hardware License v 2.1 (the "License");
// you may not use this file except in compliance with the License,
// or, at your option, the Apache License version 2.0.
// You may obtain a copy of the License at https://solderpad.org/licenses/SHL-2.1/.
// Unless required by applicable law or agreed to in writing,
// any work distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and limitations under the License.
//
// Author: Manuel Rodríguez <manuel.cederog@gmail.com>
// Date: 06/02/2023
// Acknowledges: SSRC - Technology Innovation Institute (TII)
//
// Description: RISC-V IOMMU Translation Logic Wrapper.
//              Encompasses all modules involved in the address translation
//              process and report of translation faults.
//              Process Context support: YES
//              MSI Translation support: YES
//
// PR1 changes:
//   - Replaced unified rv_iommu_iotlb_sv39x4 with separate S1 / S2 IOTLBs
//   - Added hit-combining + per-cache update enable logic
//   - PTW / MSIPTW / CDW interfaces and IO ports are unchanged
//   - Behaviour is functionally equivalent to the unified IOTLB

//! NOTES:
/*
    - For now, req_trans_i must be hold high for the entire translation process (whenever walks are needed). If it is cleared,
      IOTLB hit signal is also cleared even if it has a valid translation. Further on, input signals may be propagated to achieve
      a stronger implementation (+ HW cost).
*/

module rv_iommu_tw_sv39x4_pc #(

    parameter int unsigned  IOTLB_ENTRIES       = 4,      // (deprecated, kept for BC)
    parameter int unsigned  IOTLB_S1_ENTRIES    = 4,      // new: S1 IOTLB depth
    parameter int unsigned  IOTLB_S2_ENTRIES    = 4,      // new: S2 IOTLB depth
    parameter int unsigned  DDTC_ENTRIES        = 4,
    parameter int unsigned  PDTC_ENTRIES        = 4,
    parameter int unsigned  MRIFC_ENTRIES       = 4,

    // MSI translation support
    parameter rv_iommu::msi_trans_t MSITrans    = rv_iommu::MSI_DISABLED,

    /// AXI Full request struct type
    parameter type  axi_req_t       = logic,
    /// AXI Full response struct type
    parameter type  axi_rsp_t       = logic,

    // DC width
    parameter int DC_WIDTH          = -1
) (
    input  logic    clk_i,
    input  logic    rst_ni,

    // Trigger translation
    input  logic    req_trans_i,    // Normal translation
    input  logic    req_dbg_i,      // Debug translation

    // Translation request data
    input  logic [23:0]                     did_i,
    input  logic                            pv_i,
    input  logic [19:0]                     pid_i,
    input  logic [riscv::VLEN-1:0]          iova_i,
    output logic [15:0]                     gscid_o,
    output logic [19:0]                     pscid_o,

    input  logic [rv_iommu::TTYP_LEN-1:0]   trans_type_i,
    input  logic                            priv_lvl_i,

    // AXI ports directed to Data Structures Interface
    // CDW
    input  axi_rsp_t    cdw_axi_resp_i,
    output axi_req_t    cdw_axi_req_o,
    // PTW
    input  axi_rsp_t    ptw_axi_resp_i,
    output axi_req_t    ptw_axi_req_o,
    // MSI PTW
    input  axi_rsp_t    msiptw_axi_resp_i,
    output axi_req_t    msiptw_axi_req_o,
    // MRIF handler
    input  axi_rsp_t    mrif_handler_axi_resp_i,
    output axi_req_t    mrif_handler_axi_req_o,

    // From Regmap
    input  rv_iommu_reg_pkg::iommu_reg2hw_capabilities_reg_t   capabilities_i,
    input  rv_iommu_reg_pkg::iommu_reg2hw_fctl_reg_t           fctl_i,
    input  rv_iommu_reg_pkg::iommu_reg2hw_ddtp_reg_t           ddtp_i,

    // Request status and output data
    output logic                        trans_valid_o,
    output logic [riscv::PLEN-1:0]      spaddr_o,
    output logic                        is_superpage_o,
    // Error
    output logic                                trans_error_o,
    output logic                                report_fault_o,
    output logic [(rv_iommu::CAUSE_LEN-1):0]    cause_code_o,
    output logic                                is_guest_pf_o,
    output logic                                is_implicit_o,
    output logic [riscv::SVX-1:0]               bad_gpaddr_o,
    input  logic                                msi_write_error_i,

    // to HPM
    output logic                        iotlb_miss_o,
    output logic                        ddt_walk_o,
    output logic                        pdt_walk_o,
    output logic                        s1_ptw_o,
    output logic                        s2_ptw_o,

    // IOATC Invalidation control
    input  logic                        flush_ddtc_i,
    input  logic                        flush_dv_i,
    input  logic [23:0]                 flush_did_i,
    input  logic                        flush_pdtc_i,
    input  logic                        flush_pv_i,
    input  logic [19:0]                 flush_pid_i,
    input  logic                        flush_vma_i,
    input  logic                        flush_gvma_i,
    input  logic                        flush_av_i,
    input  logic                        flush_gv_i,
    input  logic                        flush_pscv_i,
    input  logic [riscv::GPPNW-1:0]     flush_vpn_i,
    input  logic [15:0]                 flush_gscid_i,
    input  logic [19:0]                 flush_pscid_i,

    output logic        ignore_request_o,
    input  logic        msi_data_valid_i,
    input  logic [31:0] msi_data_i
);

    // Address translation parameters
    logic [15:0] gscid;
    logic [19:0] pscid;
    logic [riscv::PPNW-1:0] iohgatp_ppn, iosatp_ppn;

    // PTW implicit translations for CDW walks
    logic                           cdw_implicit_access;
    logic [riscv::GPPNW-1:0]        pdt_gppn;
    logic                           cdw_done;
    logic                           flush_cdw;
    logic [riscv::PPNW-1:0]         iohgatp_ppn_fw;
    logic                           is_ddt_walk;

    // ── DDTW 専用信号 ────────────────────────────────────────────────────
    logic                                   ddtw_active;
    logic                                   ddtw_error;
    logic [rv_iommu::CAUSE_LEN-1:0]         ddtw_cause_code;
    logic                                   ddtw_implicit_access;
    logic [riscv::GPPNW-1:0]                ddtw_pdt_gppn;
    logic [riscv::PPNW-1:0]                 ddtw_iohgatp_ppn_fw;
    axi_req_t                               ddtw_axi_req;
    axi_rsp_t                               ddtw_axi_resp;

    // ── PDTW 専用信号 ────────────────────────────────────────────────────
    logic                                   pdtw_active;
    logic                                   pdtw_error;
    logic [rv_iommu::CAUSE_LEN-1:0]         pdtw_cause_code;
    logic                                   pdtw_implicit_access;
    logic [riscv::GPPNW-1:0]                pdtw_pdt_gppn;
    axi_req_t                               pdtw_axi_req;
    axi_rsp_t                               pdtw_axi_resp;

    // CDW から見える集約 signal
    assign cdw_active           = ddtw_active | pdtw_active;
    assign cdw_error            = ddtw_error | pdtw_error;
    assign cdw_cause_code = ddtw_error ? ddtw_cause_code :
                        pdtw_error ? pdtw_cause_code : '0;
    assign cdw_implicit_access  = ddtw_implicit_access | pdtw_implicit_access;
    assign pdt_gppn             = ddtw_active ? ddtw_pdt_gppn : pdtw_pdt_gppn;
    assign iohgatp_ppn_fw       = ddtw_iohgatp_ppn_fw;       // DDTW のみが forward する
    assign is_ddt_walk          = ddtw_active;               // = DDTW が active かどうか

    // To determine if current DC enables MSI translation
    logic msi_enabled;

    // MSI address check
    logic iova_is_msi;

    // MSI DC fields
    logic [riscv::GPPNW-1:0]    msi_addr_mask;
    logic [riscv::GPPNW-1:0]    msi_addr_pattern;

    // To determine if request is translated or untranslated
    logic is_translated;
    assign is_translated = (!trans_type_i[3] && trans_type_i[2]);

    // To determine if request is a PCIe ATS TR
    logic is_pcie_tr_req;
    assign is_pcie_tr_req = (trans_type_i == rv_iommu::PCIE_ATS_TRANS_REQ);

    // To determine if transaction is a store
    logic is_store;
    assign is_store = ((&trans_type_i[1:0] == 1'b1) && (!trans_type_i[3]));

    // To determine if transaction is read-for-execute
    logic is_rx;
    assign is_rx = (!trans_type_i[3] && !trans_type_i[1] && trans_type_i[0]);

    // Efective iohgatp.ppn field to introduce in the PTW. May need to be forwarded by the CDW
    logic [riscv::PPNW-1:0] ptw_iohgatp_ppn;
    assign ptw_iohgatp_ppn = (is_ddt_walk & cdw_implicit_access) ? iohgatp_ppn_fw : iohgatp_ppn;

    // IOATC wires
    // DDTC
    logic                       ddtc_access;
    logic [(DC_WIDTH-1):0]      ddtc_lu_content;
    logic                       ddtc_lu_hit;

    logic                       ddtc_update;
    logic [23:0]                ddtc_up_did;
    logic [(DC_WIDTH-1):0]      ddtc_up_content;

    rv_iommu::dc_base_t         dc_base;
    assign dc_base = rv_iommu::dc_base_t'(ddtc_lu_content);

    // PDTC
    logic                       pdtc_access;
    rv_iommu::pc_t              pdtc_lu_content;
    logic                       pdtc_lu_hit;

    logic                       pdtc_update;
    logic [23:0]                pdtc_up_did;
    logic [19:0]                pdtc_up_pid;
    rv_iommu::pc_t              pdtc_up_content;

    // ─────────────────────────────────────────────────────────────────
    // IOTLB access wires (S1 / S2 split)
    // ─────────────────────────────────────────────────────────────────
    logic                       iotlb_access;
    logic                       iotlb_lu_hit;
    logic                       iotlb_lu_miss;

    // S1 IOTLB lookup outputs
    riscv::pte_t                s1_iotlb_lu_pte;
    logic                       s1_iotlb_lu_2M;
    logic                       s1_iotlb_lu_1G;
    logic                       s1_iotlb_hit;
    logic                       s1_iotlb_miss;

    // S2 IOTLB lookup outputs
    riscv::pte_t                s2_iotlb_lu_pte;
    logic                       s2_iotlb_lu_2M;
    logic                       s2_iotlb_lu_1G;
    logic                       s2_iotlb_lu_is_msi;
    logic                       s2_iotlb_hit;
    logic                       s2_iotlb_miss;

    // Legacy alias signals (still referenced by the translation always_comb block)
    riscv::pte_t                iotlb_lu_1S_content;
    riscv::pte_t                iotlb_lu_2S_content;
    logic                       iotlb_lu_1S_2M, iotlb_lu_1S_1G;
    logic                       iotlb_lu_2S_2M, iotlb_lu_2S_1G;
    logic                       iotlb_lu_is_msi;

    assign iotlb_lu_1S_content = s1_iotlb_lu_pte;
    assign iotlb_lu_2S_content = s2_iotlb_lu_pte;
    assign iotlb_lu_1S_2M      = s1_iotlb_lu_2M;
    assign iotlb_lu_1S_1G      = s1_iotlb_lu_1G;
    assign iotlb_lu_2S_2M      = s2_iotlb_lu_2M;
    assign iotlb_lu_2S_1G      = s2_iotlb_lu_1G;
    assign iotlb_lu_is_msi     = s2_iotlb_lu_is_msi;

    // ─────────────────────────────────────────────────────────────────
    // Combined hit / miss
    //
    //   The combined IOTLB hit semantics, equivalent to the unified IOTLB:
    //     - S1 enabled → S1 IOTLB must hit
    //     - S2 enabled → S2 IOTLB must hit
    //     - S1-only + MSI route → S2 IOTLB must also hit with is_msi=1
    //                             (MSI entry stored at the same VPN tag)
    //     - Pure Bare-Bare → handled by the bare_translation path before lookup,
    //                        so this combination never asserts iotlb_access
    //
    //   "MSI route active" is detected by the S2 IOTLB returning hit with is_msi=1.
    //   In that case S2 lookup result is consumed regardless of S2_en.
    // ─────────────────────────────────────────────────────────────────
    logic msi_route_active;
    assign msi_route_active = s2_iotlb_hit & s2_iotlb_lu_is_msi;

    logic s2_required;
    assign s2_required = S2_en | msi_route_active;

    assign iotlb_lu_hit  = iotlb_access &
                           (S1_en       ? s1_iotlb_hit : 1'b1) &
                           (s2_required ? s2_iotlb_hit : 1'b1) &
                           (S1_en | S2_en | msi_route_active);
    assign iotlb_lu_miss = iotlb_access & ~iotlb_lu_hit;

    // First and second-stage translation status
    logic S1_en, S2_en;
    assign S1_en    = ((dc_base.tc.pdtv && pdtc_lu_content.fsc.mode != 4'b0000) ||
                       (!dc_base.tc.pdtv && dc_base.fsc.mode != 4'b0000)          );
    assign S2_en    = (dc_base.iohgatp.mode != 4'b0000);

    // IOVA canonicalization fault signals
    logic   iova_s1_ncanon;
    assign  iova_s1_ncanon = (iova_i[63:38] != {26{iova_i[38]}});
    logic   iova_s2_ncanon;
    assign  iova_s2_ncanon = |iova_i[63:41];

    // Alternative translation config for PTW implicit second-stage translations in CDW Walks
    logic   ptw_en_1S, ptw_en_2S;
    assign  ptw_en_1S = (cdw_implicit_access) ? 1'b0 : S1_en;
    assign  ptw_en_2S = (cdw_implicit_access) ? 1'b1 : S2_en;

    // Set for faults occurred before DDTC lookup
    logic   report_always;

    // Translation error signaling according to the spec
    logic   wrap_error;
    logic [(rv_iommu::CAUSE_LEN-1):0]  wrap_cause_code;
    // CDW error
    logic cdw_error;
    logic [(rv_iommu::CAUSE_LEN-1):0]  cdw_cause_code;
    // PTW error
    logic ptw_error;
    logic [(rv_iommu::CAUSE_LEN-1):0]  ptw_cause_code;

    logic msiptw_error;
    logic [(rv_iommu::CAUSE_LEN-1):0]  msiptw_cause_code;
    logic mrif_handler_error;
    logic [(rv_iommu::CAUSE_LEN-1):0]  mrif_handler_cause_code;

    // Guest page fault occurred during implicit 2nd-stage translation for 1st-stage translation
    logic   ptw_error_2S_int;
    assign  is_implicit_o = (ptw_error_2S_int | (flush_cdw & ~is_ddt_walk));

    // MSI PTW is active
    logic msiptw_active;

    // HPM event indicators
    logic cdw_active, ptw_active;
    assign iotlb_miss_o = iotlb_lu_miss;
    assign ddt_walk_o   = ddtw_active;
    assign pdt_walk_o   = pdtw_active;
    assign s1_ptw_o     = ptw_active & (ptw_en_1S);
    assign s2_ptw_o     = ptw_active & (ptw_en_2S);
    assign gscid_o      = gscid;
    assign pscid_o      = pscid;

    // The translation involved a superpage
    assign is_superpage_o = iotlb_lu_1S_2M | iotlb_lu_1S_1G | iotlb_lu_2S_2M | iotlb_lu_2S_1G;

    // If DC.tc.DPE is 1 and no valid process_id is given by the device, default value of zero is used
    logic [19:0] process_id;
    assign process_id = (!pv_i && dc_base.tc.dpe) ? '0 : pid_i;

    // To check whether process_id is wider than supported
    logic pid_wider_than_supported;
    assign pid_wider_than_supported = ((dc_base.fsc.mode == 4'b0001 && |process_id[19:8]) ||
                                       (dc_base.fsc.mode == 4'b0010 && |process_id[19:17]));

    // Fault reporting per DC.tc.DTF
    assign  report_fault_o    = (((ddtc_lu_hit & !dc_base.tc.dtf) |
                                  (report_always | msi_write_error_i | (cdw_error & is_ddt_walk))) & trans_error_o);

    // Update bus from PTW
    logic                       ptw_update;
    logic                       ptw_up_1S_2M;
    logic                       ptw_up_1S_1G;
    logic                       ptw_up_2S_2M;
    logic                       ptw_up_2S_1G;
    logic [riscv::GPPNW-1:0]    ptw_up_vpn;
    logic [19:0]                ptw_up_pscid;
    logic [15:0]                ptw_up_gscid;
    riscv::pte_t                ptw_up_1S_content;
    riscv::pte_t                ptw_up_2S_content;

    // Update bus from MSI PTW
    logic                       msi_update;
    logic                       mrifc_update;
    logic                       msi_up_1S_2M;
    logic                       msi_up_1S_1G;
    logic [riscv::GPPNW-1:0]    msi_up_vpn;
    logic [19:0]                msi_up_pscid;
    logic [15:0]                msi_up_gscid;
    riscv::pte_t                msi_up_1S_content;
    rv_iommu::msi_pte_flat_t    msi_up_content;
    rv_iommu::mrifc_entry_t     mrifc_up_msi_content;

    // MRIFC
    logic                       mrifc_lu_hit;
    logic                       mrifc_lu_miss;
    riscv::pte_t                mrifc_lu_1S_content;
    rv_iommu::mrifc_entry_t     mrifc_lu_msi_content;

    // ─────────────────────────────────────────────────────────────────
    // Combined update bus (= same shape as unified IOTLB had)
    // ─────────────────────────────────────────────────────────────────
    logic                       iotlb_update;
    logic                       iotlb_up_1S_2M;
    logic                       iotlb_up_1S_1G;
    logic                       iotlb_up_2S_2M;
    logic                       iotlb_up_2S_1G;
    logic                       iotlb_up_is_msi;
    logic [riscv::GPPNW-1:0]    iotlb_up_vpn;
    logic [19:0]                iotlb_up_pscid;
    logic [15:0]                iotlb_up_gscid;
    riscv::pte_t                iotlb_up_1S_content;
    riscv::pte_t                iotlb_up_2S_content;

    assign iotlb_update         = ptw_update | msi_update;
    assign iotlb_up_1S_2M       = (msi_update) ? (msi_up_1S_2M      )            : (ptw_up_1S_2M       );
    assign iotlb_up_1S_1G       = (msi_update) ? (msi_up_1S_1G      )            : (ptw_up_1S_1G       );
    assign iotlb_up_2S_2M       = (msi_update) ? (1'b0              )            : (ptw_up_2S_2M       );
    assign iotlb_up_2S_1G       = (msi_update) ? (1'b0              )            : (ptw_up_2S_1G       );
    assign iotlb_up_is_msi      = (msi_update) ? (1'b1              )            : (1'b0               );
    assign iotlb_up_vpn         = (msi_update) ? (msi_up_vpn        )            : (ptw_up_vpn         );
    assign iotlb_up_pscid       = (msi_update) ? (msi_up_pscid      )            : (ptw_up_pscid       );
    assign iotlb_up_gscid       = (msi_update) ? (msi_up_gscid      )            : (ptw_up_gscid       );
    assign iotlb_up_1S_content  = (msi_update) ? (msi_up_1S_content )            : (ptw_up_1S_content  );
    assign iotlb_up_2S_content  = (msi_update) ? (riscv::pte_t'(msi_up_content)) : (ptw_up_2S_content  );

    // ─────────────────────────────────────────────────────────────────
    // Per-cache update enables
    //   S1 IOTLB: written when an S1 entry is produced (PTW S1 leaf OR MSI path with S1 enabled)
    //   S2 IOTLB: written when an S2 entry is produced (PTW S2 leaf OR MSI path always)
    // ─────────────────────────────────────────────────────────────────
    logic   s1_iotlb_update;
    logic   s2_iotlb_update;
    logic   s1_iotlb_up_en_1S;
    logic   s1_iotlb_up_en_2S;
    logic   s2_iotlb_up_en_1S;
    logic   s2_iotlb_up_en_2S;

    // S1 IOTLB updated when S1 is the active first stage of this translation
    assign s1_iotlb_update    = iotlb_update & S1_en;
    assign s1_iotlb_up_en_1S  = 1'b1;        // entries always stored as en_1S=1
    assign s1_iotlb_up_en_2S  = S2_en;       // nested context tag

    // S2 IOTLB updated when an S2 entry was produced:
    //   - PTW nested completion (ptw_update & S2_en)
    //   - MSI translation completion (msi_update; entry tagged with is_msi=1)
    assign s2_iotlb_update    = (iotlb_update & S2_en) | msi_update;
    assign s2_iotlb_up_en_1S  = S1_en;
    assign s2_iotlb_up_en_2S  = S2_en;

    // first-stage data bus between PTW and MSI PTW
    logic                       gpaddr_is_msi;
    logic [riscv::GPPNW-1:0]    msi_vpn;
    logic                       msi_1S_2M;
    logic                       msi_1S_1G;
    riscv::pte_t                msi_gpte;

    // Init PTW
    logic   init_ptw;
    assign  init_ptw =  (iotlb_lu_miss) &
                        ((S1_en) |
                         (S2_en & ~iova_is_msi));

    // Init MSI translation
    logic   init_msi_trans;
    assign  init_msi_trans =    (gpaddr_is_msi) |
                                ((iotlb_lu_miss & mrifc_lu_miss) &
                                 (~S1_en & iova_is_msi));

    // Bare translation
    logic   bare_translation;
    assign  bare_translation =  (~S1_en) &
                                (~S2_en) &
                                (~iova_is_msi);

    // Resume and ignore (MRIF)
    logic   msiptw_ignore, mrif_handler_ignore;
    assign  ignore_request_o = (msiptw_ignore | mrif_handler_ignore);

    // Bad gpaddr propagation
    logic                       ptw_error_2S;
    logic [riscv::SVX-1:0]      ptw_bad_gpaddr;
    logic [riscv::SVX-1:0]      iotlb_bad_gpaddr;
    logic                       wrap_cause_is_guest;

    //# Device Directory Table Cache
    rv_iommu_ddtc #(
        .DDTC_ENTRIES       (DDTC_ENTRIES   ),
        .DC_WIDTH           (DC_WIDTH       )
    ) i_rv_iommu_ddtc (
        .clk_i              (clk_i          ),
        .rst_ni             (rst_ni         ),
        .flush_i            (flush_ddtc_i   ),
        .flush_dv_i         (flush_dv_i     ),
        .flush_did_i        (flush_did_i    ),
        .update_i           (ddtc_update    ),
        .up_did_i           (ddtc_up_did    ),
        .up_content_i       (ddtc_up_content),
        .lookup_i           (ddtc_access    ),
        .lu_did_i           (did_i          ),
        .lu_content_o       (ddtc_lu_content),
        .lu_hit_o           (ddtc_lu_hit    )
    );

    //# Process Directory Table Cache
    rv_iommu_pdtc #(
        .PDTC_ENTRIES       (PDTC_ENTRIES)
    ) i_rv_iommu_pdtc (
        .clk_i              (clk_i          ),
        .rst_ni             (rst_ni         ),
        .flush_i            (flush_pdtc_i   ),
        .flush_dv_i         (flush_dv_i     ),
        .flush_pv_i         (flush_pv_i     ),
        .flush_did_i        (flush_did_i    ),
        .flush_pid_i        (flush_pid_i    ),
        .update_i           (pdtc_update    ),
        .up_did_i           (pdtc_up_did    ),
        .up_pid_i           (pdtc_up_pid    ),
        .up_content_i       (pdtc_up_content),
        .lookup_i           (pdtc_access    ),
        .lu_did_i           (did_i          ),
        .lu_pid_i           (process_id     ),
        .lu_content_o       (pdtc_lu_content),
        .lu_hit_o           (pdtc_lu_hit    )
    );

    // ════════════════════════════════════════════════════════════════════
    // First-stage IOTLB (new)
    // ════════════════════════════════════════════════════════════════════
    rv_iommu_iotlb_s1 #(
        .IOTLB_S1_ENTRIES   (IOTLB_S1_ENTRIES)
    ) i_rv_iommu_iotlb_s1 (
        .clk_i              (clk_i                  ),
        .rst_ni             (rst_ni                 ),

        // Flush
        .flush_vma_i        ( flush_vma_i           ),
        .flush_gvma_i       ( flush_gvma_i          ),
        .flush_av_i         ( flush_av_i            ),
        .flush_gv_i         ( flush_gv_i            ),
        .flush_pscv_i       ( flush_pscv_i          ),
        .flush_vpn_i        ( flush_vpn_i           ),
        .flush_gscid_i      ( flush_gscid_i         ),
        .flush_pscid_i      ( flush_pscid_i         ),

        // Update
        .update_i           ( s1_iotlb_update       ),
        .up_1S_2M_i         ( iotlb_up_1S_2M        ),
        .up_1S_1G_i         ( iotlb_up_1S_1G        ),
        .up_en_1S_i         ( s1_iotlb_up_en_1S     ),
        .up_en_2S_i         ( s1_iotlb_up_en_2S     ),
        .up_vpn_i           ( iotlb_up_vpn          ),
        .up_pscid_i         ( iotlb_up_pscid        ),
        .up_gscid_i         ( iotlb_up_gscid        ),
        .up_1S_content_i    ( iotlb_up_1S_content   ),

        // Lookup
        .lookup_i           ( iotlb_access          ),
        .lu_iova_i          ( iova_i                ),
        .lu_pscid_i         ( pscid                 ),
        .lu_gscid_i         ( gscid                 ),
        .en_1S_i            ( S1_en                 ),
        .en_2S_i            ( S2_en                 ),
        .lu_1S_2M_o         ( s1_iotlb_lu_2M        ),
        .lu_1S_1G_o         ( s1_iotlb_lu_1G        ),
        .lu_hit_o           ( s1_iotlb_hit          ),
        .lu_miss_o          ( s1_iotlb_miss         ),
        .lu_1S_content_o    ( s1_iotlb_lu_pte       )
    );

    // ════════════════════════════════════════════════════════════════════
    // Second-stage IOTLB (new)
    // ════════════════════════════════════════════════════════════════════
    rv_iommu_iotlb_s2 #(
        .IOTLB_S2_ENTRIES   (IOTLB_S2_ENTRIES)
    ) i_rv_iommu_iotlb_s2 (
        .clk_i              (clk_i                  ),
        .rst_ni             (rst_ni                 ),

        // Flush
        .flush_vma_i        ( flush_vma_i           ),
        .flush_gvma_i       ( flush_gvma_i          ),
        .flush_av_i         ( flush_av_i            ),
        .flush_gv_i         ( flush_gv_i            ),
        .flush_pscv_i       ( flush_pscv_i          ),
        .flush_vpn_i        ( flush_vpn_i           ),
        .flush_gscid_i      ( flush_gscid_i         ),
        .flush_pscid_i      ( flush_pscid_i         ),

        // Update
        .update_i           ( s2_iotlb_update       ),
        .up_2S_2M_i         ( iotlb_up_2S_2M        ),
        .up_2S_1G_i         ( iotlb_up_2S_1G        ),
        .up_is_msi_i        ( iotlb_up_is_msi       ),
        .up_en_1S_i         ( s2_iotlb_up_en_1S     ),
        .up_en_2S_i         ( s2_iotlb_up_en_2S     ),
        .up_vpn_i           ( iotlb_up_vpn          ),
        .up_pscid_i         ( iotlb_up_pscid        ),
        .up_gscid_i         ( iotlb_up_gscid        ),
        .up_1S_2M_i         ( iotlb_up_1S_2M        ),  // for gppn pre-compute
        .up_1S_1G_i         ( iotlb_up_1S_1G        ),  // for gppn pre-compute
        .up_1S_content_i    ( iotlb_up_1S_content   ),  // for gppn pre-compute
        .up_2S_content_i    ( iotlb_up_2S_content   ),

        // Lookup
        .lookup_i           ( iotlb_access          ),
        .lu_iova_i          ( iova_i                ),
        .lu_pscid_i         ( pscid                 ),
        .lu_gscid_i         ( gscid                 ),
        .en_1S_i            ( S1_en                 ),
        .en_2S_i            ( S2_en                 ),
        .lu_2S_2M_o         ( s2_iotlb_lu_2M        ),
        .lu_2S_1G_o         ( s2_iotlb_lu_1G        ),
        .lu_is_msi_o        ( s2_iotlb_lu_is_msi    ),
        .lu_hit_o           ( s2_iotlb_hit          ),
        .lu_miss_o          ( s2_iotlb_miss         ),
        .lu_2S_content_o    ( s2_iotlb_lu_pte       )
    );
    
    logic flush;  // = 何もしない、 future use
    assign flush = 1'b0;
    //# Page Table Walker (unchanged from PR0)
    rv_iommu_ptw_sv39x4_pc #(
        .axi_req_t              ( axi_req_t         ),
        .axi_rsp_t              ( axi_rsp_t         ),
        .MSITrans               ( MSITrans          )
    ) i_rv_iommu_ptw_sv39x4_pc (
        .clk_i                  (clk_i              ),
        .rst_ni                 (rst_ni             ),
        .init_ptw_i             (init_ptw           ),
        .ptw_active_o           (ptw_active         ),
        .ptw_error_o            (ptw_error          ),
        .ptw_error_2S_o         (ptw_error_2S       ),
        .ptw_error_2S_int_o     (ptw_error_2S_int   ),
        .cause_code_o           (ptw_cause_code     ),
        .en_1S_i                (ptw_en_1S          ),
        .en_2S_i                (ptw_en_2S          ),
        .is_store_i             (is_store           ),
        .is_rx_i                (is_rx              ),
        .priv_lvl_i             (priv_lvl_i         ),
        .sum_i                  (pdtc_lu_content.ta.sum     ),
        .mem_resp_i             (ptw_axi_resp_i     ),
        .mem_req_o              (ptw_axi_req_o      ),
        .update_o               (ptw_update         ),
        .up_1S_2M_o             (ptw_up_1S_2M       ),
        .up_1S_1G_o             (ptw_up_1S_1G       ),
        .up_2S_2M_o             (ptw_up_2S_2M       ),
        .up_2S_1G_o             (ptw_up_2S_1G       ),
        .up_vpn_o               (ptw_up_vpn         ),
        .up_pscid_o             (ptw_up_pscid       ),
        .up_gscid_o             (ptw_up_gscid       ),
        .up_1S_content_o        (ptw_up_1S_content  ),
        .up_2S_content_o        (ptw_up_2S_content  ),
        .req_iova_i             (iova_i             ),
        .pscid_i                (pscid              ),
        .gscid_i                (gscid              ),
        .msi_en_i               (msi_enabled        ),
        .msi_addr_mask_i        (msi_addr_mask      ),
        .msi_addr_pattern_i     (msi_addr_pattern   ),
        .gpaddr_is_msi_o        (gpaddr_is_msi      ),
        .msi_vpn_o              (msi_vpn            ),
        .msi_1S_2M_o            (msi_1S_2M          ),
        .msi_1S_1G_o            (msi_1S_1G          ),
        .msi_gpte_o             (msi_gpte           ),
        .cdw_implicit_access_i  (cdw_implicit_access),
        .pdt_gppn_i             (pdt_gppn           ),
        .cdw_done_o             (cdw_done           ),
        .flush_i                (flush              ),
        .flush_cdw_o            (flush_cdw          ),
        .iosatp_ppn_i           (iosatp_ppn         ),
        .iohgatp_ppn_i          (ptw_iohgatp_ppn    ),
        .bad_gpaddr_o           (ptw_bad_gpaddr     )
    );

    //# MSI Address Translation support
    generate
    if (MSITrans != rv_iommu::MSI_DISABLED) begin : gen_msi_support

        rv_iommu::dc_ext_t dc_ext;
        assign dc_ext = rv_iommu::dc_ext_t'(ddtc_lu_content);

        assign msi_enabled      = (dc_ext.msiptp.mode != 4'b0000);
        assign msi_addr_mask    = dc_ext.msi_addr_mask.mask[riscv::GPPNW-1:0];
        assign msi_addr_pattern = dc_ext.msi_addr_pattern.pattern[riscv::GPPNW-1:0];

        assign iova_is_msi      =   (msi_enabled) &
                                    (is_store) &
                                    ((iova_i[(riscv::GPLEN-1):12] & ~msi_addr_mask) == (msi_addr_pattern & ~msi_addr_mask));

        rv_iommu_msiptw #(
            .MSITrans           (MSITrans  ),
            .axi_req_t          (axi_req_t ),
            .axi_rsp_t          (axi_rsp_t )
        ) i_rv_iommu_msiptw (
            .clk_i  (clk_i),
            .rst_ni (rst_ni),
            .mem_resp_i         ( msiptw_axi_resp_i     ),
            .mem_req_o          ( msiptw_axi_req_o      ),
            .init_msi_trans_i   ( init_msi_trans & ~req_dbg_i ),
            .msiptw_active_o    ( msiptw_active         ),
            .ignore_o           ( msiptw_ignore         ),
            .req_iova_i         ( iova_i                ),
            .en_1S_i            ( S1_en                 ),
            .is_rx_i            ( is_rx                 ),
            .vpn_i              ( msi_vpn               ),
            .pscid_i            ( pscid                 ),
            .gscid_i            ( gscid                 ),
            .is_1S_2M_i         ( msi_1S_2M             ),
            .is_1S_1G_i         ( msi_1S_1G             ),
            .gpte_i             ( msi_gpte              ),
            .msiptp_ppn_i       ( dc_ext.msiptp.ppn     ),
            .msi_addr_mask_i    ( msi_addr_mask         ),
            .vpn_o              ( msi_up_vpn            ),
            .pscid_o            ( msi_up_pscid          ),
            .gscid_o            ( msi_up_gscid          ),
            .is_1S_2M_o         ( msi_up_1S_2M          ),
            .is_1S_1G_o         ( msi_up_1S_1G          ),
            .content_1S_o       ( msi_up_1S_content     ),
            .iotlb_update_o     ( msi_update            ),
            .iotlb_msi_content_o( msi_up_content        ),
            .mrifc_update_o     ( mrifc_update          ),
            .mrifc_msi_content_o( mrifc_up_msi_content  ),
            .error_o            ( msiptw_error          ),
            .cause_o            ( msiptw_cause_code     )
        );
    end : gen_msi_support

    else begin : gen_msi_support_disabled

        assign msi_enabled          = 1'b0;
        assign msi_addr_mask        = '0;
        assign msi_addr_pattern     = '0;
        assign iova_is_msi          = 1'b0;
        assign msiptw_axi_req_o     = '0;
        assign msiptw_active        = 1'b0;
        assign msiptw_ignore        = 1'b0;
        assign msi_up_vpn           = '0;
        assign msi_up_pscid         = '0;
        assign msi_up_gscid         = '0;
        assign msi_up_1S_2M         = '0;
        assign msi_up_1S_1G         = '0;
        assign msi_up_1S_content    = '0;
        assign msi_update           = 1'b0;
        assign msi_up_content       = '0;
        assign mrifc_update         = 1'b0;
        assign mrifc_up_msi_content = '0;
        assign msiptw_error         = 1'b0;
        assign msiptw_cause_code    = '0;

    end : gen_msi_support_disabled
    endgenerate

    //# MRIF Support for MSI Translation
    generate
    if (MSITrans == rv_iommu::MSI_FLAT_MRIF) begin : gen_mrif_support

        rv_iommu_mrif_handler #(
            .axi_req_t          (axi_req_t ),
            .axi_rsp_t          (axi_rsp_t )
        ) i_rv_iommu_mrif_handler (
            .clk_i          (clk_i),
            .rst_ni         (rst_ni),
            .mem_resp_i     (mrif_handler_axi_resp_i),
            .mem_req_o      (mrif_handler_axi_req_o),
            .init_mrif_i    (mrifc_lu_hit & msi_data_valid_i),
            .ignore_o       (mrif_handler_ignore),
            .int_id_i       (msi_data_i),
            .mrif_addr_i    (mrifc_lu_msi_content.addr),
            .notice_nid_i   (mrifc_lu_msi_content.nid),
            .notice_ppn_i   (mrifc_lu_msi_content.nppn),
            .error_o        (mrif_handler_error),
            .cause_o        (mrif_handler_cause_code)
        );

        rv_iommu_mrifc #(
            .MRIFC_ENTRIES  (MRIFC_ENTRIES)
        ) i_rv_iommu_mrifc (
            .clk_i              (clk_i),
            .rst_ni             (rst_ni),
            .flush_vma_i        (flush_vma_i            ),
            .flush_gvma_i       (flush_gvma_i           ),
            .flush_av_i         (flush_av_i             ),
            .flush_gv_i         (flush_gv_i             ),
            .flush_pscv_i       (flush_pscv_i           ),
            .flush_vpn_i        (flush_vpn_i            ),
            .flush_gscid_i      (flush_gscid_i          ),
            .flush_pscid_i      (flush_pscid_i          ),
            .update_i           (mrifc_update           ),
            .up_1S_2M_i         (msi_up_1S_2M           ),
            .up_1S_1G_i         (msi_up_1S_1G           ),
            .up_vpn_i           (msi_up_vpn             ),
            .up_pscid_i         (msi_up_pscid           ),
            .up_gscid_i         (msi_up_gscid           ),
            .up_1S_content_i    (msi_up_1S_content      ),
            .up_msi_content_i   (mrifc_up_msi_content   ),
            .lookup_i           (iotlb_access           ),
            .lu_iova_i          (iova_i                 ),
            .lu_pscid_i         (pscid                  ),
            .lu_gscid_i         (gscid                  ),
            .en_1S_i            (S1_en                  ),
            .en_2S_i            (S2_en                  ),
            .lu_hit_o           (mrifc_lu_hit           ),
            .lu_miss_o          (mrifc_lu_miss          ),
            .lu_1S_content_o    (mrifc_lu_1S_content    ),
            .lu_msi_content_o   (mrifc_lu_msi_content   )
        );
    end : gen_mrif_support

    else begin : gen_mrif_support_disabled

        assign mrif_handler_axi_req_o   = '0;
        assign mrif_handler_ignore      = 1'b0;
        assign mrif_handler_error       = 1'b0;
        assign mrif_handler_cause_code  = '0;
        assign mrifc_lu_hit             = 1'b0;
        assign mrifc_lu_miss            = 1'b0;
        assign mrifc_lu_1S_content      = '0;
        assign mrifc_lu_msi_content     = '0;
    end : gen_mrif_support_disabled
    endgenerate

    //# DDT walker
    rv_iommu_ddtw #(
        .MSITrans   (MSITrans),
        .axi_req_t  (axi_req_t),
        .axi_rsp_t  (axi_rsp_t),
        .DC_WIDTH   (DC_WIDTH)
    ) i_rv_iommu_ddtw (
        .clk_i                  (clk_i),
        .rst_ni                 (rst_ni),
        .active_o               (ddtw_active),
        .error_o                (ddtw_error),
        .cause_code_o           (ddtw_cause_code),
        .caps_ats_i             (capabilities_i.ats.q),
        .caps_t2gpa_i           (capabilities_i.t2gpa.q),
        .caps_pd20_i            (capabilities_i.pd20.q),
        .caps_pd17_i            (capabilities_i.pd17.q),
        .caps_pd8_i             (capabilities_i.pd8.q),
        .caps_sv39_i            (capabilities_i.sv39.q),
        .caps_sv39x4_i          (capabilities_i.sv39x4.q),
        .caps_msi_flat_i        (capabilities_i.msi_flat.q),
        .caps_amo_hwad_i        (capabilities_i.amo_hwad.q),
        .caps_end_i             (capabilities_i.endi.q),
        .fctl_be_i              (fctl_i.be.q),
        .mem_resp_i             (ddtw_axi_resp),
        .mem_req_o              (ddtw_axi_req),
        .update_dc_o            (ddtc_update),
        .up_did_o               (ddtc_up_did),
        .up_dc_content_o        (ddtc_up_content),
        .req_did_i              (did_i),
        .init_i                 (ddtc_access && ~ddtc_lu_hit),
        .ddtp_ppn_i             (ddtp_i.ppn.q),
        .ddtp_mode_i            (ddtp_i.iommu_mode.q),
        .en_stage2_i            (S2_en),
        .ptw_done_i             (cdw_done),
        .flush_i                (flush_cdw),
        .pdt_ppn_i              (iotlb_up_2S_content.ppn),
        .cdw_implicit_access_o  (ddtw_implicit_access),
        .pdt_gppn_o             (ddtw_pdt_gppn),
        .iohgatp_ppn_fw_o       (ddtw_iohgatp_ppn_fw)
    );

    //# PDT walker
    rv_iommu_pdtw #(
        .axi_req_t  (axi_req_t),
        .axi_rsp_t  (axi_rsp_t)
    ) i_rv_iommu_pdtw (
        .clk_i                  (clk_i),
        .rst_ni                 (rst_ni),
        .active_o               (pdtw_active),
        .error_o                (pdtw_error),
        .cause_code_o           (pdtw_cause_code),
        .mem_resp_i             (pdtw_axi_resp),
        .mem_req_o              (pdtw_axi_req),
        .update_pc_o            (pdtc_update),
        .up_did_o               (pdtc_up_did),
        .up_pid_o               (pdtc_up_pid),
        .up_pc_content_o        (pdtc_up_content),
        .req_did_i              (did_i),
        .req_pid_i              (process_id),
        .init_i                 (pdtc_access && ~pdtc_lu_hit),
        .en_stage2_i            (S2_en),
        .pdtp_ppn_i             (dc_base.fsc.ppn),
        .pdtp_mode_i            (dc_base.fsc.mode),
        .ptw_done_i             (cdw_done),
        .flush_i                (flush_cdw),
        .pdt_ppn_i              (iotlb_up_2S_content.ppn),
        .cdw_implicit_access_o  (pdtw_implicit_access),
        .pdt_gppn_o             (pdtw_pdt_gppn)
    );

    //# CDW AXI mux (2 walker's AXI master を 1 本に集約)
    rv_iommu_cdw_axi_mux #(
        .axi_req_t      (axi_req_t),
        .axi_rsp_t      (axi_rsp_t)
    ) i_cdw_axi_mux (
        .ddtw_active_i          (ddtw_active),
        .ddtw_axi_req_i         (ddtw_axi_req),
        .ddtw_axi_resp_o        (ddtw_axi_resp),
        .pdtw_active_i          (pdtw_active),
        .pdtw_axi_req_i         (pdtw_axi_req),
        .pdtw_axi_resp_o        (pdtw_axi_resp),
        .cdw_axi_req_o          (cdw_axi_req_o),
        .cdw_axi_resp_i         (cdw_axi_resp_i)
    );

    //# Translation logic (unchanged from PR0)
    always_comb begin : translation

        ddtc_access         = 1'b0;
        pdtc_access         = 1'b0;
        gscid               = '0;
        pscid               = '0;
        iosatp_ppn          = '0;
        iohgatp_ppn         = '0;
        iotlb_access        = 1'b0;
        wrap_cause_code     = '0;
        wrap_error          = 1'b0;
        trans_valid_o       = 1'b0;
        spaddr_o            = '0;
        report_always       = 1'b0;

        if (req_trans_i | req_dbg_i) begin

            if (ddtp_i.iommu_mode.q == 4'b0000) begin
                wrap_cause_code    = rv_iommu::ALL_INB_TRANSACTIONS_DISALLOWED;
                wrap_error   = 1'b1;
                report_always   = 1'b1;
            end

            else if (ddtp_i.iommu_mode.q == 4'b0001) begin
                if (is_translated || is_pcie_tr_req) begin
                    wrap_cause_code    = rv_iommu::TRANS_TYPE_DISALLOWED;
                    wrap_error   = 1'b1;
                    report_always   = 1'b1;
                end
                else begin
                    trans_valid_o   = 1'b1;
                    spaddr_o        = iova_i[riscv::PLEN-1:0];
                end
            end

            else if ((ddtp_i.iommu_mode.q == 4'b0011 && (|did_i[23:15])) || (ddtp_i.iommu_mode.q == 4'b0010 && (|did_i[23:6]))) begin
                wrap_cause_code = rv_iommu::TRANS_TYPE_DISALLOWED;
                wrap_error   = 1'b1;
                report_always   = 1'b1;
            end

            else ddtc_access = 1'b1;
        end

        if (ddtc_lu_hit) begin

            if (((is_translated || is_pcie_tr_req) && !dc_base.tc.en_ats) ||
                (pv_i && !dc_base.tc.pdtv) ||
                (pv_i && dc_base.tc.pdtv && pid_wider_than_supported)) begin

                wrap_cause_code  = rv_iommu::TRANS_TYPE_DISALLOWED;
                wrap_error = 1'b1;
            end

            else begin

                if (is_translated) begin
                    if (!dc_base.tc.t2gpa) begin
                        trans_valid_o   = 1'b1;
                        spaddr_o        = iova_i[riscv::PLEN-1:0];
                    end
                    else begin
                        gscid           = dc_base.iohgatp.gscid;
                        iohgatp_ppn     = dc_base.iohgatp.ppn;
                        if (iova_s2_ncanon) begin
                            wrap_error      = 1'b1;
                            if (is_store) wrap_cause_code = rv_iommu::STORE_GUEST_PAGE_FAULT;
                            else          wrap_cause_code = rv_iommu::LOAD_GUEST_PAGE_FAULT;
                        end else begin
                            iotlb_access    = 1'b1;
                        end
                    end
                end

                else begin
                    if (!dc_base.tc.pdtv) begin
                        gscid           = dc_base.iohgatp.gscid;
                        pscid           = dc_base.ta.pscid;
                        iohgatp_ppn     = dc_base.iohgatp.ppn;
                        iosatp_ppn      = dc_base.fsc.ppn;
                        if (S1_en && iova_s1_ncanon) begin
                            wrap_error      = 1'b1;
                            if (is_store) wrap_cause_code = rv_iommu::STORE_PAGE_FAULT;
                            else          wrap_cause_code = rv_iommu::LOAD_PAGE_FAULT;
                        end else if (!S1_en && S2_en && iova_s2_ncanon) begin
                            wrap_error      = 1'b1;
                            if (is_store) wrap_cause_code = rv_iommu::STORE_GUEST_PAGE_FAULT;
                            else          wrap_cause_code = rv_iommu::LOAD_GUEST_PAGE_FAULT;
                        end else begin
                            iotlb_access    = 1'b1;
                        end
                    end
                    else begin
                        if ((!pv_i && !dc_base.tc.dpe) || (dc_base.fsc.mode == 4'b0000)) begin
                            gscid           = dc_base.iohgatp.gscid;
                            iohgatp_ppn     = dc_base.iohgatp.ppn;
                            if (S2_en && iova_s2_ncanon) begin
                                wrap_error      = 1'b1;
                                if (is_store) wrap_cause_code = rv_iommu::STORE_GUEST_PAGE_FAULT;
                                else          wrap_cause_code = rv_iommu::LOAD_GUEST_PAGE_FAULT;
                            end else begin
                                iotlb_access    = 1'b1;
                            end
                        end
                        else begin
                            iohgatp_ppn = dc_base.iohgatp.ppn;
                            pdtc_access = 1'b1;
                        end
                    end
                end
            end

            if (pdtc_lu_hit) begin
                if (priv_lvl_i && !pdtc_lu_content.ta.ens) begin
                    wrap_cause_code    = rv_iommu::TRANS_TYPE_DISALLOWED;
                    wrap_error   = 1'b1;
                end
                else begin
                    gscid           = dc_base.iohgatp.gscid;
                    pscid           = pdtc_lu_content.ta.pscid;
                    iohgatp_ppn     = dc_base.iohgatp.ppn;
                    iosatp_ppn      = pdtc_lu_content.fsc.ppn;
                    if (S1_en && iova_s1_ncanon) begin
                        wrap_error      = 1'b1;
                        if (is_store) wrap_cause_code = rv_iommu::STORE_PAGE_FAULT;
                        else          wrap_cause_code = rv_iommu::LOAD_PAGE_FAULT;
                    end else if (!S1_en && S2_en && iova_s2_ncanon) begin
                        wrap_error      = 1'b1;
                        if (is_store) wrap_cause_code = rv_iommu::STORE_GUEST_PAGE_FAULT;
                        else          wrap_cause_code = rv_iommu::LOAD_GUEST_PAGE_FAULT;
                    end else begin
                    iotlb_access    = 1'b1;
                    end
                end
            end

            if (iotlb_lu_hit) begin
                trans_valid_o   = 1'b1;

                if  ((!is_store && !is_rx && (!iotlb_lu_1S_content.r && S1_en)                                        ) ||        // (0)
                    (is_store && (!iotlb_lu_1S_content.w && S1_en)                                                  ) ||        // (1)
                        (is_rx && (!iotlb_lu_1S_content.x && S1_en)                                                 ) ||        // (2)
                        ((!priv_lvl_i) && !iotlb_lu_1S_content.u && S1_en                                           ) ||        // (3)
                        (priv_lvl_i && iotlb_lu_1S_content.u && (!pdtc_lu_content.ta.sum || iotlb_lu_1S_content.x) && S1_en  )  // (4)
                    ) begin
                        if (is_store)   wrap_cause_code = rv_iommu::STORE_PAGE_FAULT;
                        else            wrap_cause_code = rv_iommu::LOAD_PAGE_FAULT;
                        wrap_error      = 1'b1;
                        trans_valid_o   = 1'b0;
                end

                else if ((!is_store && !is_rx && (!iotlb_lu_2S_content.r && S2_en)) ||
                        (is_store && (!iotlb_lu_2S_content.w && S2_en))             ||
                            (is_rx && (!iotlb_lu_2S_content.x && S2_en))
                        ) begin
                        if (is_store)   wrap_cause_code = rv_iommu::STORE_GUEST_PAGE_FAULT;
                        else            wrap_cause_code = rv_iommu::LOAD_GUEST_PAGE_FAULT;
                        wrap_error     = 1'b1;
                        trans_valid_o   = 1'b0;
                end

                else begin
                    spaddr_o = {((S2_en || iotlb_lu_is_msi) ? (iotlb_lu_2S_content.ppn) : (iotlb_lu_1S_content.ppn)), iova_i[11:0]};

                    if (S1_en && S2_en) begin
                        case ({iotlb_lu_1S_2M, iotlb_lu_1S_1G, iotlb_lu_2S_2M, iotlb_lu_2S_1G})
                            4'b0010:    spaddr_o[20:12] = iotlb_lu_1S_content.ppn[20:12];
                            4'b1010, 4'b0110:   spaddr_o[20:12] = iova_i[20:12];
                            4'b0001:    spaddr_o[29:12] = iotlb_lu_1S_content.ppn[29:12];
                            4'b0101:    spaddr_o[29:12] = iova_i[29:12];
                            4'b1001:    spaddr_o[29:12] = {iotlb_lu_1S_content.ppn[29:21], iova_i[20:12]};
                            default:;
                        endcase
                    end

                    else begin
                        if ((iotlb_lu_2S_1G) || (iotlb_lu_1S_1G & ~iotlb_lu_is_msi))   spaddr_o[29:12] = iova_i[29:12];
                        if ((iotlb_lu_2S_2M) || (iotlb_lu_1S_2M & ~iotlb_lu_is_msi))   spaddr_o[20:12] = iova_i[20:12];
                    end

                    if (req_dbg_i) begin
                        if (iotlb_lu_2S_2M || iotlb_lu_1S_2M)       spaddr_o[20:12] = {1'b0, {8{1'b1}}};
                        else if (iotlb_lu_2S_1G || iotlb_lu_1S_1G)  spaddr_o[29:12] = {1'b0, {17{1'b1}}};
                    end
                end
            end

            if ((ddtc_lu_hit) &&
                (pdtc_lu_hit || !dc_base.tc.pdtv || !(pv_i || dc_base.tc.dpe)) &&
                (bare_translation)) begin
                trans_valid_o   = 1'b1;
                spaddr_o        = iova_i[riscv::PLEN-1:0];
            end
        end

        if (init_msi_trans & req_dbg_i) begin
            wrap_cause_code = rv_iommu::TRANS_TYPE_DISALLOWED;
            wrap_error      = 1'b1;
        end
    end : translation

    //# Error routing
    always_comb begin : error_routing

        trans_error_o   =  ((wrap_error)         |
                           (cdw_error)          |
                           (ptw_error)          |
                           (msiptw_error)       |
                           (mrif_handler_error) |
                           (msi_write_error_i));

        priority case (1'b1)
            wrap_error:         cause_code_o = wrap_cause_code;
            cdw_error:          cause_code_o = cdw_cause_code;
            ptw_error:          cause_code_o = ptw_cause_code;
            msiptw_error:       cause_code_o = msiptw_cause_code;
            mrif_handler_error: cause_code_o = mrif_handler_cause_code;
            msi_write_error_i:  cause_code_o = rv_iommu::MSI_ST_ACCESS_FAULT;
            default:            cause_code_o = '0;
        endcase
    end : error_routing

    //# Guest page fault GPA reporting
    assign wrap_cause_is_guest = (wrap_cause_code == rv_iommu::LOAD_GUEST_PAGE_FAULT)
                              || (wrap_cause_code == rv_iommu::STORE_GUEST_PAGE_FAULT);

    always_comb begin : iotlb_bad_gpaddr_compute
        iotlb_bad_gpaddr = '0;
        if (S2_en && !S1_en) begin
            iotlb_bad_gpaddr = iova_i[riscv::SVX-1:0];
        end
        else if (S1_en && S2_en) begin
            if (iotlb_lu_1S_1G)
                iotlb_bad_gpaddr = {iotlb_lu_1S_content.ppn[riscv::GPPNW-1:18], iova_i[29:0]};
            else if (iotlb_lu_1S_2M)
                iotlb_bad_gpaddr = {iotlb_lu_1S_content.ppn[riscv::GPPNW-1:9],  iova_i[20:0]};
            else
                iotlb_bad_gpaddr = {iotlb_lu_1S_content.ppn[riscv::GPPNW-1:0],  iova_i[11:0]};
        end
    end : iotlb_bad_gpaddr_compute

    assign is_guest_pf_o = ptw_error_2S | (wrap_error & wrap_cause_is_guest);

    assign bad_gpaddr_o  = ptw_error_2S
                         ? ptw_bad_gpaddr
                         : ((wrap_error & wrap_cause_is_guest) ? iotlb_bad_gpaddr : '0);

endmodule