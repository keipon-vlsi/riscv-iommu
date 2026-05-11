// gen_access_matrix_nested.c — S1/S2 PTE パーミッション × アクセス種別 (NESTED_FULL)
//
// ケース内訳:
//   (A) S1 vary × S2 full × 2 acc = 16flags × 2 = 32
//   (B) S2 vary × S1 full × 2 acc = 16flags × 2 = 32
//   (C) typical pairs × 2 acc = 8pairs × 2 = 16
// 合計 80 ケース
#include "gen_common.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY      "access_matrix_nested"
#define FULL_VALID     0xDF

static uint8_t make_flags(int r, int w, int x, int u) {
    uint8_t f = 1 << 0;
    f |= (r ? 1 : 0) << 1;
    f |= (w ? 1 : 0) << 2;
    f |= (x ? 1 : 0) << 3;
    f |= (u ? 1 : 0) << 4;
    f |= 1 << 6;
    f |= 1 << 7;
    return f;
}

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    gen_common_init();
    FILE *out = stdout;
    int case_id = 0;

    static const access_t ACCS[] = { ACC_READ, ACC_WRITE };
    static const char    *AS[]   = { "r",      "w"       };

    /* (A) S1 vary × S2 full × 2 acc = 32 */
    for (int u = 0; u < 2; u++)
    for (int r = 0; r < 2; r++)
    for (int w = 0; w < 2; w++)
    for (int x = 0; x < 2; x++) {
        uint8_t s1f = make_flags(r, w, x, u);
        for (int ai = 0; ai < 2; ai++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name, "s1vary_u%d_r%d_w%d_x%d_acc%s",
                     u, r, w, x, AS[ai]);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = STAGE_NESTED_FULL;
            tc.level = 0; tc.flags = s1f; tc.rsvd_pattern = 0;
            tc.s2_level = 0; tc.s2_flags = FULL_VALID; tc.s2_rsvd_pattern = 0;
            tc.access = ACCS[ai];
            run_case(&tc, out);
        }
    }
    /* (B) S2 vary × S1 full × 2 acc = 32 */
    for (int u = 0; u < 2; u++)
    for (int r = 0; r < 2; r++)
    for (int w = 0; w < 2; w++)
    for (int x = 0; x < 2; x++) {
        uint8_t s2f = make_flags(r, w, x, u);
        for (int ai = 0; ai < 2; ai++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name, "s2vary_u%d_r%d_w%d_x%d_acc%s",
                     u, r, w, x, AS[ai]);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = STAGE_NESTED_FULL;
            tc.level = 0; tc.flags = FULL_VALID; tc.rsvd_pattern = 0;
            tc.s2_level = 0; tc.s2_flags = s2f; tc.s2_rsvd_pattern = 0;
            tc.access = ACCS[ai];
            run_case(&tc, out);
        }
    }
    /* (C) typical pairs × 2 acc = 16 */
    static const struct { uint8_t s1; uint8_t s2; const char *tag; } PAIRS[] = {
        {0xC2, 0xC2, "s1R_s2R"},    {0xC4, 0xC4, "s1W_s2W"},
        {0xC8, 0xC8, "s1X_s2X"},    {0xC2, 0xC4, "s1R_s2W"},
        {0xC4, 0xC2, "s1W_s2R"},    {0xC2, 0xC8, "s1R_s2X"},
        {0xCE, 0xC2, "s1RWX_s2R"},  {0xC2, 0xCE, "s1R_s2RWX"},
    };
    for (size_t p = 0; p < sizeof(PAIRS)/sizeof(PAIRS[0]); p++) {
        for (int ai = 0; ai < 2; ai++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name, "pair_%s_acc%s", PAIRS[p].tag, AS[ai]);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = STAGE_NESTED_FULL;
            tc.level = 0; tc.flags = PAIRS[p].s1 | 0xC0; tc.rsvd_pattern = 0;
            tc.s2_level = 0; tc.s2_flags = PAIRS[p].s2 | 0xC0; tc.s2_rsvd_pattern = 0;
            tc.access = ACCS[ai];
            run_case(&tc, out);
        }
    }

    fprintf(stderr, "✓ [%s] generated %d cases\n", CATEGORY, case_id);
    free(g_memory);
    return 0;
}
