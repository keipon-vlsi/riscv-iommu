// gen_pc_nested_full.c — PDTV=1 + PC.fsc=Sv39 + S2=Sv39x4。S1/S2 両 leaf フラグ全網羅
//
// =============================================================================
//  gen_nested_full.c の PC (Process Context) 版。
//
//  戦略 (nested_full と同様):
//   - S1 leaf PTE.PPN = 0x150 固定。S2 test PTE.PPN = 0x250 固定。
//   - S2 PT: 0x100..0x17F identity (0x150 除く) + GPA=0x150<<12 を test S2 PTE で override。
//   - S2 identity setup → add_process_context → S2 test PTE → S1 PTE の順。
//
//  固定軸
//   - DC.tc.PDTV = 1、DC.fsc.pdtp.MODE = PD20
//   - process_id = PC_PROCESS_ID_FIXED (0x42)
//
//  ケース数: 256 × 256 × 2 = 131,072 (full tier)
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY  "pc_nested_full"

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

    gen_common_init();

    FILE *out = stdout;
    int case_id = 0;

    for (int s1f = 0; s1f < 256; s1f++) {
        for (int s2f = 0; s2f < 256; s2f++) {
            for (int acc = 0; acc < 2; acc++) {
                test_case_t tc = {0};
                tc.case_id = case_id++;
                snprintf(tc.name, sizeof tc.name,
                         "pc_nf_s1_%02x_s2_%02x_%s",
                         s1f, s2f, acc == 0 ? "r" : "w");
                strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
                tc.stage_mode      = STAGE_PC_NESTED_FULL;
                tc.level           = 0;
                tc.flags           = (uint8_t)s1f;
                tc.rsvd_pattern    = 0;
                tc.access          = acc == 0 ? ACC_READ : ACC_WRITE;
                tc.iova            = 0;
                tc.s2_level        = 0;
                tc.s2_flags        = (uint8_t)s2f;
                tc.s2_rsvd_pattern = 0;
                run_case(&tc, out);
            }
        }
    }

    fprintf(stderr, "✓ [%s] generated %d cases (256 × 256 × 2)\n",
            CATEGORY, case_id);
    free(g_memory);
    return 0;
}
