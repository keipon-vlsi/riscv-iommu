// gen_nested_full_quick.c — `nested_full` の quick 版 (代表パターンサンプル)
//
// =============================================================================
//  なぜ quick 版を作るか
//   - 本家 nested_full は 256 × 256 × 2 = 131,072 ケースで CI 向け。
//   - 日中の iter cycle で全件回すのは 30-60 分かかって現実的でない。
//   - PTE フラグの「境界」となる代表 16 パターンだけを使えば、
//     16 × 16 × 2 = 512 ケースで主要な動作分布を網羅できる。
//
//  代表パターン 16 個の選び方
//
//   ┌───────┬─────────────────────────────────┬─────────────────────────┐
//   │ flags │ 何を意図しているか              │ 期待挙動                  │
//   ├───────┼─────────────────────────────────┼─────────────────────────┤
//   │ 0x00  │ V=0                             │ Invalid PTE → fault     │
//   │ 0x05  │ V=1, R=0, W=1 (= reserved combo) │ spec 上 reserved → fault│
//   │ 0x09  │ V=1, R=0, X=1 (= execute-only)   │ Read fault              │
//   │ 0xC3  │ V|R|A|D                          │ R-only kernel → success │
//   │ 0xC7  │ V|R|W|A|D                        │ RW kernel → success     │
//   │ 0xCB  │ V|R|X|A|D                        │ RX kernel → success     │
//   │ 0xCF  │ V|R|W|X|A|D                      │ RWX kernel → success    │
//   │ 0xD3  │ V|R|U|A|D                        │ R-only user → success   │
//   │ 0xD7  │ V|R|W|U|A|D                      │ RW user → success       │
//   │ 0xDB  │ V|R|X|U|A|D                      │ RX user → success       │
//   │ 0xDF  │ V|R|W|X|U|A|D                    │ RWX user → success      │
//   │ 0x8F  │ V|R|W|X|D (no A)                 │ A=0 → fault (any access)│
//   │ 0x4F  │ V|R|W|X|A (no D)                 │ D=0 → write fault       │
//   │ 0x9F  │ V|R|W|X|U|D (no A)               │ A=0 → fault user        │
//   │ 0x5F  │ V|R|W|X|U|A (no D)               │ D=0 → write fault user  │
//   │ 0xFF  │ all bits incl G                  │ Full access (G=1)       │
//   └───────┴─────────────────────────────────┴─────────────────────────┘
//
//  Quick 版に取り入れていない軸
//   - reserved bit pattern : phase1_pte_flags / s2_only でカバー済み
//   - non-leaf level        : nested で代表的なケース済み
//   - IOVA variation        : iova_variation でカバー済み
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY  "nested_full_quick"

static const uint8_t REPRESENTATIVE_FLAGS[] = {
    0x00,    // V=0 (invalid)
    0x05,    // V|W (reserved combo)
    0x09,    // V|X (execute-only)
    0xC3,    // V|R|A|D (read-only kernel)
    0xC7,    // V|R|W|A|D (RW kernel)
    0xCB,    // V|R|X|A|D (RX kernel)
    0xCF,    // V|R|W|X|A|D (RWX kernel)
    0xD3,    // V|R|U|A|D (read-only user)
    0xD7,    // V|R|W|U|A|D (RW user)
    0xDB,    // V|R|X|U|A|D (RX user)
    0xDF,    // V|R|W|X|U|A|D (RWX user)
    0x8F,    // V|R|W|X|D (A=0 fault)
    0x4F,    // V|R|W|X|A (D=0 fault on write)
    0x9F,    // V|R|W|X|U|D (A=0 user)
    0x5F,    // V|R|W|X|U|A (D=0 user fault on write)
    0xFF,    // all bits incl G
};
#define NUM_REP_FLAGS (sizeof(REPRESENTATIVE_FLAGS) / sizeof(REPRESENTATIVE_FLAGS[0]))

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

    gen_common_init();

    FILE *out = stdout;
    int case_id = 0;

    for (size_t i = 0; i < NUM_REP_FLAGS; i++) {
        for (size_t j = 0; j < NUM_REP_FLAGS; j++) {
            for (int acc = 0; acc < 2; acc++) {
                uint8_t s1_flags = REPRESENTATIVE_FLAGS[i];
                uint8_t s2_flags = REPRESENTATIVE_FLAGS[j];

                test_case_t tc = {0};
                tc.case_id = case_id++;
                snprintf(tc.name, sizeof tc.name,
                         "nfq_s1_%02x_s2_%02x_%s",
                         s1_flags, s2_flags, acc == 0 ? "r" : "w");
                strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
                tc.stage_mode      = STAGE_NESTED_FULL;
                tc.level           = 0;
                tc.flags           = s1_flags;
                tc.rsvd_pattern    = 0;
                tc.access          = acc == 0 ? ACC_READ : ACC_WRITE;
                tc.iova            = 0;
                tc.s2_level        = 0;
                tc.s2_flags        = s2_flags;
                tc.s2_rsvd_pattern = 0;
                run_case(&tc, out);
            }
        }
    }

    fprintf(stderr, "✓ [%s] generated %d cases (%zu × %zu reps × 2 access)\n",
            CATEGORY, case_id, NUM_REP_FLAGS, NUM_REP_FLAGS);
    free(g_memory);
    return 0;
}