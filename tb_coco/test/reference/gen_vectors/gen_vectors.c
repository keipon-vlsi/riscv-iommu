// gen_vectors.c
//
// Drives ved-rivos/iommu-reference (libiommu + libtables) to enumerate
// all PTE-flag combinations × placement levels × access types for a
// Sv39 1-stage walk (PDTV=0, no PC, G-stage Bare).  Emits the reference
// model's response as JSONL — one record per test case.
//
// Output (one line per case, JSONL format):
//   {"case_id":N,"name":"...","level":L,"flags":F,"access":"read"|"write",
//    "rsvd_pattern":R,"status":S,"PPN":"0xHEX","S":B,
//    "fault":{"cause":C,"iotval":"0xHEX","iotval2":"0xHEX","ttyp":T} | null}
//
// Build:  see Makefile in the same directory.
// Run:    ./gen_vectors > golden_vectors.jsonl
//
// Phase 1 scope (Phase 2+ extends to PDTV=1, S2, fetch, etc.)

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#include "iommu.h"
#include "tables_api.h"
#include "iommu_ref_api.h"

// =============================================================================
// Global TB state required by libiommu callbacks
// =============================================================================
#define TEST_MEM_SZ  (256ULL * 1024 * 1024)   // 256 MiB sparse-ish

int8_t  *memory = NULL;
uint64_t access_viol_addr      = (uint64_t)-1;
uint64_t data_corruption_addr  = (uint64_t)-1;
uint8_t  pr_go_requested = 0, pw_go_requested = 0;
uint64_t next_free_page;
uint64_t next_free_gpage[65536];
int      test_endian = LITTLE_ENDIAN;

ats_msg_t exp_msg, rcvd_msg;
uint8_t   exp_msg_received = 0;
uint8_t   message_received = 0;

