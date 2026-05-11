// gen_s2_only.c — G-stage only translation (S1 Bare, S2 Sv39x4)
//
// =============================================================================
//  検証「軸」(可変軸)
//   1. S2 leaf PTE フラグ        : V/R/W/X/U/G/A/D 全 256 通り
//   2. S2 配置 level             : 0 (4K leaf), 1 (2M position), 2 (1G position)
//   3. アクセス                   : read / write
//   4. PTE bits[63:54] のリザーブビットパターン
//                                : 10 個の単独 bit + 90 個のランダム
//
//   構造は phase1_pte_flags をそのまま S2 PTE に対して再現したもの。
//   違い: DC.fsc=Bare, DC.iohgatp=Sv39x4。IOVA は GPA として扱われる。
//
//  固定軸 (このカテゴリでは __動かさない__)
//   - IOVA (= GPA)         : 0x002345 固定
//   - DID                  : 0
//   - S1                   : Bare (= identity passthrough)
//   - PDTV                 : 0
//   - MSI                  : MSIPTP_Off
//
//  ケース内訳
//   (A) Leaf level (LVL0 4K) : 256 flags × 2 access = 512
//   (B) Non-leaf at lvl1/2  : 256 flags × 2 levels  = 512
//   (C) Reserved-bit         : 10 + 90              = 100
//   合計                                            = 1124
//
//  期待値
//   - phase1_pte_flags と類似の fault パターンが S2 経路でも正しく出るか
//   - cause コードは S1 経路 (13/15) と異なり S2 経路 (21/23) になる
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY  "s2_only"

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
                     "s2_leaf_lvl0_f%02x_%s", flags, acc == 0 ? "r" : "w");
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode    = STAGE_S2_ONLY;
            tc.level         = 0;
            tc.flags         = (uint8_t)flags;
            tc.access        = acc == 0 ? ACC_READ : ACC_WRITE;
            tc.rsvd_pattern  = 0;
            tc.iova          = 0;        // default 0x002345
            run_case(&tc, out);
        }
    }

    // (B) Non-leaf levels (1=2M, 2=1G): 256 flags × 1 access
    for (int level = 1; level <= 2; level++) {
        for (int flags = 0; flags < 256; flags++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name,
                     "s2_nonleaf_lvl%d_f%02x", level, flags);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode    = STAGE_S2_ONLY;
            tc.level         = level;
            tc.flags         = (uint8_t)flags;
            tc.access        = ACC_READ;
            tc.rsvd_pattern  = 0;
            tc.iova          = 0;
            run_case(&tc, out);
        }
    }

    // (C) Reserved-bit patterns (S2 PTE bits[62:54] = 9 bits): 99 cases
    //   ★ bit 63 (Svnapot N bit) は除外 ★ — phase1_pte_flags の同セクション参照。
    for (int b = 0; b < 9; b++) {                                 // ★ 10 → 9
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "s2_rsvd_single_bit%d", b + 54);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_S2_ONLY;
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
        snprintf(tc.name, sizeof tc.name, "s2_rsvd_random_%03d", i);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_S2_ONLY;
        tc.level = 0; tc.flags = 0; tc.access = ACC_READ;
        tc.rsvd_pattern = p;
        tc.iova         = 0;
        run_case(&tc, out);
    }

    fprintf(stderr, "✓ [%s] generated %d cases\n", CATEGORY, case_id);
    free(g_memory);
    return 0;
}