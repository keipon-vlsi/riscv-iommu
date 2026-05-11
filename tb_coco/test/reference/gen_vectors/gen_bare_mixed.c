// gen_bare_mixed.c — S1/S2 Bare 各構成 × IOVA バリエーション
//
// 4 stage 構成 × 4 IOVA = 16 ケース
// STAGE_BARE_BARE を含む混合テスト。
#include "gen_common.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY            "bare_mixed"
#define LEAF_VALID_FLAGS     0xDF

static const uint64_t IOVAS[] = {
    0x0000000000234345ULL, 0x0000000000000345ULL,
    0x00000000FFFFF345ULL, 0x0000000000100345ULL,
};
#define N_IOVAS (sizeof(IOVAS) / sizeof(IOVAS[0]))

static const struct { stage_mode_t mode; const char *tag; } CONFIGS[] = {
    { STAGE_BARE_BARE, "barebare"   },
    { STAGE_S1_ONLY,   "s1_s2bare"  },
    { STAGE_S2_ONLY,   "s1bare_s2"  },
    { STAGE_NESTED,    "s1_s2_id"   },
};
#define N_CFG (sizeof(CONFIGS) / sizeof(CONFIGS[0]))

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    gen_common_init();
    FILE *out = stdout;
    int case_id = 0;

    for (size_t c = 0; c < N_CFG; c++) {
        for (size_t i = 0; i < N_IOVAS; i++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name, "%s_iova%zu", CONFIGS[c].tag, i);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = CONFIGS[c].mode;
            tc.level = 0; tc.flags = LEAF_VALID_FLAGS; tc.rsvd_pattern = 0;
            tc.access = ACC_READ; tc.iova = IOVAS[i];
            run_case(&tc, out);
        }
    }

    fprintf(stderr, "✓ [%s] generated %d cases\n", CATEGORY, case_id);
    free(g_memory);
    return 0;
}
