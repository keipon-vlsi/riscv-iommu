// Copyright © 2026 (PR-walker v2: DONE state 削除版)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: 純粋な RISC-V page table walker (3 states 版)。
//              - nested/MSI/CDW は知らない。
//              - 1 つの PT を walk するか、 1 PTE を read するだけ。
//              - Permission/A/D check は呼び出し側 (walk_ctrl) の責務。
//
// Changes from v1:
//   - DONE state を削除 (PROC_PTE で leaf/error 検出時に rsp_valid を
//     combinationally drive し、 同 cycle で IDLE へ遷移)
//   - 1 walker call あたり 1 cycle 短縮
//
// Design constraint:
//   呼び出し側 (walk_ctrl) は wait state で rsp_ready_o を **常に 1**
//   にしておくこと。 さもなくば walker が response を delivery できない。

module rv_iommu_pt_walker
    import rv_iommu::*;
#(
    parameter type axi_req_t = logic,
    parameter type axi_rsp_t = logic
) (
    input  logic                                clk_i,
    input  logic                                rst_ni,

    // ── Request handshake ────────────────────────────────────────────
    input  logic                                req_valid_i,
    output logic                                req_ready_o,
    input  logic                                req_op_i,           // 0 = WALK, 1 = READ
    input  logic                                req_is_sv39x4_i,
    input  logic [riscv::PPNW-1:0]              req_root_ppn_i,
    input  logic [riscv::VLEN-1:0]              req_va_i,
    input  logic [riscv::PLEN-1:0]              req_pptr_i,

    // ── Response (combinational, 1 cycle valid in PROC_PTE) ──────────
    output logic                                rsp_valid_o,
    output riscv::pte_t                         rsp_pte_o,
    output logic [1:0]                          rsp_lvl_o,
    output logic                                rsp_error_o,
    output logic [rv_iommu::CAUSE_LEN-1:0]      rsp_cause_o,

    // ── Memory interface ─────────────────────────────────────────────
    input  axi_rsp_t                            mem_resp_i,
    output axi_req_t                            mem_req_o,

    // ── Status ───────────────────────────────────────────────────────
    output logic                                active_o
);

    // Op encoding
    localparam logic OP_WALK = 1'b0;
    localparam logic OP_READ = 1'b1;

    // FSM states (DONE 削除済)
    typedef enum logic [1:0] {
        IDLE,
        MEM_ACCESS,
        PROC_PTE
    } state_t;
    state_t state_q, state_n;

    // Walk context registers
    logic [1:0]                         level_q,        level_n;
    logic [riscv::PLEN-1:0]             pptr_q,         pptr_n;
    logic [riscv::VLEN-1:0]             va_q,           va_n;
    logic                               is_sv39x4_q,    is_sv39x4_n;
    logic                               op_q,           op_n;

    // Combinational response (driven only when PROC_PTE produces a result)
    logic                               rsp_valid_int;
    logic                               rsp_error_int;
    logic [rv_iommu::CAUSE_LEN-1:0]     rsp_cause_int;

    // Cast received data to PTE
    riscv::pte_t                        pte;
    assign pte = riscv::pte_t'(mem_resp_i.r.data);

    // Public outputs
    assign req_ready_o = (state_q == IDLE);
    assign active_o    = (state_q != IDLE);

    // Response output (combinational, valid only the cycle PROC_PTE finishes)
    assign rsp_valid_o = rsp_valid_int;
    assign rsp_pte_o   = pte;                // memory data directly (caller latches when valid=1)
    assign rsp_lvl_o   = level_q;
    assign rsp_error_o = rsp_error_int;
    assign rsp_cause_o = rsp_cause_int;

    // ── Helper functions ─────────────────────────────────────────────
    function automatic logic [riscv::PLEN-1:0] init_pptr(
        logic [riscv::PPNW-1:0]   root,
        logic [riscv::VLEN-1:0]   va,
        logic                     is_sv39x4
    );
        if (is_sv39x4)
            init_pptr = {root[riscv::PPNW-1:2], va[riscv::SVX-1:30], 3'b0};
        else
            init_pptr = {root, va[riscv::SV-1:30], 3'b0};
    endfunction

    function automatic logic [riscv::PLEN-1:0] next_pptr(
        riscv::pte_t              prev_pte,
        logic [riscv::VLEN-1:0]   va,
        logic [1:0]               level
    );
        case (level)
            2'd2:    next_pptr = {prev_pte.ppn, va[29:21], 3'b0};
            2'd1:    next_pptr = {prev_pte.ppn, va[20:12], 3'b0};
            default: next_pptr = '0;
        endcase
    endfunction

    function automatic logic is_misaligned_super(
        riscv::pte_t  p,
        logic [1:0]   lvl
    );
        case (lvl)
            2'd2:    is_misaligned_super = |p.ppn[17:0];     // 1G leaf
            2'd1:    is_misaligned_super = |p.ppn[8:0];      // 2M leaf
            default: is_misaligned_super = 1'b0;
        endcase
    endfunction

    // ── Main FSM ─────────────────────────────────────────────────────
    always_comb begin : walker_fsm

        // === Defaults — registers preserve ===
        state_n       = state_q;
        level_n       = level_q;
        pptr_n        = pptr_q;
        va_n          = va_q;
        is_sv39x4_n   = is_sv39x4_q;
        op_n          = op_q;

        // === Defaults — response is invalid unless we explicitly drive it ===
        rsp_valid_int = 1'b0;
        rsp_error_int = 1'b0;
        rsp_cause_int = '0;

        // === Defaults — AXI master is silent ===
        // ※ AXI 仕様上、 各 channel の全 signal を毎 cycle 駆動する必要があるため
        //    これらを default で 0 (or 適切な値) にしておくのは必須。
        //    walker は read-only なので AW/W は使わない (= 全部 0)。
        mem_req_o.aw         = '0;
        mem_req_o.aw_valid   = 1'b0;
        mem_req_o.w          = '0;
        mem_req_o.w_valid    = 1'b0;
        mem_req_o.b_ready    = 1'b0;

        mem_req_o.ar.id      = 4'b0000;
        mem_req_o.ar.addr    = {{riscv::XLEN-riscv::PLEN{1'b0}}, pptr_q};
        mem_req_o.ar.len     = 8'b0;                            // 1 beat per burst
        mem_req_o.ar.size    = 3'b011;                          // 8 bytes per beat
        mem_req_o.ar.burst   = axi_pkg::BURST_FIXED;            // single beat, burst type irrelevant
        mem_req_o.ar.lock    = '0;
        mem_req_o.ar.cache   = '0;
        mem_req_o.ar.prot    = '0;
        mem_req_o.ar.qos     = '0;
        mem_req_o.ar.region  = '0;
        mem_req_o.ar.user    = '0;
        mem_req_o.ar_valid   = 1'b0;
        mem_req_o.r_ready    = 1'b0;

        case (state_q)
            // ─────────────────────────────────────────────────────────
            IDLE: begin
                if (req_valid_i) begin
                    op_n        = req_op_i;
                    is_sv39x4_n = req_is_sv39x4_i;

                    if (req_op_i == OP_WALK) begin
                        level_n = 2'd2;                          // start at L1 (top)
                        va_n    = req_va_i;
                        pptr_n  = init_pptr(req_root_ppn_i, req_va_i, req_is_sv39x4_i);
                    end else begin
                        level_n = 2'd0;                          // dummy, irrelevant for READ
                        va_n    = '0;
                        pptr_n  = req_pptr_i;
                    end
                    state_n = MEM_ACCESS;
                end
            end

            // ─────────────────────────────────────────────────────────
            MEM_ACCESS: begin
                mem_req_o.ar_valid = 1'b1;
                if (mem_resp_i.ar_ready) begin
                    state_n = PROC_PTE;
                end
            end

            // ─────────────────────────────────────────────────────────
            PROC_PTE: begin
                mem_req_o.r_ready = 1'b1;

                if (mem_resp_i.r_valid) begin
                    // AXI error
                    if (mem_resp_i.r.resp != axi_pkg::RESP_OKAY) begin
                        rsp_valid_int = 1'b1;
                        rsp_error_int = 1'b1;
                        rsp_cause_int = rv_iommu::PT_DATA_CORRUPTION;
                        state_n       = IDLE;
                    end
                    // READ_PTE: just return raw 8 bytes
                    else if (op_q == OP_READ) begin
                        rsp_valid_int = 1'b1;
                        rsp_error_int = 1'b0;
                        state_n       = IDLE;
                    end
                    // WALK_FULL: structural checks
                    else begin
                        // Invalid encoding (V=0 / R=0+W=1 / reserved bits set)
                        if (!pte.v || (!pte.r && pte.w) || (|pte.reserved)) begin
                            rsp_valid_int = 1'b1;
                            rsp_error_int = 1'b1;
                            state_n       = IDLE;
                        end
                        // Leaf
                        else if (pte.r || pte.x) begin
                            rsp_valid_int = 1'b1;
                            rsp_error_int = is_misaligned_super(pte, level_q);
                            state_n       = IDLE;
                        end
                        // Non-leaf at deepest level → fault
                        else if (level_q == 2'd0) begin
                            rsp_valid_int = 1'b1;
                            rsp_error_int = 1'b1;
                            state_n       = IDLE;
                        end
                        // Non-leaf with A/D/U set → fault
                        else if (pte.a || pte.d || pte.u) begin
                            rsp_valid_int = 1'b1;
                            rsp_error_int = 1'b1;
                            state_n       = IDLE;
                        end
                        // Non-leaf: descend (response NOT driven, continue walking)
                        else begin
                            pptr_n  = next_pptr(pte, va_q, level_q);
                            level_n = level_q - 2'd1;
                            state_n = MEM_ACCESS;
                        end
                    end
                end
            end

            default: state_n = IDLE;
        endcase
    end

    // ── Sequential ───────────────────────────────────────────────────
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            state_q     <= IDLE;
            level_q     <= 2'd0;
            pptr_q      <= '0;
            va_q        <= '0;
            is_sv39x4_q <= 1'b0;
            op_q        <= OP_WALK;
        end else begin
            state_q     <= state_n;
            level_q     <= level_n;
            pptr_q      <= pptr_n;
            va_q        <= va_n;
            is_sv39x4_q <= is_sv39x4_n;
            op_q        <= op_n;
        end
    end

endmodule