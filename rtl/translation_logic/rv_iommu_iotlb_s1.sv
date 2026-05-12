// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (refactor)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: First-stage IOTLB for RISC-V IOMMU.
//              Caches first-stage (S1) PTEs keyed by (PSCID, GSCID, VPN).
//              Independent from the second-stage IOTLB (rv_iommu_iotlb_s2).
//              Compliant with Sv39x4 virtual memory scheme.
//
// PR1 scope:
//   - Lookup port: 1 (TW-driven)
//   - Update from: PTW (S1 leaf path) and MSIPTW (when S1 was enabled)
//   - Flush: IOTINVAL.VMA (S1 entries) and IOTINVAL.GVMA (nested S1 entries
//             that need invalidation when their corresponding S2 mapping changes)
//   - GVMA partial invalidation uses stored S1 PTE for make_gppn(),
//     keeping spec-compliance with the original unified IOTLB.

module rv_iommu_iotlb_s1 #(
    parameter int unsigned IOTLB_S1_ENTRIES = 4
)(
    input  logic                    clk_i,
    input  logic                    rst_ni,

    // Flush signals
    input  logic                    flush_vma_i,      // IOTINVAL.VMA
    input  logic                    flush_gvma_i,     // IOTINVAL.GVMA (invalidates nested S1 entries)
    input  logic                    flush_av_i,       // ADDR valid
    input  logic                    flush_gv_i,       // GSCID valid
    input  logic                    flush_pscv_i,     // PSCID valid
    input  logic [riscv::GPPNW-1:0] flush_vpn_i,      // VPN/GPPN to be flushed
    input  logic [15:0]             flush_gscid_i,    // GSCID identifier to be flushed
    input  logic [19:0]             flush_pscid_i,    // PSCID identifier to be flushed

    // Update signals (S1 leaf write)
    input  logic                    update_i,
    input  logic                    up_1S_2M_i,
    input  logic                    up_1S_1G_i,
    input  logic                    up_en_1S_i,       // Must be 1 (gated by TW)
    input  logic                    up_en_2S_i,       // Indicates nested context
    input  logic [riscv::GPPNW-1:0] up_vpn_i,
    input  logic [19:0]             up_pscid_i,
    input  logic [15:0]             up_gscid_i,
    input  riscv::pte_t             up_1S_content_i,

    // Lookup signals
    input  logic                    lookup_i,
    input  logic [riscv::VLEN-1:0]  lu_iova_i,
    input  logic [19:0]             lu_pscid_i,
    input  logic [15:0]             lu_gscid_i,
    input  logic                    en_1S_i,
    input  logic                    en_2S_i,
    output logic                    lu_1S_2M_o,
    output logic                    lu_1S_1G_o,
    output logic                    lu_hit_o,
    output logic                    lu_miss_o,
    output riscv::pte_t             lu_1S_content_o
);

    // Tag struct (S1-specific)
    struct packed {
        logic [19:0]            pscid;
        logic [15:0]            gscid;
        logic [riscv::GPPN2:0]  vpn2;       // Wide for Sv39x4 compatibility (used when stored as GPPN)
        logic [8:0]             vpn1;
        logic [8:0]             vpn0;
        logic                   is_1S_2M;
        logic                   is_1S_1G;
        logic                   en_1S;      // Always 1 for valid entries
        logic                   en_2S;      // Tag for stage-mode consistency check
        logic                   valid;
    } [IOTLB_S1_ENTRIES-1:0] tags_q, tags_n;

    // Content: S1 PTE only
    riscv::pte_t [IOTLB_S1_ENTRIES-1:0] content_q, content_n;

    // Lookup intermediate signals
    logic [8:0]                 vpn0, vpn1;
    logic [riscv::GPPN2:0]      vpn2;
    logic [IOTLB_S1_ENTRIES-1:0] lu_hit;
    logic [IOTLB_S1_ENTRIES-1:0] replace_en;
    logic [IOTLB_S1_ENTRIES-1:0] match_pscid;
    logic [IOTLB_S1_ENTRIES-1:0] match_gscid;
    logic [IOTLB_S1_ENTRIES-1:0] match_stage;
    logic [IOTLB_S1_ENTRIES-1:0] is_1G;
    logic [IOTLB_S1_ENTRIES-1:0] is_2M;

    // ------------------------------------------------------------
    //# Lookup
    // ------------------------------------------------------------
    always_comb begin : lookup
        automatic logic [riscv::GPPN2:0] mask_pn2;
        mask_pn2 = en_1S_i ? ((2**(riscv::VPN2+1))-1) : ((2**(riscv::GPPN2+1))-1);
        vpn0 = lu_iova_i[20:12];
        vpn1 = lu_iova_i[29:21];
        vpn2 = lu_iova_i[30+riscv::GPPN2:30] & mask_pn2;

        lu_hit          = '{default: 0};
        lu_hit_o        = 1'b0;
        lu_miss_o       = lookup_i;
        lu_1S_content_o = '{default: 0};
        lu_1S_2M_o      = 1'b0;
        lu_1S_1G_o      = 1'b0;
        match_pscid     = '{default: 0};
        match_gscid     = '{default: 0};
        match_stage     = '{default: 0};
        is_1G           = '{default: 0};
        is_2M           = '{default: 0};

        for (int unsigned i = 0; i < IOTLB_S1_ENTRIES; i++) begin

            // S1 IOTLB only stores entries with en_1S=1, so PSCID matching applies
            // when lookup also has en_1S=1. If lookup en_1S=0, match_stage will fail.
            match_pscid[i] = (((lu_pscid_i == tags_q[i].pscid) || content_q[i].g) && en_1S_i) || !en_1S_i;

            // GSCID match only matters in nested mode
            match_gscid[i] = (lu_gscid_i == tags_q[i].gscid && en_2S_i) || !en_2S_i;

            // Stage consistency: entry's en_1S/en_2S must match lookup's
            match_stage[i] = (tags_q[i].en_2S == en_2S_i) && (tags_q[i].en_1S == en_1S_i);

            // S1 superpage flags only (no S2 considerations in this cache)
            is_1G[i] = tags_q[i].is_1S_1G;
            is_2M[i] = tags_q[i].is_1S_2M;

            if (tags_q[i].valid && match_pscid[i] && match_gscid[i] && match_stage[i] &&
                (vpn2 == (tags_q[i].vpn2 & mask_pn2))) begin

                if (is_1G[i] || ((vpn1 == tags_q[i].vpn1) && (is_2M[i] || vpn0 == tags_q[i].vpn0))) begin
                    lu_1S_2M_o      = tags_q[i].is_1S_2M;
                    lu_1S_1G_o      = tags_q[i].is_1S_1G;
                    lu_1S_content_o = content_q[i];
                    lu_hit_o        = lookup_i;
                    lu_miss_o       = 1'b0;
                    lu_hit[i]       = 1'b1;
                end
            end
        end
    end

    // ------------------------------------------------------------
    //# Update / Flush
    // ------------------------------------------------------------
    logic  [IOTLB_S1_ENTRIES-1:0] vaddr_vpn0_match;
    logic  [IOTLB_S1_ENTRIES-1:0] vaddr_vpn1_match;
    logic  [IOTLB_S1_ENTRIES-1:0] vaddr_vpn2_match;
    logic  [IOTLB_S1_ENTRIES-1:0] vaddr_2M_match;
    logic  [IOTLB_S1_ENTRIES-1:0] vaddr_1G_match;
    logic  [IOTLB_S1_ENTRIES-1:0] gpaddr_gppn0_match;
    logic  [IOTLB_S1_ENTRIES-1:0] gpaddr_gppn1_match;
    logic  [IOTLB_S1_ENTRIES-1:0] gpaddr_gppn2_match;
    logic  [IOTLB_S1_ENTRIES-1:0] gpaddr_2M_match;
    logic  [IOTLB_S1_ENTRIES-1:0] gpaddr_1G_match;
    logic  [IOTLB_S1_ENTRIES-1:0] [riscv::GPPNW-1:0] gppn;

    always_comb begin : update_flush
        tags_n    = tags_q;
        content_n = content_q;

        for (int unsigned i = 0; i < IOTLB_S1_ENTRIES; i++) begin

            // VMA-VA based matching (IOVA path)
            vaddr_vpn0_match[i] = (flush_vpn_i[8:0]                       == tags_q[i].vpn0);
            vaddr_vpn1_match[i] = (flush_vpn_i[17:9]                      == tags_q[i].vpn1);
            vaddr_vpn2_match[i] = (flush_vpn_i[18+riscv::VPN2:18]         == tags_q[i].vpn2[riscv::VPN2:0]);
            vaddr_2M_match[i]   = (vaddr_vpn2_match[i] && vaddr_vpn1_match[i] && tags_q[i].is_1S_2M);
            vaddr_1G_match[i]   = (vaddr_vpn2_match[i] && tags_q[i].is_1S_1G);

            // GVMA-GPA based matching: reconstruct GPPN from VPN + stored S1 PTE
            gppn[i] = rv_iommu::make_gppn(tags_q[i].en_1S, tags_q[i].is_1S_1G, tags_q[i].is_1S_2M,
                                          {tags_q[i].vpn2, tags_q[i].vpn1, tags_q[i].vpn0},
                                          content_q[i]);
            gpaddr_gppn0_match[i] = (flush_vpn_i[8:0]                       == gppn[i][8:0]);
            gpaddr_gppn1_match[i] = (flush_vpn_i[17:9]                      == gppn[i][17:9]);
            gpaddr_gppn2_match[i] = (flush_vpn_i[18+riscv::GPPN2:18]        == gppn[i][18+riscv::GPPN2:18]);
            gpaddr_2M_match[i]    = (gpaddr_gppn2_match[i] && gpaddr_gppn1_match[i] && tags_q[i].is_1S_2M);
            gpaddr_1G_match[i]    = (gpaddr_gppn2_match[i] && tags_q[i].is_1S_1G);

            // IOTINVAL.VMA (S1 entry invalidation)
            //   Same 8 cases as the original unified IOTLB, but only affects S1 entries
            //   (which is everything in this cache).
            if (flush_vma_i) begin
                unique case ({flush_gv_i, flush_av_i, flush_pscv_i})
                    3'b000: begin
                        // All host address space entries (S2 disabled, S1 enabled)
                        if (!tags_q[i].en_2S && tags_q[i].en_1S) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    3'b001: begin
                        if ((!tags_q[i].en_2S && tags_q[i].en_1S) &&
                            (tags_q[i].pscid == flush_pscid_i) && !content_q[i].g) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    3'b010: begin
                        if ((!tags_q[i].en_2S && tags_q[i].en_1S) &&
                            ((vaddr_vpn2_match[i] && vaddr_vpn1_match[i] && vaddr_vpn0_match[i]) ||
                              vaddr_2M_match[i] || vaddr_1G_match[i])) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    3'b011: begin
                        if ((!tags_q[i].en_2S && tags_q[i].en_1S) &&
                            ((vaddr_vpn2_match[i] && vaddr_vpn1_match[i] && vaddr_vpn0_match[i]) ||
                              vaddr_2M_match[i] || vaddr_1G_match[i]) &&
                            tags_q[i].pscid == flush_pscid_i && !content_q[i].g) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    3'b100: begin
                        if ((tags_q[i].en_2S && tags_q[i].en_1S) && (tags_q[i].gscid == flush_gscid_i)) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    3'b101: begin
                        if ((tags_q[i].en_2S && tags_q[i].en_1S) &&
                            (tags_q[i].gscid == flush_gscid_i && tags_q[i].pscid == flush_pscid_i) &&
                            !content_q[i].g) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    3'b110: begin
                        if ((tags_q[i].en_2S && tags_q[i].en_1S) &&
                            ((vaddr_vpn2_match[i] && vaddr_vpn1_match[i] && vaddr_vpn0_match[i]) ||
                              vaddr_2M_match[i] || vaddr_1G_match[i]) &&
                            tags_q[i].gscid == flush_gscid_i) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    3'b111: begin
                        if ((tags_q[i].en_2S && tags_q[i].en_1S) &&
                            ((vaddr_vpn2_match[i] && vaddr_vpn1_match[i] && vaddr_vpn0_match[i]) ||
                              vaddr_2M_match[i] || vaddr_1G_match[i]) &&
                            (tags_q[i].gscid == flush_gscid_i && tags_q[i].pscid == flush_pscid_i) &&
                            !content_q[i].g) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                endcase
            end

            // IOTINVAL.GVMA (also affects nested S1 entries whose GPA mapping changed)
            else if (flush_gvma_i) begin
                unique casez ({flush_gv_i, flush_av_i})
                    2'b0?: begin
                        // Invalidate all nested entries (any VM)
                        if (tags_q[i].en_2S) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    2'b10: begin
                        // Invalidate nested entries for specific GSCID
                        if (tags_q[i].en_2S && tags_q[i].gscid == flush_gscid_i) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    2'b11: begin
                        // Invalidate nested entries for specific GSCID + GPA match
                        if (tags_q[i].en_2S && tags_q[i].gscid == flush_gscid_i &&
                           ((gpaddr_gppn2_match[i] && gpaddr_gppn1_match[i] && gpaddr_gppn0_match[i]) ||
                             gpaddr_2M_match[i] || gpaddr_1G_match[i])) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                endcase
            end

            // Normal replacement
            else if (update_i && replace_en[i] && up_en_1S_i && up_1S_content_i.v) begin
                tags_n[i] = '{
                    pscid:      up_pscid_i,
                    gscid:      up_gscid_i,
                    vpn2:       up_vpn_i[18+riscv::GPPN2:18],
                    vpn1:       up_vpn_i[17:9],
                    vpn0:       up_vpn_i[8:0],
                    en_1S:      up_en_1S_i,
                    en_2S:      up_en_2S_i,
                    is_1S_1G:   up_1S_1G_i,
                    is_1S_2M:   up_1S_2M_i,
                    valid:      1'b1
                };
                content_n[i] = up_1S_content_i;
            end
        end
    end

    // ------------------------------------------------------------
    //# PLRU
    // ------------------------------------------------------------
    logic [2*(IOTLB_S1_ENTRIES-1)-1:0] plru_tree_q, plru_tree_n;

    always_comb begin : plru_replacement
        plru_tree_n = plru_tree_q;
        for (int unsigned i = 0; i < IOTLB_S1_ENTRIES; i++) begin
            automatic int unsigned idx_base, shift, new_index;
            if (lu_hit[i] && lookup_i) begin
                for (int unsigned lvl = 0; lvl < $clog2(IOTLB_S1_ENTRIES); lvl++) begin
                    idx_base = $unsigned((2**lvl)-1);
                    shift = $clog2(IOTLB_S1_ENTRIES) - lvl;
                    new_index = ~((i >> (shift-1)) & 32'b1);
                    plru_tree_n[idx_base + (i >> shift)] = new_index[0];
                end
            end
        end
        for (int unsigned i = 0; i < IOTLB_S1_ENTRIES; i += 1) begin
            automatic logic en;
            automatic int unsigned idx_base, shift, new_index;
            en = 1'b1;
            for (int unsigned lvl = 0; lvl < $clog2(IOTLB_S1_ENTRIES); lvl++) begin
                idx_base = $unsigned((2**lvl)-1);
                shift = $clog2(IOTLB_S1_ENTRIES) - lvl;
                new_index = (i >> (shift-1)) & 32'b1;
                if (new_index[0]) en &= plru_tree_q[idx_base + (i>>shift)];
                else              en &= ~plru_tree_q[idx_base + (i>>shift)];
            end
            replace_en[i] = en;
        end
    end

    // ------------------------------------------------------------
    //# Sequential
    // ------------------------------------------------------------
    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            tags_q      <= '{default: 0};
            content_q   <= '{default: 0};
            plru_tree_q <= '{default: 0};
        end else begin
            tags_q      <= tags_n;
            content_q   <= content_n;
            plru_tree_q <= plru_tree_n;
        end
    end

    // ------------------------------------------------------------
    //# Assertions
    // ------------------------------------------------------------
    //pragma translate_off
    `ifndef VERILATOR
    initial begin : p_assertions
        assert ((IOTLB_S1_ENTRIES % 2 == 0) && (IOTLB_S1_ENTRIES > 1))
        else begin $error("S1 IOTLB size must be a multiple of 2 and greater than 1"); $stop(); end
    end

    function int countSetBits_s1(logic[IOTLB_S1_ENTRIES-1:0] vector);
        automatic int count = 0;
        foreach (vector[idx]) count += vector[idx];
        return count;
    endfunction

    assert property (@(posedge clk_i)(countSetBits_s1(lu_hit) <= 1))
        else begin $error("More than one hit in S1 IOTLB!"); $stop(); end
    assert property (@(posedge clk_i)(countSetBits_s1(replace_en) <= 1))
        else begin $error("More than one S1 IOTLB entry selected for replace!"); $stop(); end
    `endif
    //pragma translate_on

endmodule