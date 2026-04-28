// =============================================================================
// rv_iommu_tw_sv39x4_pc_wrapper.sv
//
// Translation Wrapper 検証用テストラッパ (Force 方式)
//
// 構成:
//   - rv_iommu_tw_sv39x4_pc を内包 (MSI 無効化)
//   - コメントアウトされたポートは /* unused */ として tie-off
//   - PTW サブモジュール (rv_iommu_ptw_sv39x4_pc) の以下の入力を
//     force_ptw_en_i=1 の間 force で駆動:
//       * init_ptw_i
//       * en_1S_i
//       * en_2S_i
//       * iosatp_ppn_i
//       * iohgatp_ppn_i
//
// 階層パス:
//   rv_iommu_tw_test_wrapper
//     └─ i_dut  (rv_iommu_tw_sv39x4_pc)
//          └─ i_rv_iommu_ptw_sv39x4_pc  (rv_iommu_ptw_sv39x4_pc)
// =============================================================================

`timescale 1ns/1ps

module rv_iommu_tw_test_wrapper #(
    parameter int unsigned  IOTLB_ENTRIES = 4,
    parameter int unsigned  DDTC_ENTRIES  = 4,
    parameter int unsigned  PDTC_ENTRIES  = 4,
    parameter int unsigned  MRIFC_ENTRIES = 4,

    parameter type          axi_req_t     = logic,
    parameter type          axi_rsp_t     = logic,

    parameter logic [23:0]  TEST_DID      = 24'h000001,
    parameter logic [19:0]  TEST_PID      = 20'h00001,
    parameter logic [43:0]  DDT_ROOT_PPN  = 44'h0000_0000_0100
) (
    input  logic    clk_i,
    input  logic    rst_ni,

    // -- Trigger translation --
    // input  logic    req_trans_i,    /* unused */
    // input  logic    req_dbg_i,      /* unused */

    // -- Translation request data --
    // input  logic [23:0]            did_i,    /* unused */
    // input  logic                   pv_i,     /* unused */
    // input  logic [19:0]            pid_i,    /* unused */
    // input  logic [riscv::VLEN-1:0] iova_i,   /* unused */
    // output logic [15:0]            gscid_o,  /* unused */
    // output logic [19:0]            pscid_o,  /* unused */

    input  logic [rv_iommu::TTYP_LEN-1:0]   trans_type_i,
    input  logic                             priv_lvl_i,

    // -- AXI: CDW --
    // input  axi_rsp_t    cdw_axi_resp_i,   /* unused */
    // output axi_req_t    cdw_axi_req_o,    /* unused */

    // -- AXI: PTW --
    input  axi_rsp_t    ptw_axi_resp_i,
    output axi_req_t    ptw_axi_req_o,

    // -- AXI: MSI PTW --
    // input  axi_rsp_t    msiptw_axi_resp_i,   /* unused */
    // output axi_req_t    msiptw_axi_req_o,    /* unused */

    // -- AXI: MRIF handler --
    // input  axi_rsp_t    mrif_handler_axi_resp_i,   /* unused */
    // output axi_req_t    mrif_handler_axi_req_o,    /* unused */

    // -- From Regmap (tied internally) --
    // input  rv_iommu_reg_pkg::iommu_reg2hw_capabilities_reg_t   capabilities_i,
    // input  rv_iommu_reg_pkg::iommu_reg2hw_fctl_reg_t           fctl_i,
    // input  rv_iommu_reg_pkg::iommu_reg2hw_ddtp_reg_t           ddtp_i,

    // -- Translation output --
    // output logic                    trans_valid_o,   /* unused */
    // output logic [riscv::PLEN-1:0]  spaddr_o,        /* unused */
    // output logic                    is_superpage_o,  /* unused */

    // -- Error --
    output logic                                    trans_error_o,
    // output logic                                 report_fault_o,   /* unused */
    output logic [(rv_iommu::CAUSE_LEN-1):0]        cause_code_o,
    // output logic                                 is_guest_pf_o,    /* unused */
    // output logic                                 is_implicit_o,    /* unused */
    // output logic [riscv::SVX-1:0]                bad_gpaddr_o,     /* unused */
    // input  logic                                 msi_write_error_i, /* unused */

    // -- HPM --
    // output logic    iotlb_miss_o,  /* unused */
    // output logic    ddt_walk_o,    /* unused */
    // output logic    pdt_walk_o,    /* unused */
    // output logic    s1_ptw_o,      /* unused */
    // output logic    s2_ptw_o,      /* unused */

    // // -- Flush --
    // input  logic                        flush_ddtc_i,
    // input  logic                        flush_dv_i,
    // input  logic [23:0]                 flush_did_i,
    // input  logic                        flush_pdtc_i,
    // input  logic                        flush_pv_i,
    // input  logic [19:0]                 flush_pid_i,
    // input  logic                        flush_vma_i,
    // input  logic                        flush_gvma_i,
    // input  logic                        flush_av_i,
    // input  logic                        flush_gv_i,
    // input  logic                        flush_pscv_i,
    // input  logic [riscv::GPPNW-1:0]     flush_vpn_i,
    // input  logic [15:0]                 flush_gscid_i,
    // input  logic [19:0]                 flush_pscid_i,

    // output logic    ignore_request_o,   /* unused */
    // input  logic    msi_data_valid_i,   /* unused */
    // input  logic [31:0] msi_data_i      /* unused */

    // -- Force control for PTW submodule --
    // force_ptw_en_i=1 の間 PTW の入力を下記の値で force する。
    // 0→1 エッジで force 開始、1→0 エッジで release。
    input  logic                        force_ptw_en_i,
    input  logic                        force_init_ptw_i,
    input  logic                        force_en_1S_i,
    input  logic                        force_en_2S_i,
    input  logic [riscv::PPNW-1:0]     force_iosatp_ppn_i,
    input  logic [riscv::PPNW-1:0]     force_iohgatp_ppn_i
);

    // ------------------------------------------------------------------
    // 固定レジスタ値 (Sv39/Sv39x4 有効、DDT 3レベル)
    // ------------------------------------------------------------------
    rv_iommu_reg_pkg::iommu_reg2hw_capabilities_reg_t caps;
    rv_iommu_reg_pkg::iommu_reg2hw_fctl_reg_t         fctl;
    rv_iommu_reg_pkg::iommu_reg2hw_ddtp_reg_t         ddtp;

    always_comb begin
        caps          = '0;
        caps.Sv39.q   = 1'b1;
        caps.Sv39x4.q = 1'b1;
        caps.pd20.q   = 1'b1;
        caps.pd17.q   = 1'b1;
        caps.pd8.q    = 1'b1;
    end

    always_comb begin
        fctl = '0;
    end

    always_comb begin
        ddtp              = '0;
        ddtp.iommu_mode.q = 4'b1000;    // 3レベル DDT
        ddtp.ppn.q        = DDT_ROOT_PPN;
    end

    // ------------------------------------------------------------------
    // 未使用 AXI ポート tie-off
    // ------------------------------------------------------------------
    axi_rsp_t   cdw_axi_resp_unused;
    axi_req_t   cdw_axi_req_unused;
    axi_rsp_t   msiptw_axi_resp_unused;
    axi_req_t   msiptw_axi_req_unused;
    axi_rsp_t   mrif_axi_resp_unused;
    axi_req_t   mrif_axi_req_unused;

    assign cdw_axi_resp_unused    = '0;
    assign msiptw_axi_resp_unused = '0;
    assign mrif_axi_resp_unused   = '0;

    // ------------------------------------------------------------------
    // DUT インスタンス
    // ------------------------------------------------------------------
    rv_iommu_tw_sv39x4_pc #(
        .IOTLB_ENTRIES  (IOTLB_ENTRIES),
        .DDTC_ENTRIES   (DDTC_ENTRIES),
        .PDTC_ENTRIES   (PDTC_ENTRIES),
        .MRIFC_ENTRIES  (MRIFC_ENTRIES),
        .MSITrans       (rv_iommu::MSI_DISABLED),
        .axi_req_t      (axi_req_t),
        .axi_rsp_t      (axi_rsp_t),
        .DC_WIDTH       ($bits(rv_iommu::dc_base_t))
    ) i_dut (
        // -- ポートリスト定義済み: 直結 --
        .clk_i              (clk_i),
        .rst_ni             (rst_ni),
        .trans_type_i       (trans_type_i),
        .priv_lvl_i         (priv_lvl_i),
        .ptw_axi_resp_i     (ptw_axi_resp_i),
        .ptw_axi_req_o      (ptw_axi_req_o),
        .trans_error_o      (trans_error_o),
        .cause_code_o       (cause_code_o),

        // -- Trigger: 固定値 --
        .req_trans_i        (1'b0),                             /* unused */
        .req_dbg_i          (1'b0),                             /* unused */

        // -- Translation request data: 固定値 --
        .did_i              (TEST_DID),                         /* unused */
        .pv_i               (1'b0),                             /* unused */
        .pid_i              (TEST_PID),                         /* unused */
        .iova_i             ('0),                               /* unused */
        .gscid_o            (),                                 /* unused */
        .pscid_o            (),                                 /* unused */

        // -- AXI: CDW/MSI PTW/MRIF: 固定値 --
        .cdw_axi_resp_i             (cdw_axi_resp_unused),      /* unused */
        .cdw_axi_req_o              (cdw_axi_req_unused),       /* unused */
        .msiptw_axi_resp_i          (msiptw_axi_resp_unused),   /* unused */
        .msiptw_axi_req_o           (msiptw_axi_req_unused),    /* unused */
        .mrif_handler_axi_resp_i    (mrif_axi_resp_unused),     /* unused */
        .mrif_handler_axi_req_o     (mrif_axi_req_unused),      /* unused */

        // -- Regmap: 内部固定値 --
        .capabilities_i     (caps),
        .fctl_i             (fctl),
        .ddtp_i             (ddtp),

        // -- Translation output: 未使用 --
        .trans_valid_o      (),                                 /* unused */
        .spaddr_o           (),                                 /* unused */
        .is_superpage_o     (),                                 /* unused */

        // -- Error: 未使用出力 / 固定値入力 --
        .report_fault_o     (),                                 /* unused */
        .is_guest_pf_o      (),                                 /* unused */
        .is_implicit_o      (),                                 /* unused */
        .bad_gpaddr_o       (),                                 /* unused */
        .msi_write_error_i  (1'b0),                             /* unused */

        // -- HPM: 未使用 --
        .iotlb_miss_o       (),                                 /* unused */
        .ddt_walk_o         (),                                 /* unused */
        .pdt_walk_o         (),                                 /* unused */
        .s1_ptw_o           (),                                 /* unused */
        .s2_ptw_o           (),                                 /* unused */

        // -- Flush: 固定値 (flush 不使用) --
        .flush_ddtc_i       (1'b0),
        .flush_dv_i         (1'b0),
        .flush_did_i        ('0),
        .flush_pdtc_i       (1'b0),
        .flush_pv_i         (1'b0),
        .flush_pid_i        ('0),
        .flush_vma_i        (1'b0),
        .flush_gvma_i       (1'b0),
        .flush_av_i         (1'b0),
        .flush_gv_i         (1'b0),
        .flush_pscv_i       (1'b0),
        .flush_vpn_i        ('0),
        .flush_gscid_i      ('0),
        .flush_pscid_i      ('0),

        // -- MSI: 固定値 --
        .ignore_request_o   (),                                 /* unused */
        .msi_data_valid_i   (1'b0),                             /* unused */
        .msi_data_i         ('0)                                /* unused */
    );

    // ------------------------------------------------------------------
    // PTW サブモジュールへの Force / Release
    //
    // 階層パス: i_dut.i_rv_iommu_ptw_sv39x4_pc
    //
    // force_ptw_en_i=1 の間、PTW の 5 入力を外部値に固定する。
    // force_ptw_en_i が 1→0 に下がったサイクルで release し、
    // ラッパー内の通常駆動に戻す。
    // ------------------------------------------------------------------
    logic force_en_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) force_en_q <= 1'b0;
        else         force_en_q <= force_ptw_en_i;
    end

    always @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.init_ptw_i;
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.en_1S_i;
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.en_2S_i;
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.iosatp_ppn_i;
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.iohgatp_ppn_i;
        end
        else if (force_ptw_en_i) begin
            force i_dut.i_rv_iommu_ptw_sv39x4_pc.init_ptw_i    = force_init_ptw_i;
            force i_dut.i_rv_iommu_ptw_sv39x4_pc.en_1S_i       = force_en_1S_i;
            force i_dut.i_rv_iommu_ptw_sv39x4_pc.en_2S_i       = force_en_2S_i;
            force i_dut.i_rv_iommu_ptw_sv39x4_pc.iosatp_ppn_i  = force_iosatp_ppn_i;
            force i_dut.i_rv_iommu_ptw_sv39x4_pc.iohgatp_ppn_i = force_iohgatp_ppn_i;
        end
        else if (force_en_q && !force_ptw_en_i) begin
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.init_ptw_i;
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.en_1S_i;
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.en_2S_i;
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.iosatp_ppn_i;
            release i_dut.i_rv_iommu_ptw_sv39x4_pc.iohgatp_ppn_i;
        end
    end

    // 波形出力
    initial begin
        $dumpfile("dump.vcd");
        $dumpvars(0, rv_iommu_tw_test_wrapper);
    end

endmodule
