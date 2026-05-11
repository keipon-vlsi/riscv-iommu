// gen_common.c — 全 gen_*.c で共有する callback / 設定 / 1 ケース実行
//
// 各 gen_<category>.c はこれを link して、main() で enumeration ループだけ書く。

#include "gen_common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#include "tables_api.h"
#include "iommu_ref_api.h"

// =============================================================================
// グローバル状態
// =============================================================================
int8_t  *g_memory                = NULL;
uint64_t g_access_viol_addr      = (uint64_t)-1;
uint64_t g_data_corruption_addr  = (uint64_t)-1;
uint8_t  pr_go_requested = 0, pw_go_requested = 0;
uint64_t g_next_free_page;
uint64_t g_next_free_gpage[65536];
int      test_endian = LITTLE_ENDIAN;

ats_msg_t exp_msg, rcvd_msg;
uint8_t   exp_msg_received = 0;
uint8_t   message_received = 0;

// =============================================================================
// メモリレイアウト記録 (Option B: replay.py が JSONL から読み取って env を上書き)
//   `mem_layout_t` の typedef は gen_common.h で定義済み。
//   各 run_case_* が静的・動的に確保した PPN をここに集約し、emit_jsonl で出力する。
//   値が 0 のフィールドは「該当カテゴリで未使用」を意味する (= JSONL に出力されない)。
// =============================================================================

// =============================================================================
// libiommu callback 群 (LE only — Phase 1 scope)
// =============================================================================
uint8_t read_memory(uint64_t addr, uint8_t size, char *data,
                     uint32_t rcid, uint32_t mcid, uint32_t pma, int endian) {
    (void)rcid; (void)mcid; (void)pma; (void)endian;
    if (addr == g_access_viol_addr)     return ACCESS_FAULT;
    if (addr == g_data_corruption_addr) return DATA_CORRUPTION;
    if (addr + size > TEST_MEM_SZ)      return ACCESS_FAULT;
    memcpy(data, &g_memory[addr], size);
    return 0;
}
uint8_t read_memory_for_AMO(uint64_t addr, uint8_t size, char *data,
                             uint32_t rcid, uint32_t mcid, uint32_t pma, int endian) {
    return read_memory(addr, size, data, rcid, mcid, pma, endian);
}
uint8_t write_memory(char *data, uint64_t addr, uint32_t size,
                      uint32_t rcid, uint32_t mcid, uint32_t pma, int endian) {
    (void)rcid; (void)mcid; (void)pma; (void)endian;
    if (addr == g_access_viol_addr)     return ACCESS_FAULT;
    if (addr == g_data_corruption_addr) return DATA_CORRUPTION;
    if (addr + size > TEST_MEM_SZ)      return ACCESS_FAULT;
    memcpy(&g_memory[addr], data, size);
    return 0;
}
uint8_t read_memory_test(uint64_t addr, uint8_t size, char *data) {
    return read_memory(addr, size, data, 0, 0, PMA, test_endian);
}
uint8_t write_memory_test(char *data, uint64_t addr, uint32_t size) {
    return write_memory(data, addr, size, 0, 0, PMA, test_endian);
}

void iommu_to_hb_do_global_observability_sync(uint8_t PR, uint8_t PW) {
    pr_go_requested = PR; pw_go_requested = PW;
}
void send_msg_iommu_to_hb(ats_msg_t *msg) {
    memcpy(&rcvd_msg, msg, sizeof(*msg));
    message_received = 1;
}
void handle_virtual_interrupt_file_overlap(device_context_t *DC, uint64_t gpa,
                                            uint64_t *gst_page_sz) {
    (void)DC; (void)gpa; (void)gst_page_sz;
}

uint64_t get_free_ppn(uint64_t num_ppn) {
    uint64_t aligned = (g_next_free_page + num_ppn - 1) & ~(num_ppn - 1);
    g_next_free_page = aligned + num_ppn;
    return aligned;
}
uint64_t get_free_gppn(uint64_t num_gppn, iohgatp_t iohgatp) {
    (void)iohgatp;
    return get_free_ppn(num_gppn);
}

void get_attribs_from_req(hb_to_iommu_req_t *req,
                          uint8_t *read, uint8_t *write,
                          uint8_t *exec, uint8_t *priv) {
    *read = (req->tr.read_writeAMO == READ && req->exec_req
             && req->tr.at == ADDR_TYPE_UNTRANSLATED)
            ? 0
            : (req->tr.read_writeAMO == READ) ? 1 : 0;

    *write = (req->tr.read_writeAMO == WRITE) ? 1 : 0;
    *write = ((req->tr.at == ADDR_TYPE_PCIE_ATS_TRANSLATION_REQUEST)
              && (req->no_write == 0))
             ? 1 : *write;

    *exec = (req->tr.read_writeAMO == READ && req->exec_req
             && (req->tr.at == ADDR_TYPE_UNTRANSLATED || req->pid_valid))
            ? 1 : 0;

    *priv = (req->pid_valid && req->priv_req) ? S_MODE : U_MODE;
}

// =============================================================================
// 共通設定
// =============================================================================
void gen_common_init(void) {
    g_memory = (int8_t *)calloc(1, TEST_MEM_SZ);
    if (!g_memory) { fprintf(stderr, "calloc failed\n"); exit(1); }
    reset_test_state();
}

void reset_test_state(void) {
    memset(g_memory, 0, TEST_MEM_SZ);
    g_next_free_page = 0x100;
    for (int i = 0; i < 65536; i++) g_next_free_gpage[i] = 0x100;
    g_access_viol_addr     = (uint64_t)-1;
    g_data_corruption_addr = (uint64_t)-1;
}

int configure_iommu_phase1(iommu_t *iommu) {
    capabilities_t cap = {0};
    fctl_t         fctl = {0};

    cap.version  = 0x10;
    cap.Sv39     = 1;
    cap.Sv39x4   = 1;
    cap.msi_flat = 1;
    cap.amo_hwad = 0;
    cap.pas      = 50;
    cap.end      = 0;
    cap.igs      = MSI;

    uint64_t bare_pg_sz = 0x40000000ULL;

    return reset_iommu(iommu,
        0, 0, 0,
        3, Off,
        DDT_1LVL, 0xFFFFFF,
        0, 0, 0,
        cap, fctl,
        bare_pg_sz, bare_pg_sz, bare_pg_sz, 0x200000,
        bare_pg_sz, bare_pg_sz, bare_pg_sz, 0x200000);
}

