// =============================================================================
// tb_riscv_iommu_wrapper.sv  (Phase 3 拡張版)
//
// Phase 1 (smoke): prog のみ flat 化
// Phase 2 (passthrough): dev_tr (DVM) + dev_comp 追加
// Phase 3 (translation): ds (Master AXI) を追加 ← 新規
//   → CDW/PTW が DDT/PT を fetch するために使用
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
    // (A) prog (Slave AXI) — レジスタアクセス
    // =========================================================================
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
    input  logic [DataWidth-1:0]       prog_wdata,
    input  logic [DataWidth/8-1:0]     prog_wstrb,
    input  logic                       prog_wlast,
    input  logic [UserWidth-1:0]       prog_wuser,
    input  logic                       prog_wvalid,
    output logic                       prog_wready,
    output logic [IdWidthSlv-1:0]      prog_bid,
    output logic [1:0]                 prog_bresp,
    output logic [UserWidth-1:0]       prog_buser,
    output logic                       prog_bvalid,
    input  logic                       prog_bready,
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
    output logic [IdWidthSlv-1:0]      prog_rid,
    output logic [DataWidth-1:0]       prog_rdata,
    output logic [1:0]                 prog_rresp,
    output logic                       prog_rlast,
    output logic [UserWidth-1:0]       prog_ruser,
    output logic                       prog_rvalid,
    input  logic                       prog_rready,

    // =========================================================================
    // (B) dev_tr (Slave AXI + DVM) — デバイスからの翻訳要求
    // =========================================================================
    input  logic [IdWidthSlv-1:0]      tr_awid,
    input  logic [AddrWidth-1:0]       tr_awaddr,
    input  logic [7:0]                 tr_awlen,
    input  logic [2:0]                 tr_awsize,
    input  logic [1:0]                 tr_awburst,
    input  logic                       tr_awlock,
    input  logic [3:0]                 tr_awcache,
    input  logic [2:0]                 tr_awprot,
    input  logic [3:0]                 tr_awqos,
    input  logic [3:0]                 tr_awregion,
    input  logic [5:0]                 tr_awatop,
    input  logic [UserWidth-1:0]       tr_awuser,
    input  logic [23:0]                tr_aw_stream_id,
    input  logic                       tr_aw_ss_id_valid,
    input  logic [19:0]                tr_aw_substream_id,
    input  logic                       tr_awvalid,
    output logic                       tr_awready,
    input  logic [DataWidth-1:0]       tr_wdata,
    input  logic [DataWidth/8-1:0]     tr_wstrb,
    input  logic                       tr_wlast,
    input  logic [UserWidth-1:0]       tr_wuser,
    input  logic                       tr_wvalid,
    output logic                       tr_wready,
    output logic [IdWidthSlv-1:0]      tr_bid,
    output logic [1:0]                 tr_bresp,
    output logic [UserWidth-1:0]       tr_buser,
    output logic                       tr_bvalid,
    input  logic                       tr_bready,
    input  logic [IdWidthSlv-1:0]      tr_arid,
    input  logic [AddrWidth-1:0]       tr_araddr,
    input  logic [7:0]                 tr_arlen,
    input  logic [2:0]                 tr_arsize,
    input  logic [1:0]                 tr_arburst,
    input  logic                       tr_arlock,
    input  logic [3:0]                 tr_arcache,
    input  logic [2:0]                 tr_arprot,
    input  logic [3:0]                 tr_arqos,
    input  logic [3:0]                 tr_arregion,
    input  logic [UserWidth-1:0]       tr_aruser,
    input  logic [23:0]                tr_ar_stream_id,
    input  logic                       tr_ar_ss_id_valid,
    input  logic [19:0]                tr_ar_substream_id,
    input  logic                       tr_arvalid,
    output logic                       tr_arready,
    output logic [IdWidthSlv-1:0]      tr_rid,
    output logic [DataWidth-1:0]       tr_rdata,
    output logic [1:0]                 tr_rresp,
    output logic                       tr_rlast,
    output logic [UserWidth-1:0]       tr_ruser,
    output logic                       tr_rvalid,
    input  logic                       tr_rready,

    // =========================================================================
    // (C) dev_comp (Master AXI) — 翻訳済みアクセス
    // =========================================================================
    output logic [IdWidth-1:0]         comp_awid,
    output logic [AddrWidth-1:0]       comp_awaddr,
    output logic [7:0]                 comp_awlen,
    output logic [2:0]                 comp_awsize,
    output logic [1:0]                 comp_awburst,
    output logic                       comp_awlock,
    output logic [3:0]                 comp_awcache,
    output logic [2:0]                 comp_awprot,
    output logic [3:0]                 comp_awqos,
    output logic [3:0]                 comp_awregion,
    output logic [5:0]                 comp_awatop,
    output logic [UserWidth-1:0]       comp_awuser,
    output logic                       comp_awvalid,
    input  logic                       comp_awready,
    output logic [DataWidth-1:0]       comp_wdata,
    output logic [DataWidth/8-1:0]     comp_wstrb,
    output logic                       comp_wlast,
    output logic [UserWidth-1:0]       comp_wuser,
    output logic                       comp_wvalid,
    input  logic                       comp_wready,
    input  logic [IdWidth-1:0]         comp_bid,
    input  logic [1:0]                 comp_bresp,
    input  logic [UserWidth-1:0]       comp_buser,
    input  logic                       comp_bvalid,
    output logic                       comp_bready,
    output logic [IdWidth-1:0]         comp_arid,
    output logic [AddrWidth-1:0]       comp_araddr,
    output logic [7:0]                 comp_arlen,
    output logic [2:0]                 comp_arsize,
    output logic [1:0]                 comp_arburst,
    output logic                       comp_arlock,
    output logic [3:0]                 comp_arcache,
    output logic [2:0]                 comp_arprot,
    output logic [3:0]                 comp_arqos,
    output logic [3:0]                 comp_arregion,
    output logic [UserWidth-1:0]       comp_aruser,
    output logic                       comp_arvalid,
    input  logic                       comp_arready,
    input  logic [IdWidth-1:0]         comp_rid,
    input  logic [DataWidth-1:0]       comp_rdata,
    input  logic [1:0]                 comp_rresp,
    input  logic                       comp_rlast,
    input  logic [UserWidth-1:0]       comp_ruser,
    input  logic                       comp_rvalid,
    output logic                       comp_rready,

    // =========================================================================
    // (D) ds (Master AXI) — DDT/PDT/PT 等のフェッチ ★ 新規 ★
    //     CDW/PTW が読み出し、FQ Handler が書込み、MSI IG が書込み等
    // =========================================================================
    output logic [IdWidth-1:0]         ds_awid,
    output logic [AddrWidth-1:0]       ds_awaddr,
    output logic [7:0]                 ds_awlen,
    output logic [2:0]                 ds_awsize,
    output logic [1:0]                 ds_awburst,
    output logic                       ds_awlock,
    output logic [3:0]                 ds_awcache,
    output logic [2:0]                 ds_awprot,
    output logic [3:0]                 ds_awqos,
    output logic [3:0]                 ds_awregion,
    output logic [5:0]                 ds_awatop,
    output logic [UserWidth-1:0]       ds_awuser,
    output logic                       ds_awvalid,
    input  logic                       ds_awready,
    output logic [DataWidth-1:0]       ds_wdata,
    output logic [DataWidth/8-1:0]     ds_wstrb,
    output logic                       ds_wlast,
    output logic [UserWidth-1:0]       ds_wuser,
    output logic                       ds_wvalid,
    input  logic                       ds_wready,
    input  logic [IdWidth-1:0]         ds_bid,
    input  logic [1:0]                 ds_bresp,
    input  logic [UserWidth-1:0]       ds_buser,
    input  logic                       ds_bvalid,
    output logic                       ds_bready,
    output logic [IdWidth-1:0]         ds_arid,
    output logic [AddrWidth-1:0]       ds_araddr,
    output logic [7:0]                 ds_arlen,
    output logic [2:0]                 ds_arsize,
    output logic [1:0]                 ds_arburst,
    output logic                       ds_arlock,
    output logic [3:0]                 ds_arcache,
    output logic [2:0]                 ds_arprot,
    output logic [3:0]                 ds_arqos,
    output logic [3:0]                 ds_arregion,
    output logic [UserWidth-1:0]       ds_aruser,
    output logic                       ds_arvalid,
    input  logic                       ds_arready,
    input  logic [IdWidth-1:0]         ds_rid,
    input  logic [DataWidth-1:0]       ds_rdata,
    input  logic [1:0]                 ds_rresp,
    input  logic                       ds_rlast,
    input  logic [UserWidth-1:0]       ds_ruser,
    input  logic                       ds_rvalid,
    output logic                       ds_rready,

    // =========================================================================
    // (E) WSI 観測
    // =========================================================================
    output logic [NumIRQWires-1:0]     wsi_wires_o
);

    // reg_bus typedef
    typedef logic [64-1:0]  reg_addr_t;
    typedef logic [32-1:0]  reg_data_t;
    typedef logic [4-1:0]   reg_strb_t;
    `REG_BUS_TYPEDEF_ALL(iommu_reg, reg_addr_t, reg_data_t, reg_strb_t)

    // =========================================================================
    // (1) prog packing/unpacking
    // =========================================================================
    req_slv_t   prog_req;
    resp_slv_t  prog_resp;

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

    always_comb begin
        prog_req.w       = '0;
        prog_req.w.data  = prog_wdata;
        prog_req.w.strb  = prog_wstrb;
        prog_req.w.last  = prog_wlast;
        prog_req.w.user  = prog_wuser;
    end
    assign prog_req.w_valid = prog_wvalid;
    assign prog_wready      = prog_resp.w_ready;

    assign prog_bid         = prog_resp.b.id;
    assign prog_bresp       = prog_resp.b.resp;
    assign prog_buser       = prog_resp.b.user;
    assign prog_bvalid      = prog_resp.b_valid;
    assign prog_req.b_ready = prog_bready;

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

    assign prog_rid          = prog_resp.r.id;
    assign prog_rdata        = prog_resp.r.data;
    assign prog_rresp        = prog_resp.r.resp;
    assign prog_rlast        = prog_resp.r.last;
    assign prog_ruser        = prog_resp.r.user;
    assign prog_rvalid       = prog_resp.r_valid;
    assign prog_req.r_ready  = prog_rready;

    // =========================================================================
    // (2) dev_tr packing/unpacking (with DVM)
    // =========================================================================
    req_iommu_t  tr_req;
    resp_t       tr_resp;

    always_comb begin
        tr_req.aw                = '0;
        tr_req.aw.id             = tr_awid;
        tr_req.aw.addr           = tr_awaddr;
        tr_req.aw.len            = tr_awlen;
        tr_req.aw.size           = tr_awsize;
        tr_req.aw.burst          = tr_awburst;
        tr_req.aw.lock           = tr_awlock;
        tr_req.aw.cache          = tr_awcache;
        tr_req.aw.prot           = tr_awprot;
        tr_req.aw.qos            = tr_awqos;
        tr_req.aw.region         = tr_awregion;
        tr_req.aw.atop           = tr_awatop;
        tr_req.aw.user           = tr_awuser;
        tr_req.aw.stream_id      = tr_aw_stream_id;
        tr_req.aw.ss_id_valid    = tr_aw_ss_id_valid;
        tr_req.aw.substream_id   = tr_aw_substream_id;
    end
    assign tr_req.aw_valid = tr_awvalid;
    assign tr_awready      = tr_resp.aw_ready;

    always_comb begin
        tr_req.w       = '0;
        tr_req.w.data  = tr_wdata;
        tr_req.w.strb  = tr_wstrb;
        tr_req.w.last  = tr_wlast;
        tr_req.w.user  = tr_wuser;
    end
    assign tr_req.w_valid = tr_wvalid;
    assign tr_wready      = tr_resp.w_ready;

    assign tr_bid         = tr_resp.b.id;
    assign tr_bresp       = tr_resp.b.resp;
    assign tr_buser       = tr_resp.b.user;
    assign tr_bvalid      = tr_resp.b_valid;
    assign tr_req.b_ready = tr_bready;

    always_comb begin
        tr_req.ar                = '0;
        tr_req.ar.id             = tr_arid;
        tr_req.ar.addr           = tr_araddr;
        tr_req.ar.len            = tr_arlen;
        tr_req.ar.size           = tr_arsize;
        tr_req.ar.burst          = tr_arburst;
        tr_req.ar.lock           = tr_arlock;
        tr_req.ar.cache          = tr_arcache;
        tr_req.ar.prot           = tr_arprot;
        tr_req.ar.qos            = tr_arqos;
        tr_req.ar.region         = tr_arregion;
        tr_req.ar.user           = tr_aruser;
        tr_req.ar.stream_id      = tr_ar_stream_id;
        tr_req.ar.ss_id_valid    = tr_ar_ss_id_valid;
        tr_req.ar.substream_id   = tr_ar_substream_id;
    end
    assign tr_req.ar_valid = tr_arvalid;
    assign tr_arready      = tr_resp.ar_ready;

    assign tr_rid          = tr_resp.r.id;
    assign tr_rdata        = tr_resp.r.data;
    assign tr_rresp        = tr_resp.r.resp;
    assign tr_rlast        = tr_resp.r.last;
    assign tr_ruser        = tr_resp.r.user;
    assign tr_rvalid       = tr_resp.r_valid;
    assign tr_req.r_ready  = tr_rready;

    // =========================================================================
    // (3) dev_comp packing/unpacking
    // =========================================================================
    req_t   comp_req;
    resp_t  comp_resp;

    assign comp_awid     = comp_req.aw.id;
    assign comp_awaddr   = comp_req.aw.addr;
    assign comp_awlen    = comp_req.aw.len;
    assign comp_awsize   = comp_req.aw.size;
    assign comp_awburst  = comp_req.aw.burst;
    assign comp_awlock   = comp_req.aw.lock;
    assign comp_awcache  = comp_req.aw.cache;
    assign comp_awprot   = comp_req.aw.prot;
    assign comp_awqos    = comp_req.aw.qos;
    assign comp_awregion = comp_req.aw.region;
    assign comp_awatop   = comp_req.aw.atop;
    assign comp_awuser   = comp_req.aw.user;
    assign comp_awvalid  = comp_req.aw_valid;
    assign comp_resp.aw_ready = comp_awready;

    assign comp_wdata    = comp_req.w.data;
    assign comp_wstrb    = comp_req.w.strb;
    assign comp_wlast    = comp_req.w.last;
    assign comp_wuser    = comp_req.w.user;
    assign comp_wvalid   = comp_req.w_valid;
    assign comp_resp.w_ready = comp_wready;

    always_comb begin
        comp_resp.b      = '0;
        comp_resp.b.id   = comp_bid;
        comp_resp.b.resp = comp_bresp;
        comp_resp.b.user = comp_buser;
    end
    assign comp_resp.b_valid = comp_bvalid;
    assign comp_bready       = comp_req.b_ready;

    assign comp_arid     = comp_req.ar.id;
    assign comp_araddr   = comp_req.ar.addr;
    assign comp_arlen    = comp_req.ar.len;
    assign comp_arsize   = comp_req.ar.size;
    assign comp_arburst  = comp_req.ar.burst;
    assign comp_arlock   = comp_req.ar.lock;
    assign comp_arcache  = comp_req.ar.cache;
    assign comp_arprot   = comp_req.ar.prot;
    assign comp_arqos    = comp_req.ar.qos;
    assign comp_arregion = comp_req.ar.region;
    assign comp_aruser   = comp_req.ar.user;
    assign comp_arvalid  = comp_req.ar_valid;
    assign comp_resp.ar_ready = comp_arready;

    always_comb begin
        comp_resp.r      = '0;
        comp_resp.r.id   = comp_rid;
        comp_resp.r.data = comp_rdata;
        comp_resp.r.resp = comp_rresp;
        comp_resp.r.last = comp_rlast;
        comp_resp.r.user = comp_ruser;
    end
    assign comp_resp.r_valid = comp_rvalid;
    assign comp_rready       = comp_req.r_ready;

    // =========================================================================
    // (4) ds packing/unpacking (Master AXI, dev_comp と同じパターン)
    // =========================================================================
    req_t   ds_req;
    resp_t  ds_resp;

    assign ds_awid     = ds_req.aw.id;
    assign ds_awaddr   = ds_req.aw.addr;
    assign ds_awlen    = ds_req.aw.len;
    assign ds_awsize   = ds_req.aw.size;
    assign ds_awburst  = ds_req.aw.burst;
    assign ds_awlock   = ds_req.aw.lock;
    assign ds_awcache  = ds_req.aw.cache;
    assign ds_awprot   = ds_req.aw.prot;
    assign ds_awqos    = ds_req.aw.qos;
    assign ds_awregion = ds_req.aw.region;
    assign ds_awatop   = ds_req.aw.atop;
    assign ds_awuser   = ds_req.aw.user;
    assign ds_awvalid  = ds_req.aw_valid;
    assign ds_resp.aw_ready = ds_awready;

    assign ds_wdata    = ds_req.w.data;
    assign ds_wstrb    = ds_req.w.strb;
    assign ds_wlast    = ds_req.w.last;
    assign ds_wuser    = ds_req.w.user;
    assign ds_wvalid   = ds_req.w_valid;
    assign ds_resp.w_ready = ds_wready;

    always_comb begin
        ds_resp.b      = '0;
        ds_resp.b.id   = ds_bid;
        ds_resp.b.resp = ds_bresp;
        ds_resp.b.user = ds_buser;
    end
    assign ds_resp.b_valid = ds_bvalid;
    assign ds_bready       = ds_req.b_ready;

    assign ds_arid     = ds_req.ar.id;
    assign ds_araddr   = ds_req.ar.addr;
    assign ds_arlen    = ds_req.ar.len;
    assign ds_arsize   = ds_req.ar.size;
    assign ds_arburst  = ds_req.ar.burst;
    assign ds_arlock   = ds_req.ar.lock;
    assign ds_arcache  = ds_req.ar.cache;
    assign ds_arprot   = ds_req.ar.prot;
    assign ds_arqos    = ds_req.ar.qos;
    assign ds_arregion = ds_req.ar.region;
    assign ds_aruser   = ds_req.ar.user;
    assign ds_arvalid  = ds_req.ar_valid;
    assign ds_resp.ar_ready = ds_arready;

    always_comb begin
        ds_resp.r      = '0;
        ds_resp.r.id   = ds_rid;
        ds_resp.r.data = ds_rdata;
        ds_resp.r.resp = ds_rresp;
        ds_resp.r.last = ds_rlast;
        ds_resp.r.user = ds_ruser;
    end
    assign ds_resp.r_valid = ds_rvalid;
    assign ds_rready       = ds_req.r_ready;

    // =========================================================================
    // (5) DUT 本体
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

        .dev_tr_req_i    ( tr_req              ),
        .dev_tr_resp_o   ( tr_resp             ),

        .dev_comp_resp_i ( comp_resp           ),
        .dev_comp_req_o  ( comp_req            ),

        // ds: 接続! (タイオフから卒業)
        .ds_resp_i       ( ds_resp             ),
        .ds_req_o        ( ds_req              ),

        .prog_req_i      ( prog_req            ),
        .prog_resp_o     ( prog_resp           ),

        .wsi_wires_o     ( wsi_wires_o         )
    );

    `ifdef ENABLE_WAVE_DUMP
        initial begin
    `ifdef WAVE_FORMAT_VCD
            $dumpfile("dump.vcd");
    `else
            $dumpfile("dump.fst");      // ★ .fst 拡張子で Verilator が FST encoding を選ぶ
    `endif

    `ifdef WAVE_FULL
            $dumpvars(0, tb_riscv_iommu_wrapper);
    `elsif WAVE_CDW
            // ── CDW 系のみ dump ──────────────────────────────────────
            // ★ 階層 path は wrapper の instance 名に合わせて要調整
            $dumpvars(0, tb_riscv_iommu_wrapper.dut.i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_ddtw);
            $dumpvars(0, tb_riscv_iommu_wrapper.dut.i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_pdtw);
            $dumpvars(0, tb_riscv_iommu_wrapper.dut.i_rv_iommu_tw_sv39x4_pc.i_cdw_axi_mux);
            // TW top レベル信号 (= ddtc_update, pdtc_update など) を 1 段だけ
            $dumpvars(1, tb_riscv_iommu_wrapper.dut.i_rv_iommu_tw_sv39x4_pc);
    `else
            // WAVE_SCOPE=none: dump 開始だけして $dumpvars は呼ばない
    `endif
        end
    `endif

endmodule