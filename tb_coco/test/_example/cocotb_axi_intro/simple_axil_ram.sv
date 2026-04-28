// =============================================================================
// simple_axil_ram.sv
//
// Minimal AXI4-Lite slave with internal memory. cocotbext-axi の
// AxiLiteMaster との疎通練習用。
//
// 仕様:
//   - AXI4-Lite (バースト無し、ID 無し、AxLEN 無し)
//   - DATA_WIDTH = 32, ADDR_WIDTH = 12 (4 KiB)
//   - WSTRB をバイト単位で尊重
//   - レスポンスは常に OKAY (2'b00)
//   - 1 トランザクション完了するまで次は受け付けない (シンプル)
// =============================================================================

module simple_axil_ram #(
    parameter int DATA_WIDTH = 32,
    parameter int ADDR_WIDTH = 12,
    parameter int STRB_WIDTH = DATA_WIDTH/8
) (
    input  logic clk,
    input  logic rst,

    // AW (Write Address)
    input  logic [ADDR_WIDTH-1:0] s_axil_awaddr,
    input  logic [2:0]            s_axil_awprot,
    input  logic                  s_axil_awvalid,
    output logic                  s_axil_awready,

    // W (Write Data)
    input  logic [DATA_WIDTH-1:0] s_axil_wdata,
    input  logic [STRB_WIDTH-1:0] s_axil_wstrb,
    input  logic                  s_axil_wvalid,
    output logic                  s_axil_wready,

    // B (Write Response)
    output logic [1:0]            s_axil_bresp,
    output logic                  s_axil_bvalid,
    input  logic                  s_axil_bready,

    // AR (Read Address)
    input  logic [ADDR_WIDTH-1:0] s_axil_araddr,
    input  logic [2:0]            s_axil_arprot,
    input  logic                  s_axil_arvalid,
    output logic                  s_axil_arready,

    // R (Read Data)
    output logic [DATA_WIDTH-1:0] s_axil_rdata,
    output logic [1:0]            s_axil_rresp,
    output logic                  s_axil_rvalid,
    input  logic                  s_axil_rready
);

    // ---------------- Memory ----------------
    localparam int WORD_BITS = $clog2(STRB_WIDTH);    // 32-bit data → 2
    localparam int IDX_BITS  = ADDR_WIDTH - WORD_BITS; // 12 - 2 = 10
    localparam int MEM_DEPTH = 1 << IDX_BITS;          // 1024 entries

    logic [DATA_WIDTH-1:0] mem [0:MEM_DEPTH-1];

    // Init memory to 0 for repeatable simulation
    initial begin
        for (int i = 0; i < MEM_DEPTH; i++) mem[i] = '0;
    end

    // ---------------- Write side ----------------
    typedef enum logic [1:0] {
        W_IDLE = 2'd0,
        W_DATA = 2'd1,
        W_RESP = 2'd2
    } wstate_t;

    wstate_t wstate;
    logic [ADDR_WIDTH-1:0] wr_addr_q;

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            wstate    <= W_IDLE;
            wr_addr_q <= '0;
        end else begin
            unique case (wstate)
                W_IDLE: begin
                    if (s_axil_awvalid) begin
                        wr_addr_q <= s_axil_awaddr;
                        wstate    <= W_DATA;
                    end
                end
                W_DATA: begin
                    if (s_axil_wvalid) begin
                        wstate <= W_RESP;
                    end
                end
                W_RESP: begin
                    if (s_axil_bready) begin
                        wstate <= W_IDLE;
                    end
                end
                default: wstate <= W_IDLE;
            endcase
        end
    end

    assign s_axil_awready = (wstate == W_IDLE);
    assign s_axil_wready  = (wstate == W_DATA);
    assign s_axil_bvalid  = (wstate == W_RESP);
    assign s_axil_bresp   = 2'b00;  // OKAY

    // Memory write (with WSTRB byte-strobe)
    // ★ IMPORTANT: スライス [ADDR_WIDTH-1:WORD_BITS] で 10-bit index にする
    //    (>> シフトだと 12-bit のままで Verilator WIDTHTRUNC エラー)
    always_ff @(posedge clk) begin
        if (!rst && s_axil_wvalid && s_axil_wready) begin
            for (int b = 0; b < STRB_WIDTH; b++) begin
                if (s_axil_wstrb[b])
                    mem[wr_addr_q[ADDR_WIDTH-1:WORD_BITS]][b*8 +: 8] <= s_axil_wdata[b*8 +: 8];
            end
        end
    end

    // ---------------- Read side ----------------
    typedef enum logic [0:0] {
        R_IDLE = 1'd0,
        R_DATA = 1'd1
    } rstate_t;

    rstate_t rstate;
    logic [ADDR_WIDTH-1:0] rd_addr_q;

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            rstate    <= R_IDLE;
            rd_addr_q <= '0;
        end else begin
            unique case (rstate)
                R_IDLE: begin
                    if (s_axil_arvalid) begin
                        rd_addr_q <= s_axil_araddr;
                        rstate    <= R_DATA;
                    end
                end
                R_DATA: begin
                    if (s_axil_rready) begin
                        rstate <= R_IDLE;
                    end
                end
                default: rstate <= R_IDLE;
            endcase
        end
    end

    assign s_axil_arready = (rstate == R_IDLE);
    assign s_axil_rvalid  = (rstate == R_DATA);
    assign s_axil_rresp   = 2'b00;
    // ★ こちらも同じく スライスで 10-bit index に
    assign s_axil_rdata   = mem[rd_addr_q[ADDR_WIDTH-1:WORD_BITS]];

    // ---------------- VCD dump ----------------
    // [Note] Icarus でも Verilator でも波形を出すため `ifdef ガードは外す。
    // [Note] --trace 付きでビルドされていれば $dumpfile/$dumpvars が動き、
    // [Note] 出力先は実行ディレクトリ (= sim_build/) → sim_build/dump.vcd になる。
    initial begin
        $dumpfile("dump.vcd");
        $dumpvars(0, simple_axil_ram);
    end

endmodule