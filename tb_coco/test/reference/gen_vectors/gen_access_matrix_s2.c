// gen_access_matrix_s2.c — S2 PTE パーミッション × アクセス種別 直積 (STAGE_S2_ONLY)
//
// 軸: U×R×W×X (2^4=16 flags) × R/W access = 32 ケース
#include "gen_common.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY      "access_matrix_s2"

static uint8_t make_flags(int r, int w, int x, int u) {
    uint8_t f = 1 << 0;          /* V */
    f |= (r ? 1 : 0) << 1;
    f |= (w ? 1 : 0) << 2;
    f |= (x ? 1 : 0) << 3;
    f |= (u ? 1 : 0) << 4;
    f |= 1 << 6;                 /* A */
    f |= 1 << 7;                 /* D */
    return f;
}

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    gen_common_init();
    FILE *out = stdout;
    int case_id = 0;

    static const access_t ACCS[] = { ACC_READ, ACC_WRITE };
    static const char    *AS[]   = { "r",      "w"       };

    for (int u = 0; u < 2; u++)
    for (int r = 0; r < 2; r++)
    for (int w = 0; w < 2; w++)
    for (int x = 0; x < 2; x++) {
        uint8_t flags = make_flags(r, w, x, u);
        for (int ai = 0; ai < 2; ai++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name, "s2_u%d_r%d_w%d_x%d_acc%s", u, r, w, x, AS[ai]);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = STAGE_S2_ONLY;
            tc.level = 0; tc.flags = flags; tc.access = ACCS[ai]; tc.rsvd_pattern = 0;
            run_case(&tc, out);
        }
    }

    fprintf(stderr, "✓ [%s] generated %d cases\n", CATEGORY, case_id);
    free(g_memory);
    return 0;
}
