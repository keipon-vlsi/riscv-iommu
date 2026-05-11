// gen_pte_reserved_nested.c — S1/S2 両 PTE 予約ビット fault (NESTED_FULL)
//
// ケース内訳:
//   (A) S1 reserved + S2 normal: 9 single + 30 random = 39
//   (B) S1 normal + S2 reserved: 9 single + 30 random = 39
//   (C) S1/S2 両方 reserved (S1 fault precedence): 9
// 合計 87 ケース
#include "gen_common.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY            "pte_reserved_nested"
#define LEAF_VALID_FLAGS     0xDF

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    gen_common_init();
    FILE *out = stdout;
    int case_id = 0;

    /* (A) S1 reserved + S2 normal: 9 single + 30 random = 39 */
    for (int b = 0; b < 9; b++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "s1rsvd_bit%d", b + 54);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_NESTED_FULL;
        tc.level = 0; tc.flags = LEAF_VALID_FLAGS; tc.rsvd_pattern = 1 << b;
        tc.s2_level = 0; tc.s2_flags = LEAF_VALID_FLAGS; tc.s2_rsvd_pattern = 0;
        tc.access = ACC_READ;
        run_case(&tc, out);
    }
    srand(42);
    for (int i = 0; i < 30; i++) {
        int p = rand() & 0x1FF;
        if (p == 0) p = 1;
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "s1rsvd_random_%03d", i);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_NESTED_FULL;
        tc.level = 0; tc.flags = LEAF_VALID_FLAGS; tc.rsvd_pattern = p;
        tc.s2_level = 0; tc.s2_flags = LEAF_VALID_FLAGS; tc.s2_rsvd_pattern = 0;
        tc.access = ACC_READ;
        run_case(&tc, out);
    }
    /* (B) S1 normal + S2 reserved: 9 single + 30 random = 39 */
    for (int b = 0; b < 9; b++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "s2rsvd_bit%d", b + 54);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_NESTED_FULL;
        tc.level = 0; tc.flags = LEAF_VALID_FLAGS; tc.rsvd_pattern = 0;
        tc.s2_level = 0; tc.s2_flags = LEAF_VALID_FLAGS; tc.s2_rsvd_pattern = 1 << b;
        tc.access = ACC_READ;
        run_case(&tc, out);
    }
    srand(43);
    for (int i = 0; i < 30; i++) {
        int p = rand() & 0x1FF;
        if (p == 0) p = 1;
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "s2rsvd_random_%03d", i);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_NESTED_FULL;
        tc.level = 0; tc.flags = LEAF_VALID_FLAGS; tc.rsvd_pattern = 0;
        tc.s2_level = 0; tc.s2_flags = LEAF_VALID_FLAGS; tc.s2_rsvd_pattern = p;
        tc.access = ACC_READ;
        run_case(&tc, out);
    }
    /* (C) S1 と S2 両方 reserved (S1 fault precedence test): 9 cases */
    for (int b = 0; b < 9; b++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "both_rsvd_bit%d", b + 54);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_NESTED_FULL;
        tc.level = 0; tc.flags = LEAF_VALID_FLAGS; tc.rsvd_pattern = 1 << b;
        tc.s2_level = 0; tc.s2_flags = LEAF_VALID_FLAGS; tc.s2_rsvd_pattern = 1 << b;
        tc.access = ACC_READ;
        run_case(&tc, out);
    }

    fprintf(stderr, "✓ [%s] generated %d cases\n", CATEGORY, case_id);
    free(g_memory);
    return 0;
}