int configure_iommu_pc(iommu_t *iommu) {
    capabilities_t cap = {0};
    fctl_t         fctl = {0};

    cap.version  = 0x10;
    cap.Sv39     = 1;
    cap.Sv39x4   = 1;
    cap.msi_flat = 1;
    cap.amo_hwad = 0;
    cap.pas      = 50;
    cap.end      = 0;
    cap.igs      = MSI;
    cap.pd20     = 1;   // Process Context: 3-level PDT, 20-bit process_id

    uint64_t bare_pg_sz = 0x40000000ULL;

    return reset_iommu(iommu,
        0, 0, 0,
        3, Off,
        DDT_3LVL, 0xFFFFFF,
        0, 0, 0,
        cap, fctl,
        bare_pg_sz, bare_pg_sz, bare_pg_sz, 0x200000,
        bare_pg_sz, bare_pg_sz, bare_pg_sz, 0x200000);
}

int enable_fault_queue(iommu_t *iommu, uint64_t fq_ppn, uint8_t log2szm1) {
    fqb_t   fqb   = {0};
    fqcsr_t fqcsr = {0};
    fqb.ppn      = fq_ppn;
    fqb.log2szm1 = log2szm1;
    write_register(iommu, FQB_OFFSET, 8, fqb.raw);
    fqcsr.fqen = 1;
    fqcsr.fie  = 0;
    write_register(iommu, FQCSR_OFFSET, 4, fqcsr.raw);
    for (int i = 0; i < 100; i++) {
        fqcsr.raw = read_register(iommu, FQCSR_OFFSET, 4);
        if (fqcsr.fqon) return 0;
    }
    return -1;
}

int enable_iommu_1lvl(iommu_t *iommu, uint64_t ddt_ppn) {
    ddtp_t ddtp = {0};
    ddtp.iommu_mode = DDT_1LVL;
    ddtp.ppn        = ddt_ppn;
    write_register(iommu, DDTP_OFFSET, 8, ddtp.raw);
    for (int i = 0; i < 100; i++) {
        ddtp.raw = read_register(iommu, DDTP_OFFSET, 8);
        if (ddtp.busy == 0 && ddtp.iommu_mode == DDT_1LVL) return 0;
    }
    return -1;
}

// =============================================================================
// FaultRecord 抽出
// =============================================================================
typedef struct __attribute__((packed)) {
    uint64_t dw0; uint64_t dw1; uint64_t dw2; uint64_t dw3;
} fault_record_raw_t;

typedef struct {
    int      present;
    uint16_t cause;
    uint8_t  ttyp;
    uint32_t did;
    uint64_t iotval;
    uint64_t iotval2;
} fq_extracted_t;

static fq_extracted_t pop_fault_record(iommu_t *iommu, uint64_t fq_ppn) {
    fq_extracted_t out = {0};
    uint32_t fqh = read_register(iommu, FQH_OFFSET, 4);
    uint32_t fqt = read_register(iommu, FQT_OFFSET, 4);
    if (fqh == fqt) { out.present = 0; return out; }

    fault_record_raw_t rec = {0};
    uint64_t rec_addr = (fq_ppn * PAGESIZE) + (fqh * 32);
    read_memory_test(rec_addr, 32, (char *)&rec);

    out.present = 1;
    out.cause   = (rec.dw0 >>  0) & 0xFFF;
    out.ttyp    = (rec.dw0 >> 34) & 0x3F;
    out.did     = (rec.dw0 >> 40) & 0xFFFFFF;
    out.iotval  = rec.dw2;
    out.iotval2 = rec.dw3;

    write_register(iommu, FQH_OFFSET, 4, fqh + 1);
    return out;
}

// =============================================================================
// PTE 構築ヘルパ — PPN を明示指定したい時に使う (nested_full 用)。
//   misaligned superpage の自動付与を行わない点に注意。
// =============================================================================
static pte_t build_test_pte_with_ppn(uint8_t flags, int rsvd_pattern, uint64_t ppn) {
    pte_t pte = {0};
    if (rsvd_pattern) {
        pte.V = 1; pte.R = 1; pte.W = 1; pte.X = 1;
        pte.U = 1; pte.A = 1; pte.D = 1;
        pte.PPN  = ppn;
        pte.raw |= ((uint64_t)(rsvd_pattern & 0x1FF)) << 54;   /* bits 54..62 */
        if (rsvd_pattern & 0x200) pte.raw |= (1ULL << 63);     /* bit 63 (NAPOT, scope 外 → reserved) */
    } else {
        pte.V = (flags >> 0) & 1;
        pte.R = (flags >> 1) & 1;
        pte.W = (flags >> 2) & 1;
        pte.X = (flags >> 3) & 1;
        pte.U = (flags >> 4) & 1;
        pte.G = (flags >> 5) & 1;
        pte.A = (flags >> 6) & 1;
        pte.D = (flags >> 7) & 1;
        pte.PPN = ppn;
    }
    return pte;
}

// =============================================================================
// PTE 構築ヘルパ — flags / rsvd_pattern から pte_t を作る
// =============================================================================
static pte_t build_test_pte(int level, uint8_t flags, int rsvd_pattern) {
    pte_t pte = {0};
    if (rsvd_pattern) {
        pte.V = 1; pte.R = 1; pte.W = 1; pte.X = 1;
        pte.U = 1; pte.A = 1; pte.D = 1;
        uint64_t ppn = get_free_ppn(1);
        if (rsvd_pattern & 0x200) {
            /* N=1 with PPN[3:0]=8 is valid NAPOT (64 KiB). Force bits[3:0]≠8 to stay invalid. */
            if ((ppn & 0xF) == 8) ppn ^= 1;
        }
        pte.PPN  = ppn;
        pte.raw |= ((uint64_t)(rsvd_pattern & 0x1FF)) << 54;   /* bits 54..62 */
        if (rsvd_pattern & 0x200) pte.raw |= (1ULL << 63);     /* bit 63 (NAPOT, scope 外 → reserved) */
    } else {
        pte.V = (flags >> 0) & 1;
        pte.R = (flags >> 1) & 1;
        pte.W = (flags >> 2) & 1;
        pte.X = (flags >> 3) & 1;
        pte.U = (flags >> 4) & 1;
        pte.G = (flags >> 5) & 1;
        pte.A = (flags >> 6) & 1;
        pte.D = (flags >> 7) & 1;
        if (level > 0 && (pte.R || pte.X)) {
            pte.PPN = get_free_ppn(1) | 0x1;     // Q1 case B: misaligned superpage 強制
        } else {
            pte.PPN = get_free_ppn(1);
        }
    }
    return pte;
}

