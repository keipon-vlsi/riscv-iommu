// gen_common.h — 全 gen_*.c で共有する宣言
//
// この header は「カテゴリ間で重複しない共通骨組み」をまとめます。
// 各 gen_<category>.c は main() に enumeration ループだけ書いて、
// 個別ケースの実行は run_case() に委譲します。

#ifndef GEN_COMMON_H
#define GEN_COMMON_H

#include <stdint.h>
#include <stdio.h>

#include "iommu.h"

// =============================================================================
// 翻訳モード — どの stage を有効にしてケースを回すか
// =============================================================================
typedef enum {
    STAGE_S1_ONLY        = 0,   // 既定。S1=Sv39, S2=Bare。phase1_pte_flags / iova_variation 用。
    STAGE_S2_ONLY        = 1,   // S1=Bare, S2=Sv39x4。s2_only 用。
    STAGE_NESTED         = 2,   // S1=Sv39 + S2=Sv39x4。nested 用 (S2=identity 固定)。
    STAGE_NESTED_FULL    = 3,   // S1=Sv39 + S2=Sv39x4。S1 leaf flags / S2 leaf flags 両方が可変。
    // PDTV=1 (Process Context): DC.tc.PDTV=1、PDT 経由で PC を引く
    STAGE_PC_S1_ONLY     = 4,   // PC.fsc=Sv39、iohgatp=Bare。
    STAGE_PC_S2_ONLY     = 5,   // PC.fsc=Bare、iohgatp=Sv39x4。
    STAGE_PC_NESTED      = 6,   // PC.fsc=Sv39 + iohgatp=Sv39x4 (S2=identity 固定)。
    STAGE_PC_NESTED_FULL = 7,   // PC.fsc=Sv39 + iohgatp=Sv39x4。S1/S2 両 flags 可変。
    STAGE_BARE_BARE      = 8,   // S1=Bare, S2=Bare の純粋 Bare DC。bare_mixed 用。
    STAGE_MSI            = 9,   // S1=Sv39, S2=Sv39x4, msiptp=Flat の MSI 経路。
} stage_mode_t;

// Process Context 固定値 (全 pc_* カテゴリで共通)
#define PC_PROCESS_ID_FIXED   0x00000042u
#define PC_PSCID_FIXED        0x0100u

// =============================================================================
// テストケース定義 — 全カテゴリで共通の「1 ケース分の入力」
//   各 gen_*.c は使う軸だけ埋めて、未使用フィールドはゼロのまま渡す。
// =============================================================================
typedef enum { ACC_READ = 0, ACC_WRITE = 1, ACC_EXEC = 2 } access_t;

typedef struct {
    int          case_id;              // カテゴリ内で 0 から振る通し番号
    char         name[80];             // 人間可読な短縮名
    char         category[64];         // "phase1_pte_flags", "iova_variation", "s2_only", "nested"

    // ── 翻訳モード (省略時 STAGE_S1_ONLY) ──
    stage_mode_t stage_mode;

    // ── 共通の軸 ──
    access_t     access;
    uint64_t     iova;                 // S1_ONLY/NESTED: VA / S2_ONLY: GPA。
                                       //   0 のときは run_case が default 0x002345 にフォールバック。

    // ── S1 PTE の軸 (STAGE_S1_ONLY / STAGE_NESTED で使う) ──
    //   STAGE_S2_ONLY モードでは下記 4 つを「leaf になる S2 PTE」のパラメータとして
    //   兼用している。これにより phase1_pte_flags の構造をそのまま再利用できる。
    int          level;                // S1 leaf level (S2_ONLY 時は S2 leaf level)
    uint8_t      flags;                // S1 PTE flags  (S2_ONLY 時は S2 PTE flags)
    int          rsvd_pattern;         // S1 reserved bits (S2_ONLY 時は S2 reserved bits)

    // ── S2 PTE の軸 (STAGE_NESTED で使う追加フィールド) ──
    //   nested ケースで S1 と S2 が両方 leaf を持つ場合に使う。
    //   現状の gen_nested.c は S2=identity 固定なので未使用 (Phase B で使う)。
    int          s2_level;
    uint8_t      s2_flags;
    int          s2_rsvd_pattern;

    // MSI 用軸 (msi_translation カテゴリ専用)
    uint16_t     msi_index;        // MSI PT 内の interrupt-file index
    uint8_t      msi_pte_v;        // MSI PTE.V (bit 0)
    uint8_t      msi_pte_c;        // MSI PTE.C (bit 63)
    uint8_t      msi_pte_m;        // MSI PTE.M (bits 2:1)
    uint64_t     msi_pte_ppn;      // M=3 (Basic) 時の翻訳先 PPN
    uint16_t     msi_pte_rsvd;     // translate_rw.reserved (bits 9:3) raw

    // (将来: did, pasid, pdtv_enabled, msi_addr_pattern 等)
} test_case_t;