// =============================================================================
// Memory callbacks (LE only — Phase 1 scope is LE-only)
// =============================================================================
uint8_t read_memory(uint64_t addr, uint8_t size, char *data,
                     uint32_t rcid, uint32_t mcid, uint32_t pma, int endian) {
    (void)rcid; (void)mcid; (void)pma; (void)endian;
    if (addr == access_viol_addr)     return ACCESS_FAULT;
    if (addr == data_corruption_addr) return DATA_CORRUPTION;
    if (addr + size > TEST_MEM_SZ)    return ACCESS_FAULT;
    memcpy(data, &memory[addr], size);
    return 0;
}
uint8_t read_memory_for_AMO(uint64_t addr, uint8_t size, char *data,
                             uint32_t rcid, uint32_t mcid, uint32_t pma, int endian) {
    return read_memory(addr, size, data, rcid, mcid, pma, endian);
}
uint8_t write_memory(char *data, uint64_t addr, uint32_t size,
                      uint32_t rcid, uint32_t mcid, uint32_t pma, int endian) {
    (void)rcid; (void)mcid; (void)pma; (void)endian;
    if (addr == access_viol_addr)     return ACCESS_FAULT;
    if (addr == data_corruption_addr) return DATA_CORRUPTION;
    if (addr + size > TEST_MEM_SZ)    return ACCESS_FAULT;
    memcpy(&memory[addr], data, size);
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

// libtables allocator hooks
uint64_t get_free_ppn(uint64_t num_ppn) {
    uint64_t aligned = (next_free_page + num_ppn - 1) & ~(num_ppn - 1);
    next_free_page = aligned + num_ppn;
    return aligned;
}
uint64_t get_free_gppn(uint64_t num_gppn, iohgatp_t iohgatp) {
    (void)iohgatp;
    return get_free_ppn(num_gppn);
}

// =============================================================================
// get_attribs_from_req — libiommu の必須 callback。
// iommu_ref_model/test/tbapi.c の同名関数からそのまま移植。
// 翻訳要求から read/write/exec/priv 属性を抜き出して返す。
// =============================================================================
void get_attribs_from_req(hb_to_iommu_req_t *req,
                          uint8_t *read, uint8_t *write,
                          uint8_t *exec, uint8_t *priv) {
    *read = (req->tr.read_writeAMO == READ && req->exec_req
             && req->tr.at == ADDR_TYPE_UNTRANSLATED)
            ? 0
            : (req->tr.read_writeAMO == READ) ? 1 : 0;

    *write = (req->tr.read_writeAMO == WRITE) ? 1 : 0;
    // ATS Translation Request は read として来るが、no_write=0 なら write 権を要求している。
    *write = ((req->tr.at == ADDR_TYPE_PCIE_ATS_TRANSLATION_REQUEST)
              && (req->no_write == 0))
             ? 1
             : *write;

    *exec = (req->tr.read_writeAMO == READ && req->exec_req
             && (req->tr.at == ADDR_TYPE_UNTRANSLATED || req->pid_valid))
            ? 1 : 0;

    *priv = (req->pid_valid && req->priv_req) ? S_MODE : U_MODE;
}

static void reset_test_state(void) {
    memset(memory, 0, TEST_MEM_SZ);
    next_free_page = 0x100;
    for (int i = 0; i < 65536; i++) next_free_gpage[i] = 0x100;
    access_viol_addr = (uint64_t)-1;
    data_corruption_addr = (uint64_t)-1;
}

// =============================================================================
// IOMMU configuration for Phase 1 scope
//   capabilities: Sv39 only, MSI_FLAT, no AMO_HWAD (= page-fault on A=0)
//   fctl: LE, no GXL, no WSI
// =============================================================================
static int configure_iommu_phase1(iommu_t *iommu) {
    capabilities_t cap = {0};
    fctl_t         fctl = {0};

    cap.version  = 0x10;
    cap.Sv39     = 1;            // S-stage Sv39 only (per scope)
    cap.Sv39x4   = 1;            // G-stage Sv39x4 (needed for IOMMU spec)
    cap.msi_flat = 1;            // MSI_FLAT on (extended DC = 64 byte)
    cap.amo_hwad = 0;            // Q3: HW A/D OFF — fault on A=0 / D=0+W
    cap.pas      = 50;
    cap.end      = 0;            // LE only (Q-spec: cap.end=0 → fctl.BE WARL=0)
    cap.igs      = MSI;          // Just pick one — irrelevant for Phase 1

    uint64_t bare_pg_sz = 0x40000000ULL;  // 1 GiB Bare page size

    return reset_iommu(iommu,
        /*num_hpm=*/0, /*hpmctr_bits=*/0, /*eventID_limit=*/0,
        /*num_vec_bits=*/3, /*reset_iommu_mode=*/Off,
        /*max_iommu_mode=*/DDT_3LVL, /*max_devid_mask=*/0xFFFFFF,
        /*gxl_writeable=*/0, /*fctl_be_writeable=*/0,
        /*fill_ats_in_ioatc=*/0,
        cap, fctl,
        bare_pg_sz, bare_pg_sz, bare_pg_sz, 0x200000,
        bare_pg_sz, bare_pg_sz, bare_pg_sz, 0x200000);
}

// Enable FQ at given log2szm1 (4 → 32 entries)
static int enable_fault_queue(iommu_t *iommu, uint64_t fq_ppn, uint8_t log2szm1) {
    fqb_t   fqb   = {0};
    fqcsr_t fqcsr = {0};
    fqb.ppn      = fq_ppn;
    fqb.log2szm1 = log2szm1;
    write_register(iommu, FQB_OFFSET, 8, fqb.raw);
    fqcsr.fqen = 1;
    fqcsr.fie  = 0;             // no interrupts; we poll
    write_register(iommu, FQCSR_OFFSET, 4, fqcsr.raw);

    // wait for fqon
    for (int i = 0; i < 100; i++) {
        fqcsr.raw = read_register(iommu, FQCSR_OFFSET, 4);
        if (fqcsr.fqon) return 0;
    }
    return -1;
}

// Enable IOMMU mode = DDT_1LVL (extended) — does NOT call add_dev_context
static int enable_iommu_1lvl(iommu_t *iommu, uint64_t ddt_ppn) {
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
// FaultRecord layout per spec §4.2 Figure 32 (32 byte / record)
// =============================================================================
typedef struct __attribute__((packed)) {
    uint64_t dw0;  // CAUSE/PID/PV/PRIV/TTYP/DID
    uint64_t dw1;  // custom + reserved
    uint64_t dw2;  // iotval
    uint64_t dw3;  // iotval2
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
    if (fqh == fqt) {
        out.present = 0;
        return out;
    }
    fault_record_raw_t rec;
    uint64_t rec_addr = (fq_ppn * PAGESIZE) + (fqh * 32);
    read_memory_test(rec_addr, 32, (char *)&rec);

    out.present = 1;
    out.cause   = (rec.dw0 >>  0) & 0xFFF;
    out.ttyp    = (rec.dw0 >> 34) & 0x3F;
    out.did     = (rec.dw0 >> 40) & 0xFFFFFF;
    out.iotval  = rec.dw2;
    out.iotval2 = rec.dw3;

    write_register(iommu, FQH_OFFSET, 4, fqh + 1);   // ack
    return out;
}

// =============================================================================
// Test case enumeration
// =============================================================================
typedef enum { ACC_READ = 0, ACC_WRITE = 1 } access_t;

typedef struct {
    int      case_id;
    char     name[80];
    int      level;          // 0 = leaf (LVL3), 1 = mid (LVL2), 2 = root (LVL1)
    uint8_t  flags;          // V/R/W/X/U/G/A/D bits
    access_t access;
    int      rsvd_pattern;   // 10-bit pattern for bits[63:54], 0 = not used
} test_case_t;

// =============================================================================
// Run one case end-to-end
// =============================================================================
static void run_case(const test_case_t *tc, FILE *out) {
    iommu_t iommu = {0};
    if (configure_iommu_phase1(&iommu) < 0) {
        fprintf(stderr, "configure_iommu_phase1 failed at case %d\n", tc->case_id);
        exit(1);
    }
    reset_test_state();

    uint64_t ddt_ppn = get_free_ppn(1);
    uint64_t fq_ppn  = get_free_ppn(1);

    if (enable_fault_queue(&iommu, fq_ppn, /*log2szm1=*/4) < 0) {
        fprintf(stderr, "enable_fault_queue failed at case %d\n", tc->case_id);
        exit(1);
    }
    if (enable_iommu_1lvl(&iommu, ddt_ppn) < 0) {
        fprintf(stderr, "enable_iommu_1lvl failed at case %d\n", tc->case_id);
        exit(1);
    }

    // Build DC: Sv39 S1, G-stage Bare, PDTV=0, no PC
    device_context_t DC = {0};
    DC.tc.V        = 1;
    DC.tc.PDTV     = 0;
    DC.tc.EN_ATS   = 0;
    DC.fsc.iosatp.MODE = IOSATP_Sv39;
    DC.fsc.iosatp.PPN  = get_free_ppn(1);   // S1 root PT page
    DC.iohgatp.MODE = IOHGATP_Bare;
    DC.msiptp.MODE  = MSIPTP_Off;
    add_dev_context(&iommu, &DC, /*device_id=*/0);

    // Build PTE
    pte_t pte = {0};
    if (tc->rsvd_pattern) {
        // valid leaf PTE, then OR reserved bits (bits 63..54)
        pte.V = 1; pte.R = 1; pte.W = 1; pte.X = 1;
        pte.U = 1; pte.A = 1; pte.D = 1;
        pte.PPN  = get_free_ppn(1);
        pte.raw |= ((uint64_t)(tc->rsvd_pattern & 0x3FF)) << 54;
    } else {
        pte.V = (tc->flags >> 0) & 1;
        pte.R = (tc->flags >> 1) & 1;
        pte.W = (tc->flags >> 2) & 1;
        pte.X = (tc->flags >> 3) & 1;
        pte.U = (tc->flags >> 4) & 1;
        pte.G = (tc->flags >> 5) & 1;
        pte.A = (tc->flags >> 6) & 1;
        pte.D = (tc->flags >> 7) & 1;
        // Q1 case B: leaf-like at non-leaf level → misaligned PPN
        if (tc->level > 0 && (pte.R || pte.X)) {
            pte.PPN = get_free_ppn(1) | 0x1;     // bit[0]=1 → not 2 MiB aligned
        } else {
            pte.PPN = get_free_ppn(1);
        }
    }

    uint64_t iova = 0x002345;     // VPN[2]=0, VPN[1]=0, VPN[0]=2
    iosatp_t s1 = DC.fsc.iosatp;
    add_s_stage_pte(s1, iova, pte, /*add_level=*/tc->level, /*SXL=*/0);

    // Issue translation
    hb_to_iommu_req_t req = {0};
    req.device_id = 0;
    req.pid_valid = 0;
    req.tr.at = ADDR_TYPE_UNTRANSLATED;
    req.tr.iova   = iova;
    req.tr.length = 8;
    req.tr.read_writeAMO = (tc->access == ACC_READ) ? READ : WRITE;
    req.no_write = (tc->access == ACC_READ) ? 1 : 0;

    iommu_to_hb_rsp_t rsp = {0};
    iommu_translate_iova(&iommu, &req, &rsp);

    // Pop FQ record (if any)
    fq_extracted_t fq = pop_fault_record(&iommu, fq_ppn);

    // Emit JSONL
    //   pte_raw : leaf PTE の生 64bit 値。replay.py がそのままメモリに書き戻すと
    //             output PPN がリファレンスと完全一致する。
    fprintf(out,
        "{\"case_id\":%d,\"name\":\"%s\",\"level\":%d,\"flags\":%u,"
        "\"access\":\"%s\",\"rsvd_pattern\":%d,"
        "\"pte_raw\":\"0x%016" PRIx64 "\","
        "\"status\":%d,\"PPN\":\"0x%" PRIx64 "\",\"S\":%u,",
        tc->case_id, tc->name, tc->level, tc->flags,
        (tc->access == ACC_READ) ? "read" : "write",
        tc->rsvd_pattern,
        (uint64_t)pte.raw,
        (int)rsp.status, rsp.trsp.PPN, rsp.trsp.S);

    if (fq.present) {
        fprintf(out,
            "\"fault\":{\"cause\":%u,\"iotval\":\"0x%" PRIx64 "\","
            "\"iotval2\":\"0x%" PRIx64 "\",\"ttyp\":%u,\"did\":%u}",
            fq.cause, fq.iotval, fq.iotval2, fq.ttyp, fq.did);
    } else {
        fprintf(out, "\"fault\":null");
    }
    fprintf(out, "}\n");
}

// =============================================================================
// Main: enumerate all cases for Phase 1
// =============================================================================
int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

    memory = (int8_t *)calloc(1, TEST_MEM_SZ);
    if (!memory) { fprintf(stderr, "calloc failed\n"); return 1; }

    FILE *out = stdout;
    int case_id = 0;

    // (A) Leaf level: 256 flags × 2 access types = 512 cases
    for (int flags = 0; flags < 256; flags++) {
        for (int acc = 0; acc < 2; acc++) {
            test_case_t tc = {0};
            tc.case_id = case_id++;
            snprintf(tc.name, sizeof tc.name,
                     "leaf_lvl0_f%02x_%s", flags, acc == 0 ? "r" : "w");
            tc.level = 0;
            tc.flags = (uint8_t)flags;
            tc.access = acc == 0 ? ACC_READ : ACC_WRITE;
            tc.rsvd_pattern = 0;
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
            tc.level = level;
            tc.flags = (uint8_t)flags;
            tc.access = ACC_READ;
            tc.rsvd_pattern = 0;
            run_case(&tc, out);
        }
    }

    // (C) Reserved-bit patterns (bits 63..54 of PTE = 10 bits): 100 cases
    //     - 10 single-bit
    //     - 90 random multi-bit
    for (int b = 0; b < 10; b++) {
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "rsvd_single_bit%d", b + 54);
        tc.level = 0; tc.flags = 0; tc.access = ACC_READ;
        tc.rsvd_pattern = 1 << b;
        run_case(&tc, out);
    }
    srand(42);
    for (int i = 0; i < 90; i++) {
        int p = rand() & 0x3FF;
        if (p == 0) p = 1;
        test_case_t tc = {0};
        tc.case_id = case_id++;
        snprintf(tc.name, sizeof tc.name, "rsvd_random_%03d", i);
        tc.level = 0; tc.flags = 0; tc.access = ACC_READ;
        tc.rsvd_pattern = p;
        run_case(&tc, out);
    }

    fprintf(stderr, "✓ generated %d cases\n", case_id);
    free(memory);
    return 0;
}