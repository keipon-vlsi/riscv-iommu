// gen_nested.c — Nested 2-stage translation (S1 Sv39 + S2 Sv39x4)
//
// =============================================================================
//  検証「軸」(可変軸)  ★ Phase A ★
//   1. S1 leaf PTE フラグ : V/R/W/X/U/G/A/D 全 256 通り
//   2. S1 配置 level      : 0 / 1 / 2
//   3. アクセス            : read / write
//   4. S1 reserved bits    : 10 単独 + 90 ランダム
//
//   ※ S2 は __identity 1G superpage__ で固定 (透過)。S1 fault が nested 環境でも
//      正しく検出されるか、implicit access が S2 で fault しないかを確認するのが目的。
//
//  Phase B (将来) で追加予定
//   - S1 と S2 の組合せテスト (S1 valid × S2 様々, S1 様々 × S2 valid)
//   - implicit access fault (= S2 の S1 PT page mapping を意図的に破壊)
//
//  固定軸
//   - IOVA      : 0x002345 固定
//   - DID       : 0
//   - PDTV      : 0
//   - S2 mapping: identity 1G superpage (GPA == SPA)
//   - MSI       : MSIPTP_Off
//
//  ケース内訳 (= phase1_pte_flags と同じ)
//   (A) Leaf lvl0 4K : 512   (256 × 2)
//   (B) Non-leaf l1/2: 512
//   (C) Reserved bit : 100
//   合計             : 1124
//
//  期待値の差異
//   - S1 fault は phase1_pte_flags と同じ cause / iotval が出るはず
//   - もし implicit access (S2 walk) でバグがあると、cause=21/23 系の guest PF が
//     紛れ込む — ということは「nested 環境での S1 fault 検出ロジックの完成度」を
//     直接的に測定できる
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY  "nested"

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
                     "nested_s1_leaf_lvl0_f%02x_%s",
                     flags, acc == 0 ? "r" : "w");
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode    = STAGE_NESTED;
            tc.level         = 0;
            tc.flags         = (uint8_t)flags;
            tc.access        = acc == 0 ? ACC_READ : ACC_WRITE;
            tc.rsvd_pattern  = 0;
            tc.iova          = 0;
            run_case(&tc, out);
        }
    }

    // (B) Non-leaf levels (1=2M, 2=1G)
    for (int level = 1; level <= 2; level++) {
        for (int flags = 0; flags < 256; flags++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name,
                     "nested_s1_nonleaf_lvl%d_f%02x", level, flags);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode    = STAGE_NESTED;
            tc.level         = level;
            tc.flags         = (uint8_t)flags;
            tc.access        = ACC_READ;
            tc.rsvd_pattern  = 0;
            tc.iova          = 0;
            run_case(&tc, out);
        }
    }

    // (C) Reserved-bit patterns (S1 PTE bits[62:54] = 9 bits): 99 cases
    //   ★ bit 63 (Svnapot N bit) は除外 ★ — phase1_pte_flags の同セクション参照。
    for (int b = 0; b < 9; b++) {                                 // ★ 10 → 9
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "nested_rsvd_single_bit%d", b + 54);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_NESTED;
        tc.level = 0; tc.flags = 0; tc.access = ACC_READ;
        tc.rsvd_pattern = 1 << b;
        tc.iova         = 0;
        run_case(&tc, out);
    }
    srand(42);
    for (int i = 0; i < 90; i++) {
        int p = rand() & 0x1FF;                                   // ★ 0x3FF → 0x1FF
        if (p == 0) p = 1;
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "nested_rsvd_random_%03d", i);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_NESTED;
        tc.level = 0; tc.flags = 0; tc.access = ACC_READ;
        tc.rsvd_pattern = p;
        tc.iova         = 0;
        run_case(&tc, out);
    }

    fprintf(stderr, "✓ [%s] generated %d cases (S2 identity, S1 vary)\n",
            CATEGORY, case_id);
    free(g_memory);
    return 0;
}