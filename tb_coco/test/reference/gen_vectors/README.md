# Reference Test Vectors — カテゴリと役割

このディレクトリは **ved-rivos の riscv-iommu リファレンスモデル (libiommu)** を
駆動して、RTL 検証用のゴールデンベクタ JSONL を生成する C ハーネス群です。

各 `.c` ファイルは **1 つの「検証軸」に集中** して入力空間を網羅します。
カテゴリ間で重複しないよう、それぞれが「**何を可変軸として動かすか / 何を固定するか**」
を header コメントで明記しています。

---

## カテゴリ一覧

| ファイル | 可変軸 | 固定軸 | ケース数 |
| :--- | :--- | :--- | ---: |
| `gen_phase1_pte_flags.c` | S1 leaf PTE flags 全 256 × level (0/1/2) × access × reserved-bit (bit 54..62) | IOVA=`0x002345`, DID=0, S2=Bare, PDTV=0, MSI off | 1123 |
| `gen_iova_variation.c` | IOVA の VPN[2/1/0] を 8 境界値で網羅 (8³ × 2 access) | S1 leaf PTE=valid (`0xDF`), level=0, S2=Bare, PDTV=0 | 1024 |
| `gen_s2_only.c` | S2 leaf PTE flags 全 256 × level × access × reserved-bit (bit 54..62) | S1=Bare, IOVA(=GPA)=`0x002345`, DID=0, PDTV=0 | 1123 |
| `gen_nested.c` | S1 leaf PTE flags 全 256 × level × access × reserved-bit (bit 54..62), nested context | S2=identity 4K range, IOVA=`0x002345`, DID=0, PDTV=0 | 1123 |
| `gen_nested_full.c` | **S1 leaf flags 全 256 × S2 leaf flags 全 256 × access (r/w)** の Cartesian product | level=0 (4K) 固定, S1 leaf PPN=`0x150` 固定, S2 test PPN=`0x250` 固定 | 131,072 |
| `gen_nested_full_quick.c` | nested_full の **代表 16 S1 × 16 S2 × 2 access サンプル版** (= 日中 iter 用) | 同上 | 512 |
| (将来) `gen_pc_s1_only.c` | Process Context (PDTV=1) + S1 leaf 軸 | S2=Bare | ~1100 |
| (将来) `gen_pc_s2_only.c` | PDTV=1 + S2 leaf 軸 | S1=Bare (in PC) | ~1100 |
| (将来) `gen_pc_nested.c` | PDTV=1 + nested | S2 identity 固定 | ~1100 |

合計 (現時点): **135,977 ケース** (= quick tier 4,905 + full only 131,072)

> 注: PTE bit 63 (= Svnapot 拡張の N ビット) は **Phase 1 RTL が Svnapot 非対応**
> のため reserved 軸から除外しています。Svnapot 対応時に各 gen_*.c の `(C) Reserved-bit
> patterns` セクションのループ上限を 9 → 10、mask を `0x1FF` → `0x3FF` に戻してください。

---

## Tier 構造とシナリオの分類ルール

実行時間を抑えるため、シナリオは **3 階層** で運用します。

| Tier | コマンド | 対象 | 想定 wall time | 何のため |
| :--- | :--- | :--- | :--- | :--- |
| smoke | `make smoke` | 12 ケース手書き | ~30 秒 | 保存ごと / 数分毎 |
| **quick (default)** | `make replay` | **quick tier 全カテゴリ** (~5,000 ケース) | ~10-15 分 | commit 前 / PR |
| full | `make replay-full` | **全カテゴリ** (nested_full 含む = ~135,000 ケース) | ~60 分 | nightly CI / リリース前 |

### tier への振り分け規則

各 gen_*.c のケース数で機械的に判定:

```
ケース数 ≤ 12,000  → quick tier (= ALL_CATEGORIES に追加するだけで OK)
ケース数 >  12,000 → full tier 専用 (= FULL_ONLY_CATEGORIES に分類)
                     かつ、必ず "<カテゴリ>_quick" 兄弟を作る
```

### `_quick` 版の作り方 (新カテゴリで巨大になりそうな時の手順)

1. `gen_<NEW>.c` を作り full tier (`FULL_ONLY_CATEGORIES`) に分類
2. `gen_<NEW>_quick.c` を作り quick tier (= `ALL_CATEGORIES` の通常メンバ) に分類
3. `_quick` 側は **境界となる代表パターンだけ** を選ぶ:
   - 各軸の極端値 (V=0, all-1, etc.)
   - 主要な permission パターン (R-only, RW, RX, RWX)
   - 注目バグ系のフラグ (A=0, D=0+W, etc.)
   - 適度な user / kernel / global 切替
