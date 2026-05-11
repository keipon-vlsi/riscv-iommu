// gen_iova_variation.c — IOVA の VPN[2/1/0] 境界値網羅
//
// =============================================================================
//  検証「軸」(可変軸)
//   - IOVA の VPN[2] (bits[38:30]) を 8 境界値で動かす
//   - IOVA の VPN[1] (bits[29:21]) を 8 境界値で動かす
//   - IOVA の VPN[0] (bits[20:12]) を 8 境界値で動かす
//   - アクセス: read / write
//
//   8 × 8 × 8 × 2 = 1024 ケース
//
//  固定軸 (このカテゴリでは __動かさない__)
//   - PTE フラグ : valid leaf 固定 (V|R|W|X|U|A|D = 0xDF)
//                  全 fault 検出は phase1_pte_flags でやっているので、ここでは
//                  純粋に「IOVA を変えると正しく翻訳できるか」だけを見る。
//   - 配置 level : 0 (4K leaf) 固定
//   - DID        : 0
//   - DDT        : 1LVL モード
//   - PDTV       : 0
//   - S2         : Bare
//   - reserved   : 0
//   - page offset: 0x345 (= phase1 と同じ; offset path のサニティ)
//
//  期待結果
//   - 全 1024 ケースで翻訳 success (status=0)
//   - 出力 PPN は libiommu allocator が決めた leaf PPN
//   - VPN デコードのオフセット by-1 や bit truncation バグがあると、
//     PT エントリが期待外の場所に書かれて「非対象 IOVA だけ fault」が起きるはず
//
//  境界値の選び方
//   {0x000, 0x001, 0x0FF, 0x100, 0x101, 0x1FD, 0x1FE, 0x1FF}
//   = 下端 (0, 1) / 中央付近 (256 = bit 8 boundary) / 上端 (511 = max for 9 bits)
//   各 VPN フィールドは 9 bit (0..511) なので、bit 8 の遷移点と全 bit 1 を狙い撃ち。
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY        "iova_variation"
#define LEAF_VALID_FLAGS 0xDF        // V|R|W|X|U|A|D (G=0) — 4K leaf として有効
#define PAGE_OFFSET     0x345        // phase1 と一致

static const uint64_t VPN_BOUNDARIES[] = {
    0x000,    //   0 — 下端
    0x001,    //   1 — 下端 +1
    0x0FF,    // 255 — bit 8 境界 -1
    0x100,    // 256 — bit 8 境界 (中央)
    0x101,    // 257 — bit 8 境界 +1
    0x1FD,    // 509 — 上端 -2
    0x1FE,    // 510 — 上端 -1
    0x1FF,    // 511 — 上端 (9 bit max)
};
#define N_BOUND  (sizeof(VPN_BOUNDARIES) / sizeof(VPN_BOUNDARIES[0]))

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

    gen_common_init();

    FILE *out = stdout;
    int case_id = 0;

    for (size_t i2 = 0; i2 < N_BOUND; i2++) {
        for (size_t i1 = 0; i1 < N_BOUND; i1++) {
            for (size_t i0 = 0; i0 < N_BOUND; i0++) {
                for (int acc = 0; acc < 2; acc++) {
                    uint64_t vpn2 = VPN_BOUNDARIES[i2];
                    uint64_t vpn1 = VPN_BOUNDARIES[i1];
                    uint64_t vpn0 = VPN_BOUNDARIES[i0];
                    uint64_t iova = (vpn2 << 30)
                                  | (vpn1 << 21)
                                  | (vpn0 << 12)
                                  | PAGE_OFFSET;

                    test_case_t tc = {0};
                    tc.case_id = case_id++;
                    snprintf(tc.name, sizeof tc.name,
                             "iova_v2_%03lx_v1_%03lx_v0_%03lx_%s",
                             (unsigned long)vpn2,
                             (unsigned long)vpn1,
                             (unsigned long)vpn0,
                             acc == 0 ? "r" : "w");
                    strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
                    tc.level        = 0;                       // 4K leaf
                    tc.flags        = LEAF_VALID_FLAGS;        // valid PTE
                    tc.access       = acc == 0 ? ACC_READ : ACC_WRITE;
                    tc.rsvd_pattern = 0;
                    tc.iova         = iova;                    // ★ ここが可変軸
                    run_case(&tc, out);
                }
            }
        }
    }

    fprintf(stderr, "✓ [%s] generated %d cases (%zu³ × 2 access)\n",
            CATEGORY, case_id, N_BOUND);
    free(g_memory);
    return 0;
}