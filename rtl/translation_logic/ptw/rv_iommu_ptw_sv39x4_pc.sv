// Copyright © 2026 (PR-cdw-split v4, TW-compatible adapter)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: PTW wrapper = pt_walker + walk_ctrl + TW 接続 adapter
//
//   既存 TW の port 接続をそのまま受け取れるように、 旧 port 名を維持。
//   MSI 関連は stub (= MSI_DISABLED 前提で出力は 0)。
//   pscid/gscid は wrapper 内で snapshot + commit のときに同時に出力する。

module rv_iommu_ptw_sv39x4_pc
    import rv_iommu::*;
#(
    parameter rv_iommu::msi_trans_t MSITrans = rv_iommu::MSI_DISABLED,
    parameter type axi_req_t = logic,
    parameter type axi_rsp_t = logic
) (
    input  logic                                clk_i,
    input  logic                                rst_ni,

    // ── From TW (translation request) ───────────────────────────────
    input  logic                                init_ptw_i,
    output logic                                ptw_active_o,
    output logic                                ptw_error_o,
    output logic                                ptw_error_2S_o,       // 通常 walk 中の S2 error
    output logic                                ptw_error_2S_int_o,   // implicit walk 中の S2 error
    output logic [rv_iommu::CAUSE_LEN-1:0]      cause_code_o,
    output logic [riscv::SVX-1:0]               bad_gpaddr_o,

    input  logic                                en_1S_i,
    input  logic                                en_2S_i,
    input  logic                                is_store_i,
    input  logic                                is_rx_i,
    input  logic                                priv_lvl_i,
    input  logic                                sum_i,

    input  logic [riscv::VLEN-1:0]              req_iova_i,
    input  logic [riscv::PPNW-1:0]              iosatp_ppn_i,
    input  logic [riscv::PPNW-1:0]              iohgatp_ppn_i,
    input  logic [19:0]                         pscid_i,
    input  logic [15:0]                         gscid_i,

    // ── AXI master ──────────────────────────────────────────────────
    input  axi_rsp_t                            mem_resp_i,
    output axi_req_t                            mem_req_o,

    // ── IOTLB update ────────────────────────────────────────────────
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

    // ── MSI translation (stubbed for now) ───────────────────────────
    input  logic                                msi_en_i,
    input  rv_iommu::msi_addr_mask_t            msi_addr_mask_i,
    input  rv_iommu::msi_addr_pattern_t         msi_addr_pattern_i,
    output logic                                gpaddr_is_msi_o,
    output logic [riscv::GPPNW-1:0]             msi_vpn_o,
    output logic                                msi_1S_2M_o,
    output logic                                msi_1S_1G_o,
    // msi_pte_t は package に無いので generic 128bit (= MSI PTE は 16B)
    output logic [127:0]                        msi_gpte_o,

    // ── CDW interface ───────────────────────────────────────────────
    input  logic                                cdw_implicit_access_i,
    input  logic [riscv::GPPNW-1:0]             pdt_gppn_i,
    output logic                                cdw_done_o,
    output logic                                flush_cdw_o,

    input  logic                                flush_i
);

    // ── pt_walker handshake ──────────────────────────────────────────
    logic                       walker_req_valid;
    logic                       walker_req_ready;
    logic [riscv::PLEN-1:0]     walker_req_addr;
    logic                       walker_rsp_valid;
    logic                       walker_rsp_ready;
    logic [63:0]                walker_rsp_data;
    logic                       walker_rsp_error;

    // ── pscid / gscid snapshot ───────────────────────────────────────
    logic [19:0]                pscid_q;
    logic [15:0]                gscid_q;
    logic                       snapshot_en;
    logic                       is_implicit_q;  // ★ 今 walk が implicit (= CDW から) か?
    logic init_ptw_q, cdw_impl_q;
    assign snapshot_en = (init_ptw_i && !init_ptw_q) ||
                         (cdw_implicit_access_i && !cdw_impl_q);

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            pscid_q       <= '0;
            gscid_q       <= '0;
            init_ptw_q    <= 1'b0;
            cdw_impl_q    <= 1'b0;
            is_implicit_q <= 1'b0;
        end else begin
            init_ptw_q <= init_ptw_i;
            cdw_impl_q <= cdw_implicit_access_i;
            if (snapshot_en) begin
                pscid_q       <= pscid_i;
                gscid_q       <= gscid_i;
                // implicit_access の rising edge なら implicit mode 開始
                is_implicit_q <= cdw_implicit_access_i && !cdw_impl_q;
            end
            // PTW が IDLE に戻ったら is_implicit_q を落とす
            else if (!walk_active) begin
                is_implicit_q <= 1'b0;
            end
        end
    end

    // ── walk_ctrl 出力 (= raw 信号) ─────────────────────────────────
    logic                                walk_update_iotlb;
    logic [riscv::GPPNW-1:0]             walk_update_vpn;
    riscv::pte_t                         walk_update_1S_content;
    riscv::pte_t                         walk_update_2S_content;
    logic                                walk_update_1S_2M, walk_update_1S_1G;
    logic                                walk_update_2S_2M, walk_update_2S_1G;
    logic                                walk_update_is_msi;
    logic                                walk_ptw_done;
    logic [riscv::PPNW-1:0]              walk_pdt_ppn;
    logic                                walk_error;
    logic                                walk_error_2S;
    logic [rv_iommu::CAUSE_LEN-1:0]      walk_cause;
    logic [riscv::SVX-1:0]               walk_bad_gpaddr;
    logic                                walk_active;

    // ── pt_walker (= 純粋 AXI read engine) ──────────────────────────
    rv_iommu_pt_walker #(
        .axi_req_t (axi_req_t),
        .axi_rsp_t (axi_rsp_t)
    ) i_pt_walker (
        .clk_i           (clk_i),
        .rst_ni          (rst_ni),
        .req_valid_i     (walker_req_valid),
        .req_ready_o     (walker_req_ready),
        .req_addr_i      (walker_req_addr),
        .rsp_valid_o     (walker_rsp_valid),
        .rsp_ready_i     (walker_rsp_ready),
        .rsp_data_o      (walker_rsp_data),
        .rsp_error_o     (walker_rsp_error),
        .mem_resp_i      (mem_resp_i),
        .mem_req_o       (mem_req_o)
    );

    // ── walk_ctrl (= orchestration only) ────────────────────────────
    rv_iommu_walk_ctrl i_walk_ctrl (
        .clk_i                  (clk_i),
        .rst_ni                 (rst_ni),
        .init_i                 (init_ptw_i),
        .cdw_implicit_access_i  (cdw_implicit_access_i),
        .flush_i                (flush_i),
        .iova_i                 (req_iova_i),
        .is_store_i             (is_store_i),
        .is_rx_i                (is_rx_i),
        .priv_lvl_i             (priv_lvl_i),
        .sum_i                  (sum_i),
        .en_stage1_i            (en_1S_i),
        .en_stage2_i            (en_2S_i),
        .iosatp_ppn_i           (iosatp_ppn_i),
        .iosatp_mode_i          (4'b0000),    // unused in walk_ctrl v4 (= sv39 固定)
        .iohgatp_ppn_i          (iohgatp_ppn_i),
        .iohgatp_mode_i         (4'b0000),    // unused
        .cdw_pdt_gppn_i         (pdt_gppn_i),
        .walker_req_valid_o     (walker_req_valid),
        .walker_req_ready_i     (walker_req_ready),
        .walker_req_addr_o      (walker_req_addr),
        .walker_rsp_valid_i     (walker_rsp_valid),
        .walker_rsp_ready_o     (walker_rsp_ready),
        .walker_rsp_data_i      (walker_rsp_data),
        .walker_rsp_error_i     (walker_rsp_error),
        .update_iotlb_o         (walk_update_iotlb),
        .update_vpn_o           (walk_update_vpn),
        .update_1S_content_o    (walk_update_1S_content),
        .update_2S_content_o    (walk_update_2S_content),
        .update_1S_2M_o         (walk_update_1S_2M),
        .update_1S_1G_o         (walk_update_1S_1G),
        .update_2S_2M_o         (walk_update_2S_2M),
        .update_2S_1G_o         (walk_update_2S_1G),
        .update_is_msi_o        (walk_update_is_msi),
        .ptw_done_o             (walk_ptw_done),
        .pdt_ppn_o              (walk_pdt_ppn),
        .ptw_error_o            (walk_error),
        .ptw_error_2S_o         (walk_error_2S),
        .cause_code_o           (walk_cause),
        .bad_gpaddr_o           (walk_bad_gpaddr),
        .active_o               (walk_active)
    );

    // ── 旧 port にマッピング ────────────────────────────────────────
    assign ptw_active_o       = walk_active;
    assign ptw_error_o        = walk_error;
    // ★ S2 error を 「通常 walk 中」 と 「implicit walk 中」 で分ける
    assign ptw_error_2S_o     = walk_error_2S && !is_implicit_q;
    assign ptw_error_2S_int_o = walk_error_2S &&  is_implicit_q;
    assign cause_code_o       = walk_cause;
    assign bad_gpaddr_o       = walk_bad_gpaddr;

    assign update_o           = walk_update_iotlb;
    assign up_1S_2M_o         = walk_update_1S_2M;
    assign up_1S_1G_o         = walk_update_1S_1G;
    assign up_2S_2M_o         = walk_update_2S_2M;
    assign up_2S_1G_o         = walk_update_2S_1G;
    assign up_vpn_o           = walk_update_vpn;
    assign up_pscid_o         = pscid_q;
    assign up_gscid_o         = gscid_q;
    assign up_1S_content_o    = walk_update_1S_content;
    assign up_2S_content_o    = walk_update_2S_content;

    // ── MSI stub (= MSI_DISABLED 前提で 0 出力) ─────────────────────
    assign gpaddr_is_msi_o    = 1'b0;
    assign msi_vpn_o          = '0;
    assign msi_1S_2M_o        = 1'b0;
    assign msi_1S_1G_o        = 1'b0;
    assign msi_gpte_o         = '0;

    // ── CDW handshake ────────────────────────────────────────────────
    assign cdw_done_o         = walk_ptw_done;
    // PTW error が implicit-access walk 中に起きたら CDW に abort 通知
    assign flush_cdw_o        = walk_error;

    // ── 未使用入力 (= MSI 関連、 lint で unused 扱い OK) ────────────
    logic _unused_msi;
    assign _unused_msi = msi_en_i | (|msi_addr_mask_i) | (|msi_addr_pattern_i);

endmodule