// =============================================================================
// JSONL emit — 出力形式を全 stage_mode で統一
// =============================================================================
static const char *stage_mode_str(stage_mode_t m) {
    switch (m) {
        case STAGE_S1_ONLY:        return "s1_only";
        case STAGE_S2_ONLY:        return "s2_only";
        case STAGE_NESTED:         return "nested";
        case STAGE_NESTED_FULL:    return "nested_full";
        case STAGE_PC_S1_ONLY:     return "pc_s1_only";
        case STAGE_PC_S2_ONLY:     return "pc_s2_only";
        case STAGE_PC_NESTED:      return "pc_nested";
        case STAGE_PC_NESTED_FULL: return "pc_nested_full";
        case STAGE_BARE_BARE:      return "bare_bare";
        case STAGE_MSI:            return "msi";
        default:                   return "unknown";
    }
}

// alloc フィールド出力ヘルパ — 値が 0 でないものだけ JSON object に追加
static void emit_alloc_field(FILE *out, const mem_layout_t *layout) {
    fprintf(out, "\"alloc\":{");
    int first = 1;
    #define EMIT_ALLOC(name, val) do {                                       \
        if ((val) != 0) {                                                    \
            if (!first) fprintf(out, ",");                                   \
            fprintf(out, "\"" name "\":\"0x%" PRIx64 "\"", (uint64_t)(val)); \
            first = 0;                                                       \
        }                                                                    \
    } while (0)
    EMIT_ALLOC("ddt",          layout->ddt_ppn);
    EMIT_ALLOC("fq",           layout->fq_ppn);
    EMIT_ALLOC("pdt_root",     layout->pdt_root_ppn);
    EMIT_ALLOC("pdt_l1",       layout->pdt_l1_ppn);
    EMIT_ALLOC("pdt_leaf",     layout->pdt_leaf_ppn);
    EMIT_ALLOC("iohgatp_root", layout->iohgatp_root_ppn);
    EMIT_ALLOC("g_mid",        layout->g_mid_ppn);
    EMIT_ALLOC("g_leaf",       layout->g_leaf_ppn);
    EMIT_ALLOC("s1_root",      layout->s1_root_ppn);
    EMIT_ALLOC("s1_mid",       layout->s1_mid_ppn);
    EMIT_ALLOC("s1_leaf",      layout->s1_leaf_ppn);
    EMIT_ALLOC("msi_pt_root",  layout->msi_pt_root_ppn);
    #undef EMIT_ALLOC
    fprintf(out, "},");
}

static void emit_jsonl(FILE *out, const test_case_t *tc,
                       uint64_t iova_used, uint64_t pte_raw,
                       int has_s2, uint64_t s2_pte_raw,
                       const mem_layout_t *layout,
                       const iommu_to_hb_rsp_t *rsp,
                       const fq_extracted_t *fq) {
    const char *category = (tc->category[0]) ? tc->category : "default";

    fprintf(out,
        "{\"case_id\":%d,\"name\":\"%s\",\"category\":\"%s\","
        "\"stage_mode\":\"%s\","
        "\"iova\":\"0x%" PRIx64 "\","
        "\"level\":%d,\"flags\":%u,"
        "\"access\":\"%s\",\"rsvd_pattern\":%d,"
        "\"pte_raw\":\"0x%016" PRIx64 "\",",
        tc->case_id, tc->name, category,
        stage_mode_str(tc->stage_mode),
        iova_used,
        tc->level, tc->flags,
        (tc->access == ACC_READ) ? "read" : "write",
        tc->rsvd_pattern,
        pte_raw);

    if (has_s2) {
        fprintf(out,
            "\"s2_level\":%d,\"s2_flags\":%u,\"s2_rsvd_pattern\":%d,"
            "\"s2_pte_raw\":\"0x%016" PRIx64 "\",",
            tc->s2_level, tc->s2_flags, tc->s2_rsvd_pattern, s2_pte_raw);
    }

    if (tc->stage_mode == STAGE_MSI) {
        fprintf(out,
            "\"msi_index\":%u,\"msi_pte_v\":%u,\"msi_pte_c\":%u,"
            "\"msi_pte_m\":%u,\"msi_pte_ppn\":\"0x%" PRIx64 "\","
            "\"msi_pte_rsvd\":%u,",
            tc->msi_index, tc->msi_pte_v, tc->msi_pte_c,
            tc->msi_pte_m, tc->msi_pte_ppn, tc->msi_pte_rsvd);
    }

    // ★ Option B: alloc field を出力 (replay.py が読んで env を上書きする)
    emit_alloc_field(out, layout);

    fprintf(out,
        "\"status\":%d,\"PPN\":\"0x%" PRIx64 "\",\"S\":%u,",
        (int)rsp->status, rsp->trsp.PPN, rsp->trsp.S);

    if (fq->present) {
        fprintf(out,
            "\"fault\":{\"cause\":%u,\"iotval\":\"0x%" PRIx64 "\","
            "\"iotval2\":\"0x%" PRIx64 "\",\"ttyp\":%u,\"did\":%u}",
            fq->cause, fq->iotval, fq->iotval2, fq->ttyp, fq->did);
    } else {
        fprintf(out, "\"fault\":null");
    }
    fprintf(out, "}\n");
}

// =============================================================================
// run_case_s1_only — S1=Sv39, S2=Bare (= phase1_pte_flags / iova_variation 用)
// =============================================================================
static void run_case_s1_only(const test_case_t *tc, FILE *out) {
    iommu_t iommu = {0};
    if (configure_iommu_phase1(&iommu) < 0) {
        fprintf(stderr, "configure failed at case %d\n", tc->case_id); exit(1);
    }
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn = get_free_ppn(1);
    layout.fq_ppn  = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    device_context_t DC = {0};
    DC.tc.V        = 1;
    DC.fsc.iosatp.MODE = IOSATP_Sv39;
    DC.fsc.iosatp.PPN  = get_free_ppn(1);
    layout.s1_root_ppn = DC.fsc.iosatp.PPN;
    DC.iohgatp.MODE = IOHGATP_Bare;
    DC.msiptp.MODE  = MSIPTP_Off;
    add_dev_context(&iommu, &DC, 0);

    pte_t pte = build_test_pte(tc->level, tc->flags, tc->rsvd_pattern);

    uint64_t iova = (tc->iova != 0) ? tc->iova : 0x002345;
    iosatp_t s1 = DC.fsc.iosatp;

    uint64_t before_s1 = g_next_free_page;
    add_s_stage_pte(s1, iova, pte, tc->level, 0);
    if (g_next_free_page > before_s1) {
        layout.s1_mid_ppn  = before_s1;
        if (g_next_free_page > before_s1 + 1) layout.s1_leaf_ppn = before_s1 + 1;
    }

    hb_to_iommu_req_t req = {0};
    req.device_id = 0;
    req.tr.at = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova   = iova;
    req.tr.length = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, (uint64_t)pte.raw,
               /*has_s2=*/0, /*s2_pte_raw=*/0, &layout, &rsp, &fq);
}

