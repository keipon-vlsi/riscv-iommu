// gen_nested_full.c — Nested 2-stage で S1 leaf flags と S2 leaf flags を両方網羅
//
// =============================================================================
//  検証「軸」(可変軸)
//   1. S1 leaf PTE flags : 全 256 通り
//   2. S2 leaf PTE flags : 全 256 通り
//   3. access            : read / write
//   合計 256 × 256 × 2 = 131,072 ケース
//
//  固定軸 (このカテゴリでは __動かさない__)
//   - level      : 4K leaf 固定 (S1, S2 両方とも level=0)
//   - reserved   : 0 (= phase1 / s2_only / nested で別カバー済み)
//   - IOVA       : 0x002345
//   - DID        : 0
//   - PDTV       : 0
//   - S1 leaf PPN: 0x150 固定 (S2 PT の対応 slot を override するため)
//   - S2 test PPN: 0x250 固定 (両ステージ成功時の最終 SPA = 0x250_345)
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY  "nested_full"

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

    gen_common_init();

    FILE *out = stdout;
    int case_id = 0;

    for (int s1_flags = 0; s1_flags < 256; s1_flags++) {
        for (int s2_flags = 0; s2_flags < 256; s2_flags++) {
            for (int acc = 0; acc < 2; acc++) {
                test_case_t tc = {0};
                tc.case_id = case_id++;
                snprintf(tc.name, sizeof tc.name,
                         "nested_full_s1_%02x_s2_%02x_%s",
                         s1_flags, s2_flags, acc == 0 ? "r" : "w");
                strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
                tc.stage_mode      = STAGE_NESTED_FULL;
                tc.level           = 0;
                tc.flags           = (uint8_t)s1_flags;
                tc.rsvd_pattern    = 0;
                tc.access          = acc == 0 ? ACC_READ : ACC_WRITE;
                tc.iova            = 0;
                tc.s2_level        = 0;
                tc.s2_flags        = (uint8_t)s2_flags;
                tc.s2_rsvd_pattern = 0;
                run_case(&tc, out);
            }
        }
    }

    fprintf(stderr, "✓ [%s] generated %d cases (256 S1 × 256 S2 × 2 access)\n",
            CATEGORY, case_id);
    free(g_memory);
    return 0;
}