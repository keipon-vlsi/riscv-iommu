# 検証環境の整理 (= プレゼン slide 8 用素材)

## 1 行サマリ

**libiommu (C reference model) と自作 RTL を、 同じテストパターンで independently 走らせて、 cause / iotval / iotval2 / PPN / status の 5 フィールドが完全一致するかを per-case で diff する replay-driven 検証。**

---

## 全体フロー (= block diagram にできる図)

```
┌──────────────────────────────────────────────────────────────────┐
│  (1) Test pattern generation (= C harness)                        │
│                                                                   │
│   gen_<category>.c ── drives ──▶  libiommu (C ref model)          │
│        │                              │                           │
│        │  records input               │  records output           │
│        ▼                              ▼                           │
│   { stage_mode, iova,             { status, PPN, S, fault:        │
│     level, flags, pte_raw,          { cause, iotval, iotval2,     │
│     rsvd_pattern, access,             ttyp, did } }               │
│     alloc: { ddt, fq, pdt_*,      append per-line                 │
│             g_*, s1_* } }                                         │
│                  │                                                │
│                  ▼                                                │
│        golden_<category>.jsonl  (= per-category, 1 line per case) │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼ (= 18 ファイル、 計 10,382 / 140k cases)
                          │
┌──────────────────────────────────────────────────────────────────┐
│  (2) Replay (= cocotb testbench against RTL DUT)                  │
│                                                                   │
│   test_replay_golden.py:                                          │
│     for entry in all_entries:                                     │
│       reset_for_replay(env)        ← DUT を reset + FQ 再初期化   │
│       setup_dc_for_entry(env, e)   ← entry.alloc を env に注入    │
│                                       install_dc_* で DDT/DC を   │
│                                       配置                         │
│       setup_for_entry(env, e)      ← entry.pte_raw をメモリの     │
│                                       指定 level に書く            │
│       rtl_resp = drive_one(env, e) ← dev_tr_read/write を発行     │
│                                       FQ tail を poll で監視       │
│                                       1 応答 = 1 record           │
│       log.append(rtl_resp)                                        │
│                                                                   │
│   rtl_log.jsonl ← golden と同じ schema で 1 行ずつ書く            │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  (3) Diff (= scripts/diff_logs.py)                                │
│                                                                   │
│   per-category 突き合わせ:                                         │
│     key = (category, case_id)                                     │
│     比較: status, PPN, S, fault.{cause, iotval, iotval2, ttyp,    │
│             did}                                                  │
│                                                                   │
│   出力:                                                            │
│     - category 別 matches / mismatches 表                         │
│     - 不一致 case の field 別 diff                                │
│     - "shifted match" (= 順序ずれは許容、 内容一致なら OK)         │
└──────────────────────────────────────────────────────────────────┘
```

---

## それぞれが見ているデータの違い

### libiommu (= reference) が出力するもの
- **status**: 0 (= success) / 1 (= fault)
- **PPN**: 翻訳結果の最終 SPA (= success 時のみ意味あり)
- **S**: superpage flag (= 4K / 2M / 1G の区別)
- **fault** (= status=1 のときだけ):
  - **cause**: spec table 4.1 の cause コード (= LOAD_PAGE_FAULT=13, STORE_PAGE_FAULT=15, LOAD_GUEST_PAGE_FAULT=21, STORE_GUEST_PAGE_FAULT=23, DDT_ENTRY_MISCONFIGURED=259, 等)
  - **iotval**: 翻訳要求の iova
  - **iotval2**: guest page fault のとき → GPA、 そうでないとき → 0
  - **ttyp**: transaction type (= read/write/exec/atomic 等の分類)
  - **did**: device id (= 今回は 0 固定)

### RTL (= 自作 IOMMU) が出力するもの (= 上記と同じ schema)
- IOMMU の外部 interface (= dev_tr) から見たもの
  - 成功時: dev_tr の AXI 応答 + spaddr (translation_wrapper の `trans_valid_o`, `spaddr_o`)
  - 失敗時: FQ に enqueue された fault record (= rv_iommu_fq_handler が書く)
- testbench (= helpers/replay.py の `drive_one`) が FQ をポーリングして、 FQ 経由で取れる record を `_format_fault`、 dev_tr の AXI rdata を `_format_success` で整形

### 何を見ているか (= 検証の本質)
- ref と rtl が **同じ条件 (= 同じ DC, PC, PT, IOVA, access type)** で、
- **完全に同じ翻訳結果 (= 成功なら同じ SPA、 失敗なら同じ fault 内容)** を返すか
- spec 解釈の違い、 ロジックバグ、 タイミング起因の問題、 全てを 1 つのフィールド diff で炙り出す

