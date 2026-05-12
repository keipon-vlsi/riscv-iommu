// Copyright © 2023 Manuel Rodríguez & Zero-Day Labs, Lda.
// Copyright © 2026 (refactor)
// SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
//
// Description: Second-stage IOTLB for RISC-V IOMMU.
//              Caches second-stage (S2) PTEs and MSI translation results,
//              keyed by (PSCID, GSCID, VPN). Independent from S1 IOTLB.
//
// PR1 scope:
//   - Lookup port: 1 (TW-driven)
//   - Update from: PTW (S2 leaf path) and MSIPTW (basic translate result, is_msi=1)
//   - Flush: IOTINVAL.GVMA (all S2 entries, with optional GPA-based partial)
//             IOTINVAL.VMA also flushes MSI entries (since they were tagged
//             with the original PSCID at MSI translation time, similar to S1)
//   - GVMA partial invalidation uses a pre-computed gppn stored as a tag field
//     (computed at update time from up_en_1S_i + up_1S_content_i if provided,
//      else from up_vpn_i which equals GPA in S2-only mode).

module rv_iommu_iotlb_s2 #(
    parameter int unsigned IOTLB_S2_ENTRIES = 4
)(
    input  logic                    clk_i,
    input  logic                    rst_ni,

    // Flush signals
    input  logic                    flush_vma_i,      // IOTINVAL.VMA (= flush MSI entries with matching PSCID)
    input  logic                    flush_gvma_i,     // IOTINVAL.GVMA
    input  logic                    flush_av_i,
    input  logic                    flush_gv_i,
    input  logic                    flush_pscv_i,
    input  logic [riscv::GPPNW-1:0] flush_vpn_i,
    input  logic [15:0]             flush_gscid_i,
    input  logic [19:0]             flush_pscid_i,

    // Update signals (S2 leaf write or MSI write)
    input  logic                    update_i,
    input  logic                    up_2S_2M_i,
    input  logic                    up_2S_1G_i,
    input  logic                    up_is_msi_i,
    input  logic                    up_en_1S_i,       // For nested context tracking
    input  logic                    up_en_2S_i,
    input  logic [riscv::GPPNW-1:0] up_vpn_i,
    input  logic [19:0]             up_pscid_i,
    input  logic [15:0]             up_gscid_i,
    input  logic                    up_1S_2M_i,       // S1 superpage flags (for gppn calc when nested)
    input  logic                    up_1S_1G_i,
    input  riscv::pte_t             up_1S_content_i,  // S1 leaf PTE (for gppn calc when nested)
    input  riscv::pte_t             up_2S_content_i,

    // Lookup signals
    input  logic                    lookup_i,
    input  logic [riscv::VLEN-1:0]  lu_iova_i,
    input  logic [19:0]             lu_pscid_i,
    input  logic [15:0]             lu_gscid_i,
    input  logic                    en_1S_i,
    input  logic                    en_2S_i,
    output logic                    lu_2S_2M_o,
    output logic                    lu_2S_1G_o,
    output logic                    lu_is_msi_o,
    output logic                    lu_hit_o,
    output logic                    lu_miss_o,
    output riscv::pte_t             lu_2S_content_o
);

    // Tag struct (S2-specific). Includes pre-computed gppn for GVMA AV=1.
    struct packed {
        logic [19:0]                    pscid;
        logic [15:0]                    gscid;
        logic [riscv::GPPN2:0]          vpn2;
        logic [8:0]                     vpn1;
        logic [8:0]                     vpn0;
        logic                           is_2S_2M;
        logic                           is_2S_1G;
        logic                           is_msi;
        logic                           en_1S;
        logic                           en_2S;
        logic [riscv::GPPNW-1:0]        gppn;          // Pre-computed at update time
        logic                           valid;
    } [IOTLB_S2_ENTRIES-1:0] tags_q, tags_n;

    // Content: S2 PTE only (or synthetic MSI PTE)
    riscv::pte_t [IOTLB_S2_ENTRIES-1:0] content_q, content_n;

    logic [8:0]                  vpn0, vpn1;
    logic [riscv::GPPN2:0]       vpn2;
    logic [IOTLB_S2_ENTRIES-1:0] lu_hit;
    logic [IOTLB_S2_ENTRIES-1:0] replace_en;
    logic [IOTLB_S2_ENTRIES-1:0] match_pscid;
    logic [IOTLB_S2_ENTRIES-1:0] match_gscid;
    logic [IOTLB_S2_ENTRIES-1:0] match_stage;
    logic [IOTLB_S2_ENTRIES-1:0] is_1G;
    logic [IOTLB_S2_ENTRIES-1:0] is_2M;

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
        lu_2S_content_o = '{default: 0};
        lu_2S_2M_o      = 1'b0;
        lu_2S_1G_o      = 1'b0;
        lu_is_msi_o     = 1'b0;
        match_pscid     = '{default: 0};
        match_gscid     = '{default: 0};
        match_stage     = '{default: 0};
        is_1G           = '{default: 0};
        is_2M           = '{default: 0};

        for (int unsigned i = 0; i < IOTLB_S2_ENTRIES; i++) begin

            // PSCID matching only used when S1 is enabled at lookup time.
            // For MSI entries in S1-only mode, PSCID must also match (the entry
            // was stored with that PSCID, so subsequent lookups for the same
            // process see the cached MSI translation).
            match_pscid[i] = (((lu_pscid_i == tags_q[i].pscid)) && en_1S_i) || !en_1S_i;

            // GSCID matching when S2 is enabled
            match_gscid[i] = (lu_gscid_i == tags_q[i].gscid && en_2S_i) || !en_2S_i;

            // Stage consistency check
            match_stage[i] = (tags_q[i].en_2S == en_2S_i) && (tags_q[i].en_1S == en_1S_i);

            // S2 superpage flags only
            is_1G[i] = tags_q[i].is_2S_1G;
            is_2M[i] = tags_q[i].is_2S_2M;

            if (tags_q[i].valid && match_pscid[i] && match_gscid[i] && match_stage[i] &&
                (vpn2 == (tags_q[i].vpn2 & mask_pn2))) begin

                if (is_1G[i] || ((vpn1 == tags_q[i].vpn1) && (is_2M[i] || vpn0 == tags_q[i].vpn0))) begin
                    lu_2S_2M_o      = tags_q[i].is_2S_2M;
                    lu_2S_1G_o      = tags_q[i].is_2S_1G;
                    lu_is_msi_o     = tags_q[i].is_msi;
                    lu_2S_content_o = content_q[i];
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
    logic  [IOTLB_S2_ENTRIES-1:0] vaddr_vpn0_match;
    logic  [IOTLB_S2_ENTRIES-1:0] vaddr_vpn1_match;
    logic  [IOTLB_S2_ENTRIES-1:0] vaddr_vpn2_match;
    logic  [IOTLB_S2_ENTRIES-1:0] vaddr_2M_match;
    logic  [IOTLB_S2_ENTRIES-1:0] vaddr_1G_match;
    logic  [IOTLB_S2_ENTRIES-1:0] gpaddr_gppn0_match;
    logic  [IOTLB_S2_ENTRIES-1:0] gpaddr_gppn1_match;
    logic  [IOTLB_S2_ENTRIES-1:0] gpaddr_gppn2_match;
    logic  [IOTLB_S2_ENTRIES-1:0] gpaddr_2M_match;
    logic  [IOTLB_S2_ENTRIES-1:0] gpaddr_1G_match;

    // Pre-compute gppn at update time using same make_gppn as original IOTLB.
    logic [riscv::GPPNW-1:0] up_gppn;
    always_comb begin : compute_up_gppn
        up_gppn = rv_iommu::make_gppn(up_en_1S_i, up_1S_1G_i, up_1S_2M_i,
                                      up_vpn_i, up_1S_content_i);
    end

    always_comb begin : update_flush
        tags_n    = tags_q;
        content_n = content_q;

        for (int unsigned i = 0; i < IOTLB_S2_ENTRIES; i++) begin

            // VMA-VA based matching (for MSI entries stored under en_2S=0 path)
            vaddr_vpn0_match[i] = (flush_vpn_i[8:0]                       == tags_q[i].vpn0);
            vaddr_vpn1_match[i] = (flush_vpn_i[17:9]                      == tags_q[i].vpn1);
            vaddr_vpn2_match[i] = (flush_vpn_i[18+riscv::VPN2:18]         == tags_q[i].vpn2[riscv::VPN2:0]);
            vaddr_2M_match[i]   = (vaddr_vpn2_match[i] && vaddr_vpn1_match[i] && tags_q[i].is_2S_2M);
            vaddr_1G_match[i]   = (vaddr_vpn2_match[i] && tags_q[i].is_2S_1G);

            // GVMA-GPA based matching (uses stored gppn)
            gpaddr_gppn0_match[i] = (flush_vpn_i[8:0]                       == tags_q[i].gppn[8:0]);
            gpaddr_gppn1_match[i] = (flush_vpn_i[17:9]                      == tags_q[i].gppn[17:9]);
            gpaddr_gppn2_match[i] = (flush_vpn_i[18+riscv::GPPN2:18]        == tags_q[i].gppn[18+riscv::GPPN2:18]);
            gpaddr_2M_match[i]    = (gpaddr_gppn2_match[i] && gpaddr_gppn1_match[i] && tags_q[i].is_2S_2M);
            gpaddr_1G_match[i]    = (gpaddr_gppn2_match[i] && tags_q[i].is_2S_1G);

            // IOTINVAL.VMA — affects MSI entries stored in S1-only/Bare path
            //                (entries with en_2S=0 + is_msi=1 may live here).
            //                Pure S2 entries (en_2S=1, is_msi=0) are unaffected by VMA.
            if (flush_vma_i) begin
                unique case ({flush_gv_i, flush_av_i, flush_pscv_i})
                    3'b000: begin
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

            // IOTINVAL.GVMA — primary fence for S2 entries
            else if (flush_gvma_i) begin
                unique casez ({flush_gv_i, flush_av_i})
                    2'b0?: begin
                        if (tags_q[i].en_2S) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    2'b10: begin
                        if (tags_q[i].en_2S && tags_q[i].gscid == flush_gscid_i) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                    2'b11: begin
                        if (tags_q[i].en_2S && tags_q[i].gscid == flush_gscid_i &&
                            ((gpaddr_gppn2_match[i] && gpaddr_gppn1_match[i] && gpaddr_gppn0_match[i]) ||
                              gpaddr_2M_match[i] || gpaddr_1G_match[i])) begin
                            tags_n[i].valid = 1'b0;
                        end
                    end
                endcase
            end

            // Normal replacement
            else if (update_i && replace_en[i] && ((up_en_2S_i && up_2S_content_i.v) || up_is_msi_i)) begin
                tags_n[i] = '{
                    pscid:      up_pscid_i,
                    gscid:      up_gscid_i,
                    vpn2:       up_vpn_i[18+riscv::GPPN2:18],
                    vpn1:       up_vpn_i[17:9],
                    vpn0:       up_vpn_i[8:0],
                    en_1S:      up_en_1S_i,
                    en_2S:      up_en_2S_i,
                    is_2S_1G:   up_2S_1G_i,
                    is_2S_2M:   up_2S_2M_i,
                    is_msi:     up_is_msi_i,
                    gppn:       up_gppn,
                    valid:      1'b1
                };
                content_n[i] = up_2S_content_i;
            end
        end
    end

    // ------------------------------------------------------------
    //# PLRU
    // ------------------------------------------------------------
    logic [2*(IOTLB_S2_ENTRIES-1)-1:0] plru_tree_q, plru_tree_n;

    always_comb begin : plru_replacement
        plru_tree_n = plru_tree_q;
        for (int unsigned i = 0; i < IOTLB_S2_ENTRIES; i++) begin
            automatic int unsigned idx_base, shift, new_index;
            if (lu_hit[i] && lookup_i) begin
                for (int unsigned lvl = 0; lvl < $clog2(IOTLB_S2_ENTRIES); lvl++) begin
                    idx_base = $unsigned((2**lvl)-1);
                    shift = $clog2(IOTLB_S2_ENTRIES) - lvl;
                    new_index = ~((i >> (shift-1)) & 32'b1);
                    plru_tree_n[idx_base + (i >> shift)] = new_index[0];
                end
            end
        end
        for (int unsigned i = 0; i < IOTLB_S2_ENTRIES; i += 1) begin
            automatic logic en;
            automatic int unsigned idx_base, shift, new_index;
            en = 1'b1;
            for (int unsigned lvl = 0; lvl < $clog2(IOTLB_S2_ENTRIES); lvl++) begin
                idx_base = $unsigned((2**lvl)-1);
                shift = $clog2(IOTLB_S2_ENTRIES) - lvl;
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
        assert ((IOTLB_S2_ENTRIES % 2 == 0) && (IOTLB_S2_ENTRIES > 1))
        else begin $error("S2 IOTLB size must be a multiple of 2 and greater than 1"); $stop(); end
    end

    function int countSetBits_s2(logic[IOTLB_S2_ENTRIES-1:0] vector);
        automatic int count = 0;
        foreach (vector[idx]) count += vector[idx];
        return count;
    endfunction

    assert property (@(posedge clk_i)(countSetBits_s2(lu_hit) <= 1))
        else begin $error("More than one hit in S2 IOTLB!"); $stop(); end
    assert property (@(posedge clk_i)(countSetBits_s2(replace_en) <= 1))
        else begin $error("More than one S2 IOTLB entry selected for replace!"); $stop(); end
    `endif
    //pragma translate_on

endmodule