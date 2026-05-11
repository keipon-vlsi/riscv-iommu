// gen_pc_iova_variation.c — PDTV=1 + PC.fsc=Sv39 の IOVA 境界値網羅
//
// =============================================================================
//  gen_iova_variation.c の PC (Process Context) 版。
//
//  固定軸
//   - DC.tc.PDTV = 1、DC.fsc.pdtp.MODE = PD20
//   - process_id = PC_PROCESS_ID_FIXED (0x42)
//   - PC.ta.PSCID = PC_PSCID_FIXED (0x100)、V=ENS=SUM=1
//   - PC.fsc.iosatp.MODE = Sv39、S2 = Bare
//   - PTE フラグ : LEAF_VALID_FLAGS (0xDF) 固定
//
//  ケース内訳 (iova_variation と同一)
//   8 × 8 × 8 × 2 = 1024 ケース
// =============================================================================

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATEGORY         "pc_iova_variation"
#define LEAF_VALID_FLAGS  0xDF
#define PAGE_OFFSET       0x345

static const uint64_t VPN_BOUNDARIES[] = {
    0x000, 0x001, 0x0FF, 0x100, 0x101, 0x1FD, 0x1FE, 0x1FF,
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
                             "pc_iova_v2_%03lx_v1_%03lx_v0_%03lx_%s",
                             (unsigned long)vpn2,
                             (unsigned long)vpn1,
                             (unsigned long)vpn0,
                             acc == 0 ? "r" : "w");
                    strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
                    tc.stage_mode   = STAGE_PC_S1_ONLY;
                    tc.level        = 0;
                    tc.flags        = LEAF_VALID_FLAGS;
                    tc.access       = acc == 0 ? ACC_READ : ACC_WRITE;
                    tc.rsvd_pattern = 0;
                    tc.iova         = iova;
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