---

## RTL 側のどの信号が JSONL にマップされるか

| JSONL field | 由来 | RTL 内部 signal |
|------------|------|---------------|
| status=0 / PPN | dev_tr の AXI read response の data | `tw.trans_valid_o`, `tw.spaddr_o` → ds_if → AXI master |
| S | (= 現状未使用、 superpage 情報) | `tw.is_superpage_o` (= 未取得) |
| status=1 / fault.cause | FQ に enqueue された entry の cause | `tw.cause_code_o` → fq_handler が memory に書く |
| fault.iotval | 同じく FQ entry | iova (= `tw.iova_i` 由来) |
| fault.iotval2 | 同じく FQ entry | `tw.bad_gpaddr_o` (= guest page fault 時のみ) |
| fault.ttyp | 同じく FQ entry | transaction type (= dev_tr の AXI signals 由来) |
| fault.did | 同じく FQ entry | device id (= dev_tr の AXI ID 由来) |

cocotb 側は **FQ の memory 領域を直接読んで record をパース** (= helpers/fq.py の `drain()` メソッド) + **dev_tr の AXI master が data を受信** で結果を集めている。 IOMMU 内部の signal を直接 probe しているわけではなく、 **外部 interface だけで観測** している (= black-box 検証)。

---

## テストパターンの生成 (= 18 カテゴリの設計意図)

### 階層

```
libiommu (= 公式 spec の C reference)
   │
   │ link
   ▼
gen_vectors/  (= 自前の C harness)
   │
   ├─ gen_phase1_pte_flags.c   ← S1 leaf PTE のフラグ bit を網羅
   ├─ gen_iova_variation.c     ← IOVA の各 VPN segment を全パターン振る
   ├─ gen_s2_only.c            ← S2 単独翻訳の検査
   ├─ gen_nested.c             ← 2 段翻訳
   ├─ gen_nested_full.c        ← 2 段で S1 / S2 両方を網羅 (= フル組み合わせ)
   ├─ gen_pc_*.c               ← Process Context 付きの各種
   ├─ gen_pte_reserved_*.c     ← reserved bit fault
   ├─ gen_access_matrix_*.c    ← read/write/exec × R/W/X 許可の組合せ
   ├─ gen_bare_mixed.c         ← bare mode 混在
   ├─ gen_msi_translation.c    ← MSI 翻訳
   └─ gen_common.c             ← 共通の case 駆動関数 + 結果記録
```

### 各カテゴリの設計意図と振り方

| カテゴリ | 振っているもの | 目的 |
|---------|--------------|------|
| `phase1_pte_flags` | S1 leaf PTE の V/R/W/X/U/G/A/D 8 bit を 256 通り (= read/write = 2) × leaf level (= 3) → ~1123 | PTE フラグの正常 / 異常を網羅 |
| `iova_variation` | iova の VPN[2:0] segment を 1024 通り | アドレス空間カバレッジ |
| `s2_only` | S2 leaf PTE の全フラグ + level の組合せ | S2 単独翻訳の検査 |
| `nested` | S1 + S2 nested で、 S1 PTE を変動 | 2 段翻訳の S1 観点 |
| `nested_full_quick` | S1 と S2 PTE を直交振り (= quick = 512 ケース) | 2 段の組合せ網羅 (= 軽量版) |
| `nested_full` | 同上、 全 ~70k | nightly run 用、 完全網羅 |
| `pc_*` | 上記各カテゴリ + Process Context 経由 | PDTW path の追加検査 |
| `pte_reserved_s1` | S1 PTE の reserved bit を 1 bit ずつ立てる | spec 違反 fault の検査 |
| `pte_reserved_s2` | S2 PTE 同様 | 同上 |
| `access_matrix_s1` | (is_store, is_rx) × (R, W, X 許可) の組合せ | permission check の検査 |
| `access_matrix_s2` | S2 版 | 同上 |
| `bare_mixed` | bare mode + S1 / S2 混在 | bare path の検査 |
| `msi_translation` | MSI iova + MSI PT entry の各種 | MSI 翻訳の検査 |

### 1 ケースが持つ情報 (= JSONL 1 行に詰まっているもの)

