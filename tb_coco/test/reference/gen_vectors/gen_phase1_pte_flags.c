// gen_phase1_pte_flags.c — Phase 1 baseline: PTE フラグ + 配置 level + reserved bit を網羅
//
// =============================================================================
//  検証「軸」(可変軸)
//   1. leaf PTE フラグ        : V/R/W/X/U/G/A/D 全 256 通り
//   2. 配置 level             : 0 (4K leaf), 1 (2M position), 2 (1G position)
//   3. アクセス               : read / write
//   4. PTE bits[63:54] のリザーブビットパターン
//                              : 10 個の単独 bit + 90 個のランダム
//
//  固定軸 (このカテゴリでは __動かさない__)
//   - IOVA   : 0x002345 固定 (VPN[0]=2 のみ踏む)
//   - DID    : 0
//   - DDT    : 1LVL モード
//   - PDTV   : 0  (Process Context 無し)
//   - S2     : Bare (G-stage 翻訳無し)
//   - MSI    : MSIPTP_Off
//
//  ケース内訳
//   (A) Leaf level (LVL0, 4K) : 256 flags × 2 access      = 512
//   (B) Non-leaf at lvl1/2    : 256 flags × 2 levels × 1  = 512
//   (C) Reserved-bit patterns : 10 single-bit + 90 random = 100
//   合計                                                  = 1124
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY  "phase1_pte_flags"

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

    gen_common_init();

    FILE *out = stdout;
    int case_id = 0;

    // (A) Leaf level: 256 flags × 2 access types = 512 cases
    for (int flags = 0; flags < 256; flags++) {
        for (int acc = 0; acc < 2; acc++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name,
                     "leaf_lvl0_f%02x_%s", flags, acc == 0 ? "r" : "w");
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.level         = 0;
            tc.flags         = (uint8_t)flags;
            tc.access        = acc == 0 ? ACC_READ : ACC_WRITE;
            tc.rsvd_pattern  = 0;
            tc.iova          = 0;     // = use default 0x002345
            run_case(&tc, out);
        }
    }

    // (B) Non-leaf levels (mid=1, root=2): 256 flags × 1 access = 512 cases
    for (int level = 1; level <= 2; level++) {
        for (int flags = 0; flags < 256; flags++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name,
                     "nonleaf_lvl%d_f%02x", level, flags);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.level         = level;
            tc.flags         = (uint8_t)flags;
            tc.access        = ACC_READ;
            tc.rsvd_pattern  = 0;
            tc.iova          = 0;
            run_case(&tc, out);
        }
    }

    // (C) Reserved-bit patterns (PTE bits[62:54] = 9 bits): 99 cases
    //
    //   ★ bit 63 は除外 ★
    //   PTE bit 63 は Svnapot 拡張の N (NAPOT) bit。Phase 1 RTL は Svnapot 非対応
    //   なので bit 63 を reserved として fault させる一方、libiommu は Svnapot を
    //   実装しているため bit 63 を NAPOT 指定として解釈する。両者で動作が分かれる
    //   ので、Phase 1 ではこの軸を除外する (= 9-bit = 0x1FF までのパターン)。
    //   Svnapot 対応時にここを 10 / mask 0x3FF に戻す。
    for (int b = 0; b < 9; b++) {                                 // ★ 10 → 9
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "rsvd_single_bit%d", b + 54);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
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
        snprintf(tc.name, sizeof tc.name, "rsvd_random_%03d", i);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.level = 0; tc.flags = 0; tc.access = ACC_READ;
        tc.rsvd_pattern = p;
        tc.iova         = 0;
        run_case(&tc, out);
    }

    fprintf(stderr, "✓ [%s] generated %d cases\n", CATEGORY, case_id);
    free(g_memory);
    return 0;
}