4. ケース数の目安: **代表 N 個 × N 個 × access 2 ≈ 数百〜2000** ぐらい

### Tier 構成は Makefile で確認

```bash
make show-vars
# → ALL_CATEGORIES / FULL_ONLY_CATEGORIES / QUICK_CATEGORIES が表示される
```

---

## なぜカテゴリを分けるか

1. **検証軸が独立しているケースを混ぜると、failure 時の原因切り分けが難しい**
   PTE フラグのバグなのか IOVA デコードのバグなのか、JSONL の名前空間が分かれていれば一目で分かる。
2. **カテゴリ単位で run / diff できる**
   "IOVA 系だけ流したい" がワンコマンドでできる。CI の bisect や regression にも有利。
3. **リファクタや拡張時の影響範囲を狭く保てる**
   新カテゴリを足すときは新しい `.c` を 1 本書くだけ。既存ファイルには触らない。
4. **レビュー時に「このカテゴリでは何を保証したか」が明確になる**
   既存テストの読解コストが下がる。

---

## カテゴリの選び方 — 「軸」の独立性ルール

新カテゴリを足すときは以下を満たすか確認:

- [ ] **既存カテゴリと可変軸が直交しているか** (= 同じ軸を別のカテゴリでも動かしていないか)
- [ ] **固定軸が明確か** (= 何を意図的に動かさないか header に書いてあるか)
- [ ] **ケース数が妥当か** (数十〜数千。10 万を越えるなら更にサブ分割を検討)
- [ ] **`category` フィールドの値がファイル名と一致しているか** (`gen_xxx.c` → `category="xxx"`)

---

## 出力 JSONL のスキーマ

各 `.c` は `golden_<category>.jsonl` を吐きます。1 行 1 ケースで、フィールドは:

```json
{
  "case_id":     1234,                    // カテゴリ内で 0 から振る通し番号
  "name":        "leaf_lvl0_f00_r",       // 人間可読な短縮名
  "category":    "phase1_pte_flags",      // ★ ファイル名 (gen_ と .c を除いた部分)
  "iova":        "0x002345",              // 翻訳元 IOVA
  "level":       0,                       // PTE 配置 level (0=4K, 1=2M sp, 2=1G sp)
  "flags":       207,                     // 想定 PTE flags (デバッグ用、reserved bit は別)
  "access":      "read",                  // "read" or "write"
  "rsvd_pattern": 0,                      // PTE bits[63:54] のパターン
  "pte_raw":     "0x000000000004cdf",     // libiommu allocator が決めた leaf PTE 全 64bit
  "status":      0,                       // 0=Success, 1=Unsupported (= fault)
  "PPN":         "0x103",                 // 翻訳結果 (fault 時は 0x0)
  "S":           0,                       // superpage flag
  "fault":       null                     // fault があれば dict (cause/iotval/iotval2/ttyp/did)
}
```

- **`category` + `case_id` の組がユニークキー** (= ファイルを跨いで diff できる)
- 新フィールドを追加するときは **default 値で省略可能にして** 既存テストを壊さない設計に

---

## 追加カテゴリの作り方

> **方針**: `gen_common.{h,c}` に共通処理が集まっているので、新カテゴリは
> **`main()` の enumeration ループだけ書けばよい**。

1. `gen_<NEW>.c` を作る (既存の `gen_iova_variation.c` をひな型にコピーが楽)
2. header コメントで「可変軸 / 固定軸 / 期待件数」を明記
3. `main()` で `test_case_t` を埋めて `run_case(&tc, out)` を呼ぶ
4. `Makefile` の `CATEGORIES` 変数に `<NEW>` を追加
5. `make run` → `golden_<NEW>.jsonl` が出る
6. `cd ..; make replay` で RTL に流して diff

---

## 実行

```bash
# 全カテゴリ生成
make run
# → golden_phase1_pte_flags.jsonl  (1124 cases)
# → golden_iova_variation.jsonl    (1024 cases)

# 1 カテゴリだけ
make run-phase1_pte_flags
make run-iova_variation

# 全部消す
make clean
```

検証フロー全体は親 `tb_coco/test/Makefile` の `replay` ターゲットを参照。