// =============================================================================
// run_case_s2_only — S1=Bare, S2=Sv39x4 (= s2_only 用)
// =============================================================================
static void run_case_s2_only(const test_case_t *tc, FILE *out) {
    iommu_t iommu = {0};
    if (configure_iommu_phase1(&iommu) < 0) exit(1);
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn = get_free_ppn(1);
    layout.fq_ppn  = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    device_context_t DC = {0};
    DC.tc.V        = 1;
    DC.fsc.iosatp.MODE = IOSATP_Bare;
    DC.iohgatp.MODE  = IOHGATP_Sv39x4;
    DC.iohgatp.GSCID = 0;
    DC.iohgatp.PPN   = get_free_ppn(4);
    layout.iohgatp_root_ppn = DC.iohgatp.PPN;
    DC.msiptp.MODE   = MSIPTP_Off;
    add_dev_context(&iommu, &DC, 0);

    pte_t pte = build_test_pte(tc->level, tc->flags, tc->rsvd_pattern);
    gpte_t gpte;
    gpte.raw = pte.raw;

    uint64_t iova = (tc->iova != 0) ? tc->iova : 0x002345;
    iohgatp_t hg = DC.iohgatp;

    uint64_t before_g = g_next_free_page;
    add_g_stage_pte(&iommu, hg, iova, gpte, (uint8_t)tc->level);
    if (g_next_free_page > before_g) {
        layout.g_mid_ppn  = before_g;
        if (g_next_free_page > before_g + 1) layout.g_leaf_ppn = before_g + 1;
    }

    hb_to_iommu_req_t req = {0};
    req.device_id = 0;
    req.tr.at = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova   = iova;
    req.tr.length = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, (uint64_t)gpte.raw,
               /*has_s2=*/0, /*s2_pte_raw=*/0, &layout, &rsp, &fq);
}

// =============================================================================
// run_case_nested — S1=Sv39 + S2=Sv39x4 (= nested 用)
// =============================================================================
static void run_case_nested(const test_case_t *tc, FILE *out) {
    iommu_t iommu = {0};
    if (configure_iommu_phase1(&iommu) < 0) exit(1);
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn = get_free_ppn(1);
    layout.fq_ppn  = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    device_context_t DC = {0};
    DC.tc.V        = 1;
    DC.fsc.iosatp.MODE = IOSATP_Sv39;
    DC.fsc.iosatp.PPN  = get_free_ppn(1);
    layout.s1_root_ppn = DC.fsc.iosatp.PPN;
    DC.iohgatp.MODE  = IOHGATP_Sv39x4;
    DC.iohgatp.GSCID = 0;
    DC.iohgatp.PPN   = get_free_ppn(4);
    layout.iohgatp_root_ppn = DC.iohgatp.PPN;
    DC.msiptp.MODE   = MSIPTP_Off;
    add_dev_context(&iommu, &DC, 0);

    // S2 identity 4K mappings for 0x100..0x17F
    iohgatp_t hg = DC.iohgatp;
    pte_t s2_pte_template = {0};
    s2_pte_template.V = 1; s2_pte_template.R = 1; s2_pte_template.W = 1; s2_pte_template.X = 1;
    s2_pte_template.U = 1; s2_pte_template.A = 1; s2_pte_template.D = 1;

    uint64_t before_s2 = g_next_free_page;
    for (uint64_t ppn = 0x100; ppn < 0x180; ppn++) {
        pte_t s2_pte = s2_pte_template;
        s2_pte.PPN = ppn;
        gpte_t s2_gpte;
        s2_gpte.raw = s2_pte.raw;
        add_g_stage_pte(&iommu, hg, ppn << 12, s2_gpte, /*add_level=*/0);
    }
    // 1st add_g_stage_pte で intermediate 2 ページ alloc されたはず
    if (g_next_free_page > before_s2) {
        layout.g_mid_ppn  = before_s2;
        if (g_next_free_page > before_s2 + 1) layout.g_leaf_ppn = before_s2 + 1;
    }

    pte_t s2_identity_pte = s2_pte_template;
    s2_identity_pte.PPN = 0x100;
    gpte_t s2_identity;
    s2_identity.raw = s2_identity_pte.raw;

    pte_t s1_pte = build_test_pte(tc->level, tc->flags, tc->rsvd_pattern);

    uint64_t iova = (tc->iova != 0) ? tc->iova : 0x002345;
    iosatp_t s1 = DC.fsc.iosatp;

    uint64_t before_s1 = g_next_free_page;
    add_s_stage_pte(s1, iova, s1_pte, tc->level, 0);
    if (g_next_free_page > before_s1) {
        layout.s1_mid_ppn  = before_s1;
        if (g_next_free_page > before_s1 + 1) layout.s1_leaf_ppn = before_s1 + 1;
    }

    hb_to_iommu_req_t req = {0};
    req.device_id = 0;
    req.tr.at = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova   = iova;
    req.tr.length = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, (uint64_t)s1_pte.raw,
               /*has_s2=*/1, /*s2_pte_raw=*/(uint64_t)s2_identity.raw,
               &layout, &rsp, &fq);
}

