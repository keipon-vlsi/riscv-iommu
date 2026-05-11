// gen_pte_reserved_s2.c — S2 PTE 上位予約ビット fault 網羅
//
// gen_pte_reserved_s1.c と同構造だが STAGE_S2_ONLY を使う。
// ケース内訳: 9bits×3levels + 3 bit63 + 30random×3levels + 4pat×3levels = 27+3+90+12 = 132
#include "gen_common.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY            "pte_reserved_s2"
#define LEAF_VALID_FLAGS     0xDF
#define BIT63_RSVD           0x200      /* rsvd_pattern[9] が bit63 */

static const int INTERESTING_PATTERNS[] = { 0x1FF, 0x0F0, 0x00F, 0x155 };
#define N_INTERESTING (sizeof(INTERESTING_PATTERNS)/sizeof(INTERESTING_PATTERNS[0]))

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    gen_common_init();
    FILE *out = stdout;
    int case_id = 0;

    /* single bit per level: 9 bits × 3 levels = 27 */
    for (int level = 0; level <= 2; level++) {
        for (int b = 0; b < 9; b++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name, "s2_rsvd_lvl%d_bit%d", level, b + 54);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = STAGE_S2_ONLY;
            tc.level = level; tc.flags = LEAF_VALID_FLAGS; tc.access = ACC_READ;
            tc.rsvd_pattern = 1 << b;
            run_case(&tc, out);
        }
    }
    /* bit 63 (NAPOT scope 外): 3 levels = 3 */
    for (int level = 0; level <= 2; level++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "s2_rsvd_lvl%d_bit63_napot", level);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_S2_ONLY;
        tc.level = level; tc.flags = LEAF_VALID_FLAGS; tc.access = ACC_READ;
        tc.rsvd_pattern = BIT63_RSVD;
        run_case(&tc, out);
    }
    /* random multi-bit per level: 30 × 3 = 90 */
    srand(42);
    for (int level = 0; level <= 2; level++) {
        for (int i = 0; i < 30; i++) {
            int p = rand() & 0x1FF;
            if (p == 0) p = 1;
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name, "s2_rsvd_lvl%d_random_%03d", level, i);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = STAGE_S2_ONLY;
            tc.level = level; tc.flags = LEAF_VALID_FLAGS; tc.access = ACC_READ;
            tc.rsvd_pattern = p;
            run_case(&tc, out);
        }
    }
    /* interesting multi-bit patterns: 4 × 3 = 12 */
    for (int level = 0; level <= 2; level++) {
        for (size_t i = 0; i < N_INTERESTING; i++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name, "s2_rsvd_lvl%d_pat_%03x", level, INTERESTING_PATTERNS[i]);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = STAGE_S2_ONLY;
            tc.level = level; tc.flags = LEAF_VALID_FLAGS; tc.access = ACC_READ;
            tc.rsvd_pattern = INTERESTING_PATTERNS[i];
            run_case(&tc, out);
        }
    }

    fprintf(stderr, "✓ [%s] generated %d cases\n", CATEGORY, case_id);
    free(g_memory);
    return 0;
}
