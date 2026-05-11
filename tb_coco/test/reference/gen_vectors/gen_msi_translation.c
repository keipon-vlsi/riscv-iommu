// gen_msi_translation.c — MSI 翻訳経路の網羅テスト (STAGE_MSI)
//
// Categories per spec §3.1.3 + libiommu:
//   (A) M=3 Basic 成功:           5 idx × 2 ppn × 2 acc = 20
//   (B) V=0 → cause 262:          5 idx × 2 acc = 10
//   (C) C=1 → cause 263:          5
//   (D) M=0 → cause 263:          5
//   (E) M=2 → cause 263:          5
//   (F) M=1 + !msi_mrif → 263:    5
//   (G) M=3 + reserved → 263:     5 idx × 2 patterns = 10
//   (H) MSI 領域外 baseline:      1
// 合計 61 ケース
#include "gen_common.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#define CATEGORY            "msi_translation"
#define MSI_PATTERN          0x0000300000000000ULL
#define IOVA_FOR_INDEX(idx)  (MSI_PATTERN | ((uint64_t)(idx) << 12) | 0x010ULL)

static const uint16_t INDICES[] = { 0, 1, 7, 0x40, 0xFF };
#define N_IDX (sizeof(INDICES)/sizeof(INDICES[0]))

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    gen_common_init();
    FILE *out = stdout;
    int case_id = 0;

    /* (A) Basic success: 5 idx × 2 ppn × 2 acc = 20 */
    {
        static const uint64_t PPNS[] = { 0x200, 0x300 };
        static const access_t ACCS[] = { ACC_READ, ACC_WRITE };
        static const char    *AS[]   = { "r",      "w" };
        for (size_t i = 0; i < N_IDX; i++)
        for (int p = 0; p < 2; p++)
        for (int a = 0; a < 2; a++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name,
                     "msi_basic_idx%03x_ppn%03" PRIx64 "_%s",
                     INDICES[i], PPNS[p], AS[a]);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = STAGE_MSI; tc.access = ACCS[a];
            tc.iova = IOVA_FOR_INDEX(INDICES[i]);
            tc.msi_index = INDICES[i];
            tc.msi_pte_v = 1; tc.msi_pte_c = 0; tc.msi_pte_m = 3;
            tc.msi_pte_ppn = PPNS[p]; tc.msi_pte_rsvd = 0;
            run_case(&tc, out);
        }
    }
    /* (B) V=0 → cause 262: 5 idx × 2 acc = 10 */
    {
        static const access_t ACCS[] = { ACC_READ, ACC_WRITE };
        static const char    *AS[]   = { "r", "w" };
        for (size_t i = 0; i < N_IDX; i++)
        for (int a = 0; a < 2; a++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name, "msi_v0_idx%03x_%s", INDICES[i], AS[a]);
            strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
            tc.stage_mode = STAGE_MSI; tc.access = ACCS[a];
            tc.iova = IOVA_FOR_INDEX(INDICES[i]);
            tc.msi_index = INDICES[i];
            tc.msi_pte_v = 0; tc.msi_pte_c = 0; tc.msi_pte_m = 3;
            tc.msi_pte_ppn = 0x200; tc.msi_pte_rsvd = 0;
            run_case(&tc, out);
        }
    }
    /* (C) C=1 → cause 263: 5 */
    for (size_t i = 0; i < N_IDX; i++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "msi_c1_idx%03x", INDICES[i]);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_MSI; tc.access = ACC_READ;
        tc.iova = IOVA_FOR_INDEX(INDICES[i]);
        tc.msi_index = INDICES[i];
        tc.msi_pte_v = 1; tc.msi_pte_c = 1; tc.msi_pte_m = 3;
        tc.msi_pte_ppn = 0x200; tc.msi_pte_rsvd = 0;
        run_case(&tc, out);
    }
    /* (D) M=0 → cause 263: 5 */
    for (size_t i = 0; i < N_IDX; i++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "msi_m0_idx%03x", INDICES[i]);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_MSI; tc.access = ACC_READ;
        tc.iova = IOVA_FOR_INDEX(INDICES[i]);
        tc.msi_index = INDICES[i];
        tc.msi_pte_v = 1; tc.msi_pte_c = 0; tc.msi_pte_m = 0;
        tc.msi_pte_ppn = 0x200; tc.msi_pte_rsvd = 0;
        run_case(&tc, out);
    }
    /* (E) M=2 → cause 263: 5 */
    for (size_t i = 0; i < N_IDX; i++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "msi_m2_idx%03x", INDICES[i]);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_MSI; tc.access = ACC_READ;
        tc.iova = IOVA_FOR_INDEX(INDICES[i]);
        tc.msi_index = INDICES[i];
        tc.msi_pte_v = 1; tc.msi_pte_c = 0; tc.msi_pte_m = 2;
        tc.msi_pte_ppn = 0x200; tc.msi_pte_rsvd = 0;
        run_case(&tc, out);
    }
    /* (F) M=1 + !msi_mrif → cause 263: 5 */
    for (size_t i = 0; i < N_IDX; i++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "msi_m1_mrif_unsupported_idx%03x", INDICES[i]);
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_MSI; tc.access = ACC_READ;
        tc.iova = IOVA_FOR_INDEX(INDICES[i]);
        tc.msi_index = INDICES[i];
        tc.msi_pte_v = 1; tc.msi_pte_c = 0; tc.msi_pte_m = 1;
        tc.msi_pte_ppn = 0x200; tc.msi_pte_rsvd = 0;
        run_case(&tc, out);
    }
    /* (G) M=3 + reserved bits: 5 idx × 2 patterns = 10 */
    {
        static const uint16_t RSVD_PATTERNS[] = { 0x01, 0x40 };
        for (size_t i = 0; i < N_IDX; i++) {
            for (size_t r = 0; r < sizeof(RSVD_PATTERNS)/sizeof(RSVD_PATTERNS[0]); r++) {
                test_case_t tc = {0};
                tc.case_id = case_id++;
                snprintf(tc.name, sizeof tc.name, "msi_basic_rsvd_idx%03x_r%02x",
                         INDICES[i], RSVD_PATTERNS[r]);
                strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
                tc.stage_mode = STAGE_MSI; tc.access = ACC_READ;
                tc.iova = IOVA_FOR_INDEX(INDICES[i]);
                tc.msi_index = INDICES[i];
                tc.msi_pte_v = 1; tc.msi_pte_c = 0; tc.msi_pte_m = 3;
                tc.msi_pte_ppn = 0x200; tc.msi_pte_rsvd = RSVD_PATTERNS[r];
                run_case(&tc, out);
            }
        }
    }
    /* (H) baseline outside MSI pattern: 1 */
    {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "msi_outside_pattern_baseline");
        strncpy(tc.category, CATEGORY, sizeof tc.category - 1);
        tc.stage_mode = STAGE_MSI; tc.access = ACC_READ;
        tc.iova = 0x0000000000234345ULL;
        tc.msi_index = 0;
        tc.msi_pte_v = 1; tc.msi_pte_c = 0; tc.msi_pte_m = 3;
        tc.msi_pte_ppn = 0x200; tc.msi_pte_rsvd = 0;
        run_case(&tc, out);
    }

    fprintf(stderr, "✓ [%s] generated %d cases\n", CATEGORY, case_id);
    free(g_memory);
    return 0;
}