// =============================================================================
// run_case_nested_full — S1/S2 両 leaf 可変
// =============================================================================
static void run_case_nested_full(const test_case_t *tc, FILE *out) {
    static const uint64_t S1_LEAF_PPN  = 0x150;
    static const uint64_t S2_TEST_PPN  = 0x250;

    iommu_t iommu = {0};
    if (configure_iommu_phase1(&iommu) < 0) exit(1);
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn = get_free_ppn(1);
    layout.fq_ppn  = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    device_context_t DC = {0};
    DC.tc.V        = 1;
    DC.fsc.iosatp.MODE = IOSATP_Sv39;
    DC.fsc.iosatp.PPN  = get_free_ppn(1);
    layout.s1_root_ppn = DC.fsc.iosatp.PPN;
    DC.iohgatp.MODE  = IOHGATP_Sv39x4;
    DC.iohgatp.GSCID = 0;
    DC.iohgatp.PPN   = get_free_ppn(4);
    layout.iohgatp_root_ppn = DC.iohgatp.PPN;
    DC.msiptp.MODE   = MSIPTP_Off;
    add_dev_context(&iommu, &DC, 0);

    iohgatp_t hg = DC.iohgatp;

    pte_t s1_pte     = build_test_pte_with_ppn(tc->flags,    tc->rsvd_pattern,    S1_LEAF_PPN);
    pte_t s2_test_pte = build_test_pte_with_ppn(tc->s2_flags, tc->s2_rsvd_pattern, S2_TEST_PPN);

    pte_t s2_id_template = {0};
    s2_id_template.V = 1; s2_id_template.R = 1; s2_id_template.W = 1; s2_id_template.X = 1;
    s2_id_template.U = 1; s2_id_template.A = 1; s2_id_template.D = 1;

    uint64_t before_s2 = g_next_free_page;
    for (uint64_t ppn = 0x100; ppn < 0x180; ppn++) {
        if (ppn == S1_LEAF_PPN) continue;
        pte_t s2_id = s2_id_template;
        s2_id.PPN = ppn;
        gpte_t gpte;
        gpte.raw = s2_id.raw;
        add_g_stage_pte(&iommu, hg, ppn << 12, gpte, /*add_level=*/0);
    }
    if (g_next_free_page > before_s2) {
        layout.g_mid_ppn  = before_s2;
        if (g_next_free_page > before_s2 + 1) layout.g_leaf_ppn = before_s2 + 1;
    }

    gpte_t s2_test_gpte;
    s2_test_gpte.raw = s2_test_pte.raw;
    add_g_stage_pte(&iommu, hg, S1_LEAF_PPN << 12, s2_test_gpte, /*add_level=*/0);

    uint64_t iova = (tc->iova != 0) ? tc->iova : 0x002345;
    iosatp_t s1 = DC.fsc.iosatp;

    uint64_t before_s1 = g_next_free_page;
    add_s_stage_pte(s1, iova, s1_pte, tc->level, 0);
    if (g_next_free_page > before_s1) {
        layout.s1_mid_ppn  = before_s1;
        if (g_next_free_page > before_s1 + 1) layout.s1_leaf_ppn = before_s1 + 1;
    }

    hb_to_iommu_req_t req = {0};
    req.device_id = 0;
    req.tr.at = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova   = iova;
    req.tr.length = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, (uint64_t)s1_pte.raw,
               /*has_s2=*/1, /*s2_pte_raw=*/(uint64_t)s2_test_pte.raw,
               &layout, &rsp, &fq);
}

// =============================================================================
// run_case_pc_s1_only — PDTV=1, PC.fsc=Sv39, S2=Bare
// =============================================================================
static void run_case_pc_s1_only(const test_case_t *tc, FILE *out) {
    iommu_t iommu = {0};
    if (configure_iommu_pc(&iommu) < 0) exit(1);
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn      = get_free_ppn(1);
    layout.fq_ppn       = get_free_ppn(1);
    layout.pdt_root_ppn = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    device_context_t DC = {0};
    DC.tc.V    = 1;
    DC.tc.PDTV = 1;
    DC.fsc.pdtp.MODE = PD20;
    DC.fsc.pdtp.PPN  = layout.pdt_root_ppn;
    DC.iohgatp.MODE  = IOHGATP_Bare;
    DC.msiptp.MODE   = MSIPTP_Off;
    add_dev_context(&iommu, &DC, 0);

    process_context_t PC = {0};
    PC.ta.V     = 1;
    PC.ta.ENS   = 1;
    PC.ta.SUM   = 1;
    PC.ta.PSCID = PC_PSCID_FIXED;
    PC.fsc.iosatp.MODE = IOSATP_Sv39;
    PC.fsc.iosatp.PPN  = get_free_ppn(1);
    layout.s1_root_ppn = PC.fsc.iosatp.PPN;

    uint64_t before_pdt = g_next_free_page;
    add_process_context(&iommu, &DC, &PC, PC_PROCESS_ID_FIXED);
    if (g_next_free_page > before_pdt) {
        layout.pdt_l1_ppn   = before_pdt;
        if (g_next_free_page > before_pdt + 1) layout.pdt_leaf_ppn = before_pdt + 1;
    }

    pte_t pte = build_test_pte(tc->level, tc->flags, tc->rsvd_pattern);

    uint64_t iova = (tc->iova != 0) ? tc->iova : 0x002345;

    uint64_t before_s1 = g_next_free_page;
    add_s_stage_pte(PC.fsc.iosatp, iova, pte, tc->level, 0);
    if (g_next_free_page > before_s1) {
        layout.s1_mid_ppn  = before_s1;
        if (g_next_free_page > before_s1 + 1) layout.s1_leaf_ppn = before_s1 + 1;
    }

    hb_to_iommu_req_t req = {0};
    req.device_id  = 0;
    req.pid_valid  = 1;
    req.process_id = PC_PROCESS_ID_FIXED;
    req.tr.at      = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova    = iova;
    req.tr.length  = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write   = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, (uint64_t)pte.raw,
               /*has_s2=*/0, /*s2_pte_raw=*/0, &layout, &rsp, &fq);
}