// =============================================================================
// メモリレイアウト記録 — replay.py が JSONL から読み取って env を上書きする
// =============================================================================
typedef struct {
    // 静的 alloc (= run_case_* 冒頭で確定)
    uint64_t ddt_ppn;
    uint64_t fq_ppn;
    uint64_t pdt_root_ppn;        // 0 = unused (PDTV=0 の時)
    uint64_t iohgatp_root_ppn;    // 0 = unused (S2 Bare の時)
    uint64_t s1_root_ppn;         // 0 = unused (S1 Bare の時)

    // 動的 alloc (= add_g_stage_pte / add_s_stage_pte / add_process_context 内部)
    uint64_t g_mid_ppn;           // S2 PT mid (= 1st add_g_stage_pte alloc)
    uint64_t g_leaf_ppn;          // S2 PT leaf
    uint64_t pdt_l1_ppn;          // PDT L1 (= add_process_context alloc)
    uint64_t pdt_leaf_ppn;        // PDT leaf
    uint64_t s1_mid_ppn;          // S1 PT mid (= add_s_stage_pte alloc)
    uint64_t s1_leaf_ppn;         // S1 PT leaf

    uint64_t msi_pt_root_ppn;     // msiptp.PPN (16-entry flat MSI PT base)
} mem_layout_t;

// =============================================================================
// グローバル状態 — libiommu callback が参照する物理メモリ模擬
// =============================================================================
#define TEST_MEM_SZ  (256ULL * 1024 * 1024)   // 256 MiB

extern int8_t  *g_memory;
extern uint64_t g_next_free_page;
extern uint64_t g_next_free_gpage[65536];
extern uint64_t g_access_viol_addr;
extern uint64_t g_data_corruption_addr;
extern uint64_t g_next_free_page;   // run_case_* で snapshot するため public 化

// =============================================================================
// 公開 API
// =============================================================================

// libiommu callback 群を有効化する初期化 (memory 確保 + ポインタ初期化)。
// 各 gen_*.c の main() の冒頭で 1 度呼ぶ。
void gen_common_init(void);

// 共通 IOMMU 設定 (Sv39, Sv39x4, MSI_FLAT, amo_hwad=0 など)
int  configure_iommu_phase1(iommu_t *iommu);

// PC 用 IOMMU 設定 (phase1 + cap.pd20=1)
int  configure_iommu_pc(iommu_t *iommu);

// FQ を有効化 (log2szm1=4 → 32 entries)
int  enable_fault_queue(iommu_t *iommu, uint64_t fq_ppn, uint8_t log2szm1);

// DDT を 1LVL モードに切り替え
int  enable_iommu_1lvl(iommu_t *iommu, uint64_t ddt_ppn);

// 1 ケース実行: stage_mode に応じて以下のいずれかにディスパッチ
//   STAGE_S1_ONLY → run_case_s1_only  (S1 Sv39 + S2 Bare)
//   STAGE_S2_ONLY → run_case_s2_only  (S1 Bare + S2 Sv39x4)
//   STAGE_NESTED  → run_case_nested   (両 stage Sv39 + Sv39x4)
//
// 各 run_case_* は configure → DC 配置 → PTE 配置 → translate → emit JSONL
// を行う。tc->iova == 0 のときは 0x002345 にフォールバック。
void run_case(const test_case_t *tc, FILE *out);

// テストケース毎に呼ぶリセット (memory 全クリア + allocator pointer 初期化)
void reset_test_state(void);

#endif // GEN_COMMON_H