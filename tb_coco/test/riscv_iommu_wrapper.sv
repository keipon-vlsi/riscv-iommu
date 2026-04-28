// =============================================================================
// tb_riscv_iommu_wrapper.sv
//
// cocotb から触れるよう riscv_iommu の AXI struct を flat 信号に展開した
// テストベンチラッパ。
//
// Phase 1 スモークテスト用:
//   - prog インターフェース (Slave AXI) のみ flat 化
//   - 他の AXI バス (dev_tr, dev_comp, ds) は struct ごと '0 にタイオフ
//   - cocotb が AxiMaster で prog 経由レジスタ R/W できればゴール
// =============================================================================

`include "assertions.svh"
`include "register_interface/typedef.svh"

`include "riscv_pkg.sv"
`include "lint_wrapper_pkg.sv"

`include "rv_iommu_pkg.sv"
`include "rv_iommu_reg_pkg.sv"
`include "rv_iommu_field_pkg.sv"

module tb_riscv_iommu_wrapper
    import lint_wrapper::*;
    import rv_iommu::*;
(
    input  logic                       clk_i,
    input  logic                       rst_ni,

    // =========================================================================
    // prog インターフェース (Slave AXI) — cocotb が AxiMaster で叩く
    // 信号名は cocotbext-axi の慣例 (prefix_axsignal) に従う
    // =========================================================================

    // ---- AW: Write Address Channel ----
    input  logic [IdWidthSlv-1:0]      prog_awid,
    input  logic [AddrWidth-1:0]       prog_awaddr,
    input  logic [7:0]                 prog_awlen,
    input  logic [2:0]                 prog_awsize,
    input  logic [1:0]                 prog_awburst,
    input  logic                       prog_awlock,
    input  logic [3:0]                 prog_awcache,
    input  logic [2:0]                 prog_awprot,
    input  logic [3:0]                 prog_awqos,
    input  logic [3:0]                 prog_awregion,
    input  logic [5:0]                 prog_awatop,
    input  logic [UserWidth-1:0]       prog_awuser,
    input  logic                       prog_awvalid,
    output logic                       prog_awready,

    // ---- W: Write Data Channel ----
    input  logic [DataWidth-1:0]       prog_wdata,
    input  logic [DataWidth/8-1:0]     prog_wstrb,
    input  logic                       prog_wlast,
    input  logic [UserWidth-1:0]       prog_wuser,
    input  logic                       prog_wvalid,
    output logic                       prog_wready,

    // ---- B: Write Response Channel ----
    output logic [IdWidthSlv-1:0]      prog_bid,
    output logic [1:0]                 prog_bresp,
    output logic [UserWidth-1:0]       prog_buser,
    output logic                       prog_bvalid,
    input  logic                       prog_bready,

    // ---- AR: Read Address Channel ----
    input  logic [IdWidthSlv-1:0]      prog_arid,
    input  logic [AddrWidth-1:0]       prog_araddr,
    input  logic [7:0]                 prog_arlen,
    input  logic [2:0]                 prog_arsize,
    input  logic [1:0]                 prog_arburst,
    input  logic                       prog_arlock,
    input  logic [3:0]                 prog_arcache,
    input  logic [2:0]                 prog_arprot,
    input  logic [3:0]                 prog_arqos,
    input  logic [3:0]                 prog_arregion,
    input  logic [UserWidth-1:0]       prog_aruser,
    input  logic                       prog_arvalid,
    output logic                       prog_arready,

    // ---- R: Read Data Channel ----
    output logic [IdWidthSlv-1:0]      prog_rid,
    output logic [DataWidth-1:0]       prog_rdata,
    output logic [1:0]                 prog_rresp,
    output logic                       prog_rlast,
    output logic [UserWidth-1:0]       prog_ruser,
    output logic                       prog_rvalid,
    input  logic                       prog_rready,

    // =========================================================================
    // 観測用: WSI 割込みワイヤ (Phase 1 では監視するだけ)
    // =========================================================================
    output logic [NumIRQWires-1:0]     wsi_wires_o
);

    // =========================================================================
    // (1) reg_bus typedef — lint_checks.sv と同じ
    //     riscv_iommu 内部で AXI を reg bus に変換するときの型
    // =========================================================================
    typedef logic [64-1:0]  reg_addr_t;
    typedef logic [32-1:0]  reg_data_t;
    typedef logic [4-1:0]   reg_strb_t;
    `REG_BUS_TYPEDEF_ALL(iommu_reg, reg_addr_t, reg_data_t, reg_strb_t)

    // =========================================================================
    // (2) prog 用 struct と flat 信号の packing/unpacking
    // =========================================================================
    req_slv_t   prog_req;
    resp_slv_t  prog_resp;

    // ---- AW packing (flat 入力 → struct) ----
    always_comb begin
        prog_req.aw         = '0;
        prog_req.aw.id      = prog_awid;
        prog_req.aw.addr    = prog_awaddr;
        prog_req.aw.len     = prog_awlen;
        prog_req.aw.size    = prog_awsize;
        prog_req.aw.burst   = prog_awburst;
        prog_req.aw.lock    = prog_awlock;
        prog_req.aw.cache   = prog_awcache;
        prog_req.aw.prot    = prog_awprot;
        prog_req.aw.qos     = prog_awqos;
        prog_req.aw.region  = prog_awregion;
        prog_req.aw.atop    = prog_awatop;
        prog_req.aw.user    = prog_awuser;
    end
    assign prog_req.aw_valid = prog_awvalid;
    assign prog_awready      = prog_resp.aw_ready;

    // ---- W packing ----
    always_comb begin
        prog_req.w       = '0;
        prog_req.w.data  = prog_wdata;
        prog_req.w.strb  = prog_wstrb;
        prog_req.w.last  = prog_wlast;
        prog_req.w.user  = prog_wuser;
    end
    assign prog_req.w_valid = prog_wvalid;
    assign prog_wready      = prog_resp.w_ready;

    // ---- B unpacking (struct 出力 → flat) ----
    assign prog_bid         = prog_resp.b.id;
    assign prog_bresp       = prog_resp.b.resp;
    assign prog_buser       = prog_resp.b.user;
    assign prog_bvalid      = prog_resp.b_valid;
    assign prog_req.b_ready = prog_bready;

    // ---- AR packing ----
    always_comb begin
        prog_req.ar         = '0;
        prog_req.ar.id      = prog_arid;
        prog_req.ar.addr    = prog_araddr;
        prog_req.ar.len     = prog_arlen;
        prog_req.ar.size    = prog_arsize;
        prog_req.ar.burst   = prog_arburst;
        prog_req.ar.lock    = prog_arlock;
        prog_req.ar.cache   = prog_arcache;
        prog_req.ar.prot    = prog_arprot;
        prog_req.ar.qos     = prog_arqos;
        prog_req.ar.region  = prog_arregion;
        prog_req.ar.user    = prog_aruser;
    end
    assign prog_req.ar_valid = prog_arvalid;
    assign prog_arready      = prog_resp.ar_ready;

    // ---- R unpacking ----
    assign prog_rid          = prog_resp.r.id;
    assign prog_rdata        = prog_resp.r.data;
    assign prog_rresp        = prog_resp.r.resp;
    assign prog_rlast        = prog_resp.r.last;
    assign prog_ruser        = prog_resp.r.user;
    assign prog_rvalid       = prog_resp.r_valid;
    assign prog_req.r_ready  = prog_rready;

    // =========================================================================
    // (3) 未使用 IF はタイオフ (struct ごと '0)
    //     awvalid=0, arvalid=0 になるので IOMMU は何も処理しない
    // =========================================================================
    req_iommu_t  dev_tr_req_tied;
    resp_t       dev_comp_resp_tied;
    resp_t       ds_resp_tied;

    assign dev_tr_req_tied    = '0;
    assign dev_comp_resp_tied = '0;
    assign ds_resp_tied       = '0;

    // 未接続を hint するための floating wire (Verilator が文句言わないように受ける)
    /* verilator lint_off UNUSED */
    resp_t       dev_tr_resp_unused;
    req_t        dev_comp_req_unused;
    req_t        ds_req_unused;
    /* verilator lint_on UNUSED */

    // =========================================================================
    // (4) DUT 本体 — lint_checks.sv のパラメータをそのまま流用
    // =========================================================================
    riscv_iommu #(
        .IOTLB_ENTRIES   ( 16              ),
        .DDTC_ENTRIES    ( 8               ),
        .PDTC_ENTRIES    ( 8               ),
        .MRIFC_ENTRIES   ( 4               ),
        .InclPC          ( 1'b1            ),
        .InclBC          ( 1'b1            ),
        .InclDBG         ( 1'b1            ),
        .MSITrans        ( MSI_FLAT_MRIF   ),
        .IGS             ( BOTH            ),
        .N_INT_VEC       ( NumIRQWires     ),
        .N_IOHPMCTR      ( 16              ),
        .ADDR_WIDTH      ( AddrWidth       ),
        .DATA_WIDTH      ( DataWidth       ),
        .ID_WIDTH        ( IdWidth         ),
        .ID_SLV_WIDTH    ( IdWidthSlv      ),
        .USER_WIDTH      ( UserWidth       ),
        .aw_chan_t       ( aw_chan_t       ),
        .w_chan_t        ( w_chan_t        ),
        .b_chan_t        ( b_chan_t        ),
        .ar_chan_t       ( ar_chan_t       ),
        .r_chan_t        ( r_chan_t        ),
        .axi_req_t       ( req_t           ),
        .axi_rsp_t       ( resp_t          ),
        .axi_req_slv_t   ( req_slv_t       ),
        .axi_rsp_slv_t   ( resp_slv_t      ),
        .axi_req_iommu_t ( req_iommu_t     ),
        .reg_req_t       ( iommu_reg_req_t ),
        .reg_rsp_t       ( iommu_reg_rsp_t )
    ) i_dut (
        .clk_i           ( clk_i               ),
        .rst_ni          ( rst_ni              ),

        // Translation Request (Slave): タイオフ
        .dev_tr_req_i    ( dev_tr_req_tied     ),
        .dev_tr_resp_o   ( dev_tr_resp_unused  ),

        // Translation Completion (Master): リクエスト出ない、応答もタイオフ
        .dev_comp_resp_i ( dev_comp_resp_tied  ),
        .dev_comp_req_o  ( dev_comp_req_unused ),

        // Data Structures (Master): 同上
        .ds_resp_i       ( ds_resp_tied        ),
        .ds_req_o        ( ds_req_unused       ),

        // Programming (Slave): cocotb が叩く本命
        .prog_req_i      ( prog_req            ),
        .prog_resp_o     ( prog_resp           ),

        .wsi_wires_o     ( wsi_wires_o         )
    );

    // =========================================================================
    // VCD ダンプ (Verilator + cocotb 両対応)
    // =========================================================================
    initial begin
        $dumpfile("dump.vcd");
        $dumpvars(0, tb_riscv_iommu_wrapper);
    end

endmodule