// =============================================================================
// run_case_pc_s2_only — PDTV=1, PC.fsc=Bare, S2=Sv39x4
// =============================================================================
static void run_case_pc_s2_only(const test_case_t *tc, FILE *out) {
    iommu_t iommu = {0};
    if (configure_iommu_pc(&iommu) < 0) exit(1);
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn      = get_free_ppn(1);
    layout.fq_ppn       = get_free_ppn(1);
    layout.pdt_root_ppn = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    device_context_t DC = {0};
    DC.tc.V    = 1;
    DC.tc.PDTV = 1;
    DC.fsc.pdtp.MODE  = PD20;
    DC.fsc.pdtp.PPN   = layout.pdt_root_ppn;
    DC.iohgatp.MODE   = IOHGATP_Sv39x4;
    DC.iohgatp.GSCID  = 0;
    DC.iohgatp.PPN    = get_free_ppn(4);
    layout.iohgatp_root_ppn = DC.iohgatp.PPN;
    DC.msiptp.MODE    = MSIPTP_Off;
    add_dev_context(&iommu, &DC, 0);

    // S2 identity for 0x100..0x17F
    iohgatp_t hg = DC.iohgatp;
    pte_t s2_id_tmpl = {0};
    s2_id_tmpl.V = 1; s2_id_tmpl.R = 1; s2_id_tmpl.W = 1; s2_id_tmpl.X = 1;
    s2_id_tmpl.U = 1; s2_id_tmpl.A = 1; s2_id_tmpl.D = 1;

    uint64_t before_s2 = g_next_free_page;
    for (uint64_t ppn = 0x100; ppn < 0x180; ppn++) {
        pte_t s2p = s2_id_tmpl;
        s2p.PPN = ppn;
        gpte_t gp; gp.raw = s2p.raw;
        add_g_stage_pte(&iommu, hg, ppn << 12, gp, /*add_level=*/0);
    }
    if (g_next_free_page > before_s2) {
        layout.g_mid_ppn  = before_s2;
        if (g_next_free_page > before_s2 + 1) layout.g_leaf_ppn = before_s2 + 1;
    }

    process_context_t PC = {0};
    PC.ta.V     = 1;
    PC.ta.ENS   = 1;
    PC.ta.SUM   = 1;
    PC.ta.PSCID = PC_PSCID_FIXED;
    PC.fsc.iosatp.MODE = IOSATP_Bare;

    uint64_t before_pdt = g_next_free_page;
    add_process_context(&iommu, &DC, &PC, PC_PROCESS_ID_FIXED);
    if (g_next_free_page > before_pdt) {
        layout.pdt_l1_ppn   = before_pdt;
        if (g_next_free_page > before_pdt + 1) layout.pdt_leaf_ppn = before_pdt + 1;
    }

    pte_t pte = build_test_pte(tc->level, tc->flags, tc->rsvd_pattern);
    gpte_t gpte; gpte.raw = pte.raw;
    uint64_t iova = (tc->iova != 0) ? tc->iova : 0x002345;
    add_g_stage_pte(&iommu, hg, iova, gpte, (uint8_t)tc->level);

    hb_to_iommu_req_t req = {0};
    req.device_id  = 0;
    req.pid_valid  = 1;
    req.process_id = PC_PROCESS_ID_FIXED;
    req.tr.at      = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova    = iova;
    req.tr.length  = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write   = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, (uint64_t)gpte.raw,
               /*has_s2=*/0, /*s2_pte_raw=*/0, &layout, &rsp, &fq);
}

// =============================================================================
// run_case_pc_nested — PDTV=1, PC.fsc=Sv39, S2=Sv39x4 identity 固定
// =============================================================================
static void run_case_pc_nested(const test_case_t *tc, FILE *out) {
    iommu_t iommu = {0};
    if (configure_iommu_pc(&iommu) < 0) exit(1);
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn      = get_free_ppn(1);
    layout.fq_ppn       = get_free_ppn(1);
    layout.pdt_root_ppn = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    device_context_t DC = {0};
    DC.tc.V    = 1;
    DC.tc.PDTV = 1;
    DC.fsc.pdtp.MODE  = PD20;
    DC.fsc.pdtp.PPN   = layout.pdt_root_ppn;
    DC.iohgatp.MODE   = IOHGATP_Sv39x4;
    DC.iohgatp.GSCID  = 0;
    DC.iohgatp.PPN    = get_free_ppn(4);
    layout.iohgatp_root_ppn = DC.iohgatp.PPN;
    DC.msiptp.MODE    = MSIPTP_Off;
    add_dev_context(&iommu, &DC, 0);

    // S2 identity for 0x100..0x17F
    iohgatp_t hg = DC.iohgatp;
    gpte_t s2_id_tmpl = {0};
    s2_id_tmpl.V = 1; s2_id_tmpl.R = 1; s2_id_tmpl.W = 1; s2_id_tmpl.X = 1;
    s2_id_tmpl.U = 1; s2_id_tmpl.A = 1; s2_id_tmpl.D = 1;

    uint64_t before_s2 = g_next_free_page;
    for (uint64_t ppn = 0x100; ppn < 0x180; ppn++) {
        gpte_t gp = s2_id_tmpl;
        gp.PPN = ppn;
        add_g_stage_pte(&iommu, hg, ppn << 12, gp, /*add_level=*/0);
    }
    if (g_next_free_page > before_s2) {
        layout.g_mid_ppn  = before_s2;
        if (g_next_free_page > before_s2 + 1) layout.g_leaf_ppn = before_s2 + 1;
    }

    gpte_t s2_identity_rep = s2_id_tmpl;
    s2_identity_rep.PPN = 0x100;

    process_context_t PC = {0};
    PC.ta.V     = 1;
    PC.ta.ENS   = 1;
    PC.ta.SUM   = 1;
    PC.ta.PSCID = PC_PSCID_FIXED;
    PC.fsc.iosatp.MODE = IOSATP_Sv39;
    PC.fsc.iosatp.PPN  = get_free_ppn(1);
    layout.s1_root_ppn = PC.fsc.iosatp.PPN;

    uint64_t before_pdt = g_next_free_page;
    add_process_context(&iommu, &DC, &PC, PC_PROCESS_ID_FIXED);
    if (g_next_free_page > before_pdt) {
        layout.pdt_l1_ppn   = before_pdt;
        if (g_next_free_page > before_pdt + 1) layout.pdt_leaf_ppn = before_pdt + 1;
    }

    pte_t s1_pte = build_test_pte(tc->level, tc->flags, tc->rsvd_pattern);
    uint64_t iova = (tc->iova != 0) ? tc->iova : 0x002345;

    uint64_t before_s1 = g_next_free_page;
    add_s_stage_pte(PC.fsc.iosatp, iova, s1_pte, tc->level, 0);
    if (g_next_free_page > before_s1) {
        layout.s1_mid_ppn  = before_s1;
        if (g_next_free_page > before_s1 + 1) layout.s1_leaf_ppn = before_s1 + 1;
    }

    hb_to_iommu_req_t req = {0};
    req.device_id  = 0;
    req.pid_valid  = 1;
    req.process_id = PC_PROCESS_ID_FIXED;
    req.tr.at      = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova    = iova;
    req.tr.length  = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write   = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, (uint64_t)s1_pte.raw,
               /*has_s2=*/1, /*s2_pte_raw=*/(uint64_t)s2_identity_rep.raw,
               &layout, &rsp, &fq);
}

