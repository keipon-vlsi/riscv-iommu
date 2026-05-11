// gen_pc_nested_full_quick.c — PDTV=1 nested_full の quick 版 (代表パターンサンプル)
//
// =============================================================================
//  gen_nested_full_quick.c の PC (Process Context) 版。
//  16 × 16 × 2 = 512 ケース。
//
//  固定軸
//   - DC.tc.PDTV = 1、DC.fsc.pdtp.MODE = PD20
//   - process_id = PC_PROCESS_ID_FIXED (0x42)
//   - S1 leaf PTE.PPN = 0x150 固定、S2 test PTE.PPN = 0x250 固定
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY  "pc_nested_full_quick"

static const uint8_t REPRESENTATIVE_FLAGS[] = {
    0x00,    // V=0 (invalid)
    0x05,    // V|W (reserved combo)
    0x09,    // V|X (execute-only)
    0xC3,    // V|R|A|D (read-only kernel)
    0xC7,    // V|R|W|A|D (RW kernel)
    0xCB,    // V|R|X|A|D (RX kernel)
    0xCF,    // V|R|W|X|A|D (RWX kernel)
    0xD3,    // V|R|U|A|D (read-only user)
    0xD7,    // V|R|W|U|A|D (RW user)
    0xDB,    // V|R|X|U|A|D (RX user)
    0xDF,    // V|R|W|X|U|A|D (RWX user)
    0x8F,    // V|R|W|X|D (A=0 fault)
    0x4F,    // V|R|W|X|A (D=0 fault on write)
    0x9F,    // V|R|W|X|U|D (A=0 user)
    0x5F,    // V|R|W|X|U|A (D=0 user fault on write)
    0xFF,    // all bits incl G
};
#define NUM_REP_FLAGS (sizeof(REPRESENTATIVE_FLAGS) / sizeof(REPRESENTATIVE_FLAGS[0]))

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

    gen_common_init();

    FILE *out = stdout;
    int case_id = 0;

    for (size_t i = 0; i < NUM_REP_FLAGS; i++) {
        for (size_t j = 0; j < NUM_REP_FLAGS; j++) {
            for (int acc = 0; acc < 2; acc++) {
                uint8_t s1_flags = REPRESENTATIVE_FLAGS[i];
                uint8_t s2_flags = REPRESENTATIVE_FLAGS[j];

                test_case_t tc = {0};
                tc.case_id = case_id++;
                snprintf(tc.name, sizeof tc.name,
                         "pc_nfq_s1_%02x_s2_%02x_%s",
                         s1_flags, s2_flags, acc == 0 ? "r" : "w");
                strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
                tc.stage_mode      = STAGE_PC_NESTED_FULL;
                tc.level           = 0;
                tc.flags           = s1_flags;
                tc.rsvd_pattern    = 0;
                tc.access          = acc == 0 ? ACC_READ : ACC_WRITE;
                tc.iova            = 0;
                tc.s2_level        = 0;
                tc.s2_flags        = s2_flags;
                tc.s2_rsvd_pattern = 0;
                run_case(&tc, out);
            }
        }
    }

    fprintf(stderr, "✓ [%s] generated %d cases (%zu × %zu reps × 2 access)\n",
            CATEGORY, case_id, NUM_REP_FLAGS, NUM_REP_FLAGS);
    free(g_memory);
    return 0;
}
