// gen_pc_phase1_pte_flags.c — PDTV=1 + PC.fsc=Sv39 の PTE フラグ網羅
//
// =============================================================================
//  gen_phase1_pte_flags.c の PC (Process Context) 版。
//
//  固定軸
//   - DC.tc.PDTV = 1、DC.fsc.pdtp.MODE = PD20
//   - process_id = PC_PROCESS_ID_FIXED (0x42)
//   - PC.ta.PSCID = PC_PSCID_FIXED (0x100)、V=ENS=SUM=1
//   - PC.fsc.iosatp.MODE = Sv39 (S1 active)、S2 = Bare
//   - IOVA : 0x002345 固定
//
//  ケース内訳 (phase1_pte_flags と同一)
//   (A) Leaf lvl0 : 256 × 2 = 512
//   (B) Non-leaf  : 256 × 2 = 512
//   (C) Reserved  : 9 + 90 = 99
//   合計          : 1123
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY  "pc_phase1_pte_flags"

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

    gen_common_init();

    FILE *out = stdout;
    int case_id = 0;

    // (A) Leaf level: 256 flags × 2 access
    for (int flags = 0; flags < 256; flags++) {
        for (int acc = 0; acc < 2; acc++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name,
                     "pc_leaf_lvl0_f%02x_%s", flags, acc == 0 ? "r" : "w");
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode   = STAGE_PC_S1_ONLY;
            tc.level        = 0;
            tc.flags        = (uint8_t)flags;
            tc.access       = acc == 0 ? ACC_READ : ACC_WRITE;
            tc.rsvd_pattern = 0;
            tc.iova         = 0;
            run_case(&tc, out);
        }
    }

    // (B) Non-leaf levels
    for (int level = 1; level <= 2; level++) {
        for (int flags = 0; flags < 256; flags++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name,
                     "pc_nonleaf_lvl%d_f%02x", level, flags);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode   = STAGE_PC_S1_ONLY;
            tc.level        = level;
            tc.flags        = (uint8_t)flags;
            tc.access       = ACC_READ;
            tc.rsvd_pattern = 0;
            tc.iova         = 0;
            run_case(&tc, out);
        }
    }

    // (C) Reserved-bit patterns (bits[62:54] = 9 bits): 99 cases
    for (int b = 0; b < 9; b++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "pc_rsvd_single_bit%d", b + 54);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode   = STAGE_PC_S1_ONLY;
        tc.level = 0; tc.flags = 0; tc.access = ACC_READ;
        tc.rsvd_pattern = 1 << b;
        tc.iova         = 0;
        run_case(&tc, out);
    }
    srand(42);
    for (int i = 0; i < 90; i++) {
        int p = rand() & 0x1FF;
        if (p == 0) p = 1;
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "pc_rsvd_random_%03d", i);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode   = STAGE_PC_S1_ONLY;
        tc.level = 0; tc.flags = 0; tc.access = ACC_READ;
        tc.rsvd_pattern = p;
        tc.iova         = 0;
        run_case(&tc, out);
    }

    fprintf(stderr, "✓ [%s] generated %d cases\n", CATEGORY, case_id);
    free(g_memory);
    return 0;
}