// =============================================================================
// run_case_pc_nested_full — PDTV=1, PC.fsc=Sv39 + S2=Sv39x4。S1/S2 両 leaf 可変。
// =============================================================================
static void run_case_pc_nested_full(const test_case_t *tc, FILE *out) {
    static const uint64_t S1_LEAF_PPN = 0x150;
    static const uint64_t S2_TEST_PPN = 0x250;

    iommu_t iommu = {0};
    if (configure_iommu_pc(&iommu) < 0) exit(1);
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn      = get_free_ppn(1);
    layout.fq_ppn       = get_free_ppn(1);
    layout.pdt_root_ppn = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    device_context_t DC = {0};
    DC.tc.V    = 1;
    DC.tc.PDTV = 1;
    DC.fsc.pdtp.MODE  = PD20;
    DC.fsc.pdtp.PPN   = layout.pdt_root_ppn;
    DC.iohgatp.MODE   = IOHGATP_Sv39x4;
    DC.iohgatp.GSCID  = 0;
    DC.iohgatp.PPN    = get_free_ppn(4);
    layout.iohgatp_root_ppn = DC.iohgatp.PPN;
    DC.msiptp.MODE    = MSIPTP_Off;
    add_dev_context(&iommu, &DC, 0);

    iohgatp_t hg = DC.iohgatp;

    pte_t s1_pte  = build_test_pte_with_ppn(tc->flags,    tc->rsvd_pattern,    S1_LEAF_PPN);
    pte_t s2_test = build_test_pte_with_ppn(tc->s2_flags, tc->s2_rsvd_pattern, S2_TEST_PPN);

    pte_t s2_id_tmpl = {0};
    s2_id_tmpl.V = 1; s2_id_tmpl.R = 1; s2_id_tmpl.W = 1; s2_id_tmpl.X = 1;
    s2_id_tmpl.U = 1; s2_id_tmpl.A = 1; s2_id_tmpl.D = 1;

    uint64_t before_s2 = g_next_free_page;
    for (uint64_t ppn = 0x100; ppn < 0x180; ppn++) {
        if (ppn == S1_LEAF_PPN) continue;
        pte_t s2p = s2_id_tmpl;
        s2p.PPN = ppn;
        gpte_t gp; gp.raw = s2p.raw;
        add_g_stage_pte(&iommu, hg, ppn << 12, gp, /*add_level=*/0);
    }
    if (g_next_free_page > before_s2) {
        layout.g_mid_ppn  = before_s2;
        if (g_next_free_page > before_s2 + 1) layout.g_leaf_ppn = before_s2 + 1;
    }

    process_context_t PC = {0};
    PC.ta.V     = 1;
    PC.ta.ENS   = 1;
    PC.ta.SUM   = 1;
    PC.ta.PSCID = PC_PSCID_FIXED;
    PC.fsc.iosatp.MODE = IOSATP_Sv39;
    PC.fsc.iosatp.PPN  = get_free_ppn(1);
    layout.s1_root_ppn = PC.fsc.iosatp.PPN;

    uint64_t before_pdt = g_next_free_page;
    add_process_context(&iommu, &DC, &PC, PC_PROCESS_ID_FIXED);
    if (g_next_free_page > before_pdt) {
        layout.pdt_l1_ppn   = before_pdt;
        if (g_next_free_page > before_pdt + 1) layout.pdt_leaf_ppn = before_pdt + 1;
    }

    gpte_t s2_test_gpte; s2_test_gpte.raw = s2_test.raw;
    add_g_stage_pte(&iommu, hg, S1_LEAF_PPN << 12, s2_test_gpte, /*add_level=*/0);

    uint64_t iova = (tc->iova != 0) ? tc->iova : 0x002345;

    uint64_t before_s1 = g_next_free_page;
    add_s_stage_pte(PC.fsc.iosatp, iova, s1_pte, tc->level, 0);
    if (g_next_free_page > before_s1) {
        layout.s1_mid_ppn  = before_s1;
        if (g_next_free_page > before_s1 + 1) layout.s1_leaf_ppn = before_s1 + 1;
    }

    hb_to_iommu_req_t req = {0};
    req.device_id  = 0;
    req.pid_valid  = 1;
    req.process_id = PC_PROCESS_ID_FIXED;
    req.tr.at      = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova    = iova;
    req.tr.length  = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write   = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, (uint64_t)s1_pte.raw,
               /*has_s2=*/1, /*s2_pte_raw=*/(uint64_t)s2_test.raw,
               &layout, &rsp, &fq);
}

// =============================================================================
// run_case_bare_bare — S1=Bare, S2=Bare (= 純粋 Bare DC)
//
// 期待: IOVA = SPA、PT 不要、translate 成功で PPN=iova>>12 が返る。
// bare_pg_sz を 4 KiB にすることで PPN=IOVA>>12, S=0 の応答になる。
// =============================================================================
static int configure_iommu_bare_bare(iommu_t *iommu) {
    capabilities_t cap = {0};
    fctl_t         fctl = {0};
    cap.version  = 0x10;
    cap.Sv39     = 1;
    cap.Sv39x4   = 1;
    cap.msi_flat = 1;
    cap.amo_hwad = 0;
    cap.pas      = 50;
    cap.end      = 0;
    cap.igs      = MSI;
    /* Use 4 KiB bare page granularity so bare translation gives PPN=IOVA>>12, S=0 */
    uint64_t pg = 4096ULL;
    return reset_iommu(iommu,
        0, 0, 0,
        3, Off,
        DDT_1LVL, 0xFFFFFF,
        0, 0, 0,
        cap, fctl,
        pg, pg, pg, pg,
        pg, pg, pg, pg);
}

static void run_case_bare_bare(const test_case_t *tc, FILE *out) {
    iommu_t iommu = {0};
    if (configure_iommu_bare_bare(&iommu) < 0) exit(1);
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn = get_free_ppn(1);
    layout.fq_ppn  = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    device_context_t DC = {0};
    DC.tc.V         = 1;
    DC.fsc.iosatp.MODE = IOSATP_Bare;
    DC.iohgatp.MODE = IOHGATP_Bare;
    DC.msiptp.MODE  = MSIPTP_Off;
    add_dev_context(&iommu, &DC, 0);

    uint64_t iova = (tc->iova != 0) ? tc->iova : 0x002345;

    hb_to_iommu_req_t req = {0};
    req.device_id = 0;
    req.tr.at     = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova   = iova;
    req.tr.length = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write         = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, /*pte_raw=*/0,
               /*has_s2=*/0, /*s2_pte_raw=*/0, &layout, &rsp, &fq);
}

