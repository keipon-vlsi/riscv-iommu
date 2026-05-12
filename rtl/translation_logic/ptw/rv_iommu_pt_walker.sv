// Copyright © 2026 (PR-cdw-split v4)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: Pure AXI read engine for page-table walks (= PT walker)
//
//   責務:
//     - 指定アドレスから 8 byte (= 1 PTE) を AXI read する
//     - 読めた raw data を呼び出し側 (walk_ctrl) に渡す
//     - PTE の意味解釈は **しない** (= V/R/W/X 等の検査は walk_ctrl の仕事)
//
//   3-state FSM: IDLE / ISSUE_AR / WAIT_R
//
//   呼び出しプロトコル (= valid/ready handshake):
//     1. walk_ctrl: req_addr_i を設定し req_valid_i を立てる
//     2. walker (IDLE中): req_ready_o = 1 → 1 cycle で受領 → ISSUE_AR へ
//     3. walker: AXI で read 発行
//     4. walker (WAIT_R中): r_valid 受信 → rsp_valid_o = 1, rsp_data_o = r.data
//     5. walk_ctrl: rsp_ready_i = 1 を立てて consume → walker は IDLE に戻る

module rv_iommu_pt_walker
    import rv_iommu::*;
#(
    parameter type axi_req_t = logic,
    parameter type axi_rsp_t = logic
) (
    input  logic                                clk_i,
    input  logic                                rst_ni,

    // ── Request from walk_ctrl ──────────────────────────────────────
    input  logic                                req_valid_i,
    output logic                                req_ready_o,
    input  logic [riscv::PLEN-1:0]              req_addr_i,

    // ── Response to walk_ctrl ───────────────────────────────────────
    output logic                                rsp_valid_o,
    input  logic                                rsp_ready_i,
    output logic [63:0]                         rsp_data_o,
    output logic                                rsp_error_o,

    // ── AXI master ──────────────────────────────────────────────────
    input  axi_rsp_t                            mem_resp_i,
    output axi_req_t                            mem_req_o
);

    typedef enum logic [1:0] {
        ST_IDLE,
        ST_ISSUE_AR,
        ST_WAIT_R
    } state_t;
    state_t state_q, state_n;

    logic [riscv::PLEN-1:0]                     req_addr_q, req_addr_n;

    assign req_ready_o = (state_q == ST_IDLE);

    always_comb begin : walker_fsm
        state_n     = state_q;
        req_addr_n  = req_addr_q;

        rsp_valid_o = 1'b0;
        rsp_data_o  = '0;
        rsp_error_o = 1'b0;

        // AXI defaults
        mem_req_o          = '0;
        mem_req_o.ar.id    = 4'b0011;
        mem_req_o.ar.addr  = {{riscv::XLEN-riscv::PLEN{1'b0}}, req_addr_q};
        mem_req_o.ar.len   = 8'd0;        // 1 beat = 8 B = 1 PTE
        mem_req_o.ar.size  = 3'b011;
        mem_req_o.ar.burst = axi_pkg::BURST_INCR;
        mem_req_o.ar_valid = 1'b0;
        mem_req_o.r_ready  = 1'b0;

        case (state_q)
            ST_IDLE: begin
                if (req_valid_i) begin
                    req_addr_n = req_addr_i;
                    state_n    = ST_ISSUE_AR;
                end
            end

            ST_ISSUE_AR: begin
                mem_req_o.ar_valid = 1'b1;
                if (mem_resp_i.ar_ready) state_n = ST_WAIT_R;
            end

            ST_WAIT_R: begin
                // ★ r_ready は r_valid を待たずに早期に assert
                //    (= AXI 仕様上は問題なし、 一部 testbench の memory model が
                //     r_ready 先行を期待するケースに対応)
                mem_req_o.r_ready = rsp_ready_i;
                if (mem_resp_i.r_valid) begin
                    rsp_valid_o = 1'b1;
                    rsp_data_o  = mem_resp_i.r.data;
                    rsp_error_o = (mem_resp_i.r.resp != axi_pkg::RESP_OKAY);
                    if (rsp_ready_i) begin
                        state_n = ST_IDLE;
                    end
                end
            end

            default: state_n = ST_IDLE;
        endcase
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            state_q    <= ST_IDLE;
            req_addr_q <= '0;
        end else begin
            state_q    <= state_n;
            req_addr_q <= req_addr_n;
        end
    end

endmodule