```json
{
  "case_id": 826,                            // ← カテゴリ内連番
  "name": "pc_nonleaf_lvl2_f3a",             // ← 人間可読 ID (= ロジックは encode)
  "category": "pc_phase1_pte_flags",         // ← どのカテゴリか
  "stage_mode": "pc_s1_only",                // ← 翻訳モード (= 9 種類)
  "iova": "0x2345",                          // ← 入力 IOVA
  "level": 2,                                // ← test PTE をどの level に置くか
  "flags": 58,                               // ← PTE の フラグ部分 (= 0x3a)
  "access": "read",                          // ← read / write / atomic
  "rsvd_pattern": 0,                         // ← reserved bit pattern (= 0 なら振らない)
  "pte_raw": "0x0000000000041c3a",           // ← PTE の 64 bit 値
  "alloc": {                                 // ← メモリ配置 (= libiommu が選んだ PPN)
    "ddt": "0x100", "fq": "0x101",
    "pdt_root": "0x102", ...
  },
  // ↓ 期待される RTL 出力 (= libiommu の結果)
  "status": 1,
  "PPN": "0x0",
  "S": 0,
  "fault": {
    "cause": 13,        // = LOAD_PAGE_FAULT
    "iotval": "0x2345",
    "iotval2": "0x0",
    "ttyp": 2,
    "did": 0
  }
}
```

ポイント: **入力フィールド (= stage_mode 以降 pte_raw まで) と出力フィールド (= status 以降) を 1 つの構造体にまとめている**。 これにより:
- diff_logs.py は同じスキーマで取って `dict == dict` だけで比較できる
- alloc field を mirror することで、 RTL 側のメモリレイアウトを libiommu に完全一致させる (= Option B 機能)

---

## 検証の強さと弱さ

### 強い点
- **spec 1.0 reference implementation との 1:1 比較** → spec 解釈ズレを物理的に検出
- 外部 interface だけ見る (= black-box) → RTL 内部実装の自由度を阻害しない
- カテゴリ単位の独立性 → 「どの機能が壊れたか」 がすぐ分かる
- shifted-match (= 512 case 以内の順序ずれ許容) → 並列実行や OoO 化への余地
- alloc mirror (= Option B) → メモリレイアウト一致でデバッグが楽

### 弱い点 / 未対応
- **時間的タイミングは検査しない** (= ref も RTL も結果しか見ない、 latency 比較なし)
- **internal state の coverage は別途** (= verilator coverage で取得、 別 metrics)
- **MSI / IOATC invalidate コマンド系は薄い** (= 1 カテゴリのみ)
- **multi-master concurrency は無い** (= 1 dev_tr ずつシーケンシャル)

---

## slide 8 で抜粋すべき要素 (= 90 秒で説明する場合)

### 表紙の 1 文
> 「 spec 1.0 reference (libiommu) を golden source として、 RTL の外部応答を JSONL でログ化、 18 カテゴリ × 10,382 ケースを per-case で diff し、 cause / iotval / iotval2 / PPN / status の完全一致を要求する replay-driven 検証」

### slide に置きたい図
1. 3 段ブロック図 (= 生成 → 実行 → diff)
2. JSONL 1 件のサンプル (= 上の json snippet)
3. カテゴリ一覧 (= 表)
4. 比較フィールド (= cause / iotval 等のリスト)

### 質疑用 backup として
- なぜ shifted-match? → OoO 化への余地確保
- なぜ JSONL? → スキーマ柔軟 + diff が楽 + 人間が読める
- なぜ外部 interface だけ? → spec compliant のテスト戦略、 RTL 内部は自由
- どこまで信頼できる? → libiommu 自体は spec authors の reference、 IOMMU 仕様適合性は他の RISC-V IP でも使われている

---

## 補足: 該当する RTL コードのソース箇所

- **dev_tr 入口**: `riscv_iommu.sv` の `dev_tr_req_i / dev_tr_resp_o`
- **翻訳結果出力**: `rv_iommu_tw_sv39x4_pc.sv` の `trans_valid_o`, `spaddr_o`, `trans_error_o`, `cause_code_o`, `bad_gpaddr_o`
- **FQ への fault enqueue**: `rv_iommu_fq_handler.sv` (= ここで cause / iotval / iotval2 / ttyp / did をパックして memory に書く)
- **cocotb 側の FQ 読み取り**: `helpers/fq.py` の `read_tail()` と `drain()`
- **AXI master 駆動**: `helpers/env.py` の `dev_tr_read`, `dev_tr_write` (= cocotbext-axi 経由)

---

> 用途: プレゼン slide 8 (= 検証環境) の準備材料
> 関連: `iommu_presentation_outline.md` (= 全体構成)