// =============================================================================
// run_case_msi — S1=Sv39, S2=Sv39x4, msiptp=Flat
//
// MSI PTE format (16B):
//   bit  0      : V
//   bits 2:1    : M
//   bits 9:3    : reserved
//   bits 53:10  : PPN
//   bits 62:54  : reserved
//   bit  63     : C
// =============================================================================
#define MSI_PATTERN  0x0000300000000000ULL
#define MSI_MASK     0x000000FFFFFF000ULL

static uint64_t build_msi_pte(uint8_t v, uint8_t m, uint8_t c,
                               uint64_t ppn, uint16_t rsvd_3_9) {
    uint64_t raw = 0;
    raw |= ((uint64_t)(v & 1));
    raw |= ((uint64_t)(m & 3))   << 1;
    raw |= ((uint64_t)(rsvd_3_9 & 0x7F)) << 3;
    raw |= (ppn & ((1ULL << 44) - 1)) << 10;
    raw |= ((uint64_t)(c & 1))   << 63;
    return raw;
}

static void run_case_msi(const test_case_t *tc, FILE *out) {
    iommu_t iommu = {0};
    if (configure_iommu_phase1(&iommu) < 0) exit(1);
    reset_test_state();

    mem_layout_t layout = {0};

    layout.ddt_ppn = get_free_ppn(1);
    layout.fq_ppn  = get_free_ppn(1);
    if (enable_fault_queue(&iommu, layout.fq_ppn, 4) < 0) exit(1);
    if (enable_iommu_1lvl(&iommu, layout.ddt_ppn) < 0)    exit(1);

    layout.msi_pt_root_ppn = get_free_ppn(1);

    device_context_t DC = {0};
    DC.tc.V            = 1;
    DC.fsc.iosatp.MODE = IOSATP_Sv39;
    DC.fsc.iosatp.PPN  = get_free_ppn(1);
    layout.s1_root_ppn = DC.fsc.iosatp.PPN;
    DC.iohgatp.MODE    = IOHGATP_Sv39x4;
    DC.iohgatp.GSCID   = 0;
    DC.iohgatp.PPN     = get_free_ppn(4);
    layout.iohgatp_root_ppn = DC.iohgatp.PPN;

    DC.msiptp.MODE     = MSIPTP_Flat;
    DC.msiptp.PPN      = layout.msi_pt_root_ppn;
    DC.msi_addr_pattern.pattern = (MSI_PATTERN >> 12);
    DC.msi_addr_mask.mask       = (MSI_MASK    >> 12);
    add_dev_context(&iommu, &DC, 0);

    uint64_t pte_lo = build_msi_pte(tc->msi_pte_v, tc->msi_pte_m, tc->msi_pte_c,
                                     tc->msi_pte_ppn, tc->msi_pte_rsvd);
    uint64_t pte_hi = 0;
    uint64_t pte_addr = (layout.msi_pt_root_ppn << 12) + ((uint64_t)tc->msi_index * 16);
    write_memory_test((char *)&pte_lo, pte_addr,     8);
    write_memory_test((char *)&pte_hi, pte_addr + 8, 8);

    iohgatp_t hg = DC.iohgatp;
    pte_t s2_id = {0};
    s2_id.V = 1; s2_id.R = 1; s2_id.W = 1; s2_id.X = 1;
    s2_id.U = 1; s2_id.A = 1; s2_id.D = 1;
    s2_id.PPN = layout.msi_pt_root_ppn;
    gpte_t s2_id_gpte; s2_id_gpte.raw = s2_id.raw;

    uint64_t before_s2 = g_next_free_page;
    add_g_stage_pte(&iommu, hg, layout.msi_pt_root_ppn << 12, s2_id_gpte, /*level=*/0);
    if (g_next_free_page > before_s2) {
        layout.g_mid_ppn  = before_s2;
        if (g_next_free_page > before_s2 + 1) layout.g_leaf_ppn = before_s2 + 1;
    }

    iosatp_t s1 = DC.fsc.iosatp;
    pte_t s1_pte = {0};
    s1_pte.V = 1; s1_pte.R = 1; s1_pte.W = 1; s1_pte.X = 1;
    s1_pte.U = 1; s1_pte.A = 1; s1_pte.D = 1;

    uint64_t iova = (tc->iova != 0)
                    ? tc->iova
                    : (MSI_PATTERN | ((uint64_t)tc->msi_index << 12) | 0x010ULL);
    s1_pte.PPN = (iova >> 12);

    uint64_t before_s1 = g_next_free_page;
    add_s_stage_pte(s1, iova, s1_pte, /*level=*/0, 0);
    if (g_next_free_page > before_s1) {
        layout.s1_mid_ppn  = before_s1;
        if (g_next_free_page > before_s1 + 1) layout.s1_leaf_ppn = before_s1 + 1;
    }

    hb_to_iommu_req_t req = {0};
    req.device_id = 0;
    req.tr.at     = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova   = iova;
    req.tr.length = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write         = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);
    fq_extracted_t fq = pop_fault_record(&iommu, layout.fq_ppn);

    emit_jsonl(out, tc, iova, pte_lo,
               /*has_s2=*/0, /*s2_pte_raw=*/0, &layout, &rsp, &fq);
}

// =============================================================================
// dispatcher
// =============================================================================
void run_case(const test_case_t *tc, FILE *out) {
    switch (tc->stage_mode) {
        case STAGE_S1_ONLY:        run_case_s1_only(tc, out);        break;
        case STAGE_S2_ONLY:        run_case_s2_only(tc, out);        break;
        case STAGE_NESTED:         run_case_nested(tc, out);         break;
        case STAGE_NESTED_FULL:    run_case_nested_full(tc, out);    break;
        case STAGE_PC_S1_ONLY:     run_case_pc_s1_only(tc, out);     break;
        case STAGE_PC_S2_ONLY:     run_case_pc_s2_only(tc, out);     break;
        case STAGE_PC_NESTED:      run_case_pc_nested(tc, out);      break;
        case STAGE_PC_NESTED_FULL: run_case_pc_nested_full(tc, out); break;
        case STAGE_BARE_BARE:      run_case_bare_bare(tc, out);      break;
        case STAGE_MSI:            run_case_msi(tc, out);            break;
        default:
            fprintf(stderr, "unknown stage_mode %d at case %d\n",
                    tc->stage_mode, tc->case_id);
            exit(1);
    }
}