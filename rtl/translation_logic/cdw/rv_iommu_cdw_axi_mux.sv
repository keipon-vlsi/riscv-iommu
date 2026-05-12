// Copyright © 2026 (PR-cdw-split)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: AXI master mux for DDTW + PDTW
//              - DDTW と PDTW は **排他動作** (= ddtw_active と pdtw_active が
//                同時に 1 にならないことを TW orchestration が保証)
//              - 両 walker の AXI master を 1 本に集約し、 TW の外部 cdw_axi
//                ポートを変えない
//              - select は ddtw_active を優先 (= 万一同時アクティブになっても
//                deterministic に DDTW を選ぶ)

module rv_iommu_cdw_axi_mux #(
    parameter type axi_req_t = logic,
    parameter type axi_rsp_t = logic
) (
    // ── From DDTW ───────────────────────────────────────────────────
    input  logic        ddtw_active_i,
    input  axi_req_t    ddtw_axi_req_i,
    output axi_rsp_t    ddtw_axi_resp_o,

    // ── From PDTW ───────────────────────────────────────────────────
    input  logic        pdtw_active_i,
    input  axi_req_t    pdtw_axi_req_i,
    output axi_rsp_t    pdtw_axi_resp_o,

    // ── To external (TW's cdw_axi port) ─────────────────────────────
    output axi_req_t    cdw_axi_req_o,
    input  axi_rsp_t    cdw_axi_resp_i
);

    // ── Request mux (DDTW 優先) ─────────────────────────────────────
    always_comb begin
        if (ddtw_active_i) begin
            cdw_axi_req_o = ddtw_axi_req_i;
        end else if (pdtw_active_i) begin
            cdw_axi_req_o = pdtw_axi_req_i;
        end else begin
            cdw_axi_req_o = '0;
        end
    end

    // ── Response demux (active 側にだけ届ける) ──────────────────────
    always_comb begin
        ddtw_axi_resp_o = '0;
        pdtw_axi_resp_o = '0;
        if (ddtw_active_i) begin
            ddtw_axi_resp_o = cdw_axi_resp_i;
        end else if (pdtw_active_i) begin
            pdtw_axi_resp_o = cdw_axi_resp_i;
        end
    end

endmodule