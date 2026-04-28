# モジュール: `rv_iommu_ddtc`

> Claude 向け 1-pager。RTL 解析結果 + テスト網羅状況 + 既知の制約の統合ビュー。

---

## Quick Reference

| 項目 | 値 |
|---|---|
| **役割 (1 行)** | Device Directory Table Cache (DDTC)。完全連想方式 PLRU キャッシュで Device Context (DC) を保持し、CDW ウォークのコストを削減する |
| **RTL ファイル** | `rtl/translation_logic/rv_iommu_ddtc.sv` (~257 行) |
| **親モジュール** | `rtl/translation_logic/wrapper/rv_iommu_tw_sv39x4_pc.sv:380` / `rv_iommu_tw_sv39x4.sv:320` |
| **TB ファイル** | なし (未作成) |
| **TB ラッパ** | なし (未作成) |
| **仕様書対応** | `doc/spec/riscv-iommu/06-chapter-3.-data-structures.md` §3.8 / `10-chapter-7.-software-guidelines.md` §7.4 |
| **最終更新** | `2026-04-27` by Claude |

---

## 1. 概要

`rv_iommu_ddtc` は RISC-V IOMMU 仕様 §3.8「Memory-mapped Data Structures Cache」に相当する Device Directory Table Cache である。
デバイス (`device_id`) ごとの Device Context (DC) を最大 `DDTC_ENTRIES` エントリ保持し、ヒット時はキャッシュから即座に DC を返す。ミス時は CDW が DDT をメモリからウォークして DC をフェッチし、その結果を本モジュールに `update_i` 経由で書き戻す。
置換アルゴリズムは PLRU (Pseudo Least Recently Used) で、`DDTC_ENTRIES` エントリのバイナリツリーを `plru_tree_q` レジスタで管理する。
IODIR.INVAL_DDT コマンドに応じて全エントリ、または特定 `device_id` のエントリを無効化するフラッシュ機能を持つ。

---

## 2. パラメータ

| パラメータ | 型 | デフォルト | 役割 | 制約 |
|---|---|---|---|---|
| `DDTC_ENTRIES` | `int unsigned` | `4` | キャッシュエントリ数 | 2 の倍数かつ > 1 (line 236 assertion) |
| `DC_WIDTH` | `int` | `-1` | DC struct のビット幅 | 親モジュールから `rv_iommu::dc_base_t` または `dc_ext_t` の幅を渡す |

---

## 3. I/O ポート

### 3.1 Inputs

| 信号 | bit 幅 | 役割 | 駆動元 | TB での操作 |
|---|---|---|---|---|
| `clk_i` | 1 | クロック | 上位 | Clock 生成 |
| `rst_ni` | 1 | アクティブ Low 非同期リセット | 上位 | リセットシーケンス |
| `flush_i` | 1 | フラッシュトリガ (IODIR.INVAL_DDT) | CQ Handler → Translation Wrapper | `dut.flush_i.value = 1` |
| `flush_dv_i` | 1 | DV=1 のとき特定 `device_id` のみフラッシュ | 同上 | — |
| `flush_did_i` | 24 | フラッシュ対象 `device_id` | 同上 | — |
| `update_i` | 1 | エントリ書き込みトリガ | CDW (DDTC update) | `dut.update_i.value = 1` |
| `up_did_i` | 24 | 書き込む DC の `device_id` | CDW | — |
| `up_content_i` | `DC_WIDTH` | 書き込む DC の内容 | CDW | — |
| `lookup_i` | 1 | ルックアップトリガ | Translation Wrapper (`ddtc_access`) | `dut.lookup_i.value = 1` |
| `lu_did_i` | 24 | 検索対象 `device_id` | Translation Wrapper (`did_i`) | — |

### 3.2 Outputs

| 信号 | bit 幅 | 役割 | 行き先 | TB での観測 |
|---|---|---|---|---|
| `lu_content_o` | `DC_WIDTH` | ヒットした DC の内容 | Translation Wrapper (`ddtc_lu_content`) | `dut.lu_content_o.value` |
| `lu_hit_o` | 1 | ヒットフラグ | Translation Wrapper (`ddtc_lu_hit`) | `dut.lu_hit_o.value` |

### 3.3 双方向 / バス

なし (シンプルな入力/出力のみ)。

---

## 4. 内部状態

FSM なし。状態は 3 本のレジスタ配列で管理される。

### 4.1 主要な内部レジスタ

| レジスタ | bit 幅 | 初期値 | 更新タイミング | 用途 |
|---|---|---|---|---|
| `tags_q[DDTC_ENTRIES-1:0]` | `{device_id[23:0], valid}` × N | `'0` | posedge clk or negedge rst_ni | エントリの有効フラグと device_id タグ |
| `content_q[DDTC_ENTRIES-1:0]` | `{dc[DC_WIDTH-1:0]}` × N | `'0` | 同上 | DC の本体 (DC_WIDTH bits) |
| `plru_tree_q` | `2*(DDTC_ENTRIES-1)-1` | `'0` | 同上 | PLRU 置換ツリー (e.g. ENTRIES=4 → 5 bits) |

### 4.2 PLRU ツリー構造

```
DDTC_ENTRIES=4 の例 (plru_tree_q: 5 bits [4:0]):
  lvl0:            tree[0]           (選択: 0=左(entry0,1), 1=右(entry2,3))
                  /       \
  lvl1:      tree[1]     tree[2]     (左右それぞれ)
             /   \       /   \
  entries: [0]  [1]   [2]   [3]
```

- ヒット時に `plru_tree_n` が更新されてヒットエントリが「最近使用」になる (`rv_iommu_ddtc.sv:167-177`)
- `replace_en[i]` はツリーをデコードして「最も最近使われていない」エントリを示す (`rv_iommu_ddtc.sv:193-211`)

---

## 5. データフロー / 分岐図

```mermaid
flowchart TD
    A([lookup_i / update_i / flush_i]) --> B{動作モード}

    B -->|lookup_i=1| LOOK[Lookup 開始\nfor each entry]
    B -->|flush_i=1| FLUSH{flush_dv_i?}
    B -->|update_i=1\n& !flush_i| UPD{replace_en[i]=1\n& up_content[0]=1?}

    LOOK --> HIT_CHK{tags_q[i].valid &&\ndevice_id == lu_did_i?}
    HIT_CHK -->|Yes (any i)| HIT[lu_hit_o=1\nlu_content_o=content_q[i]\nPLRU 更新]
    HIT_CHK -->|No (all i)| MISS[lu_hit_o=0\nlu_content_o=0]

    FLUSH -->|dv_i=0| FLUSH_ALL[全エントリ valid=0]
    FLUSH -->|dv_i=1| FLUSH_DID{device_id==flush_did_i?}
    FLUSH_DID -->|Yes| FLUSH_ONE[対象エントリ valid=0]
    FLUSH_DID -->|No| FLUSH_SKIP[変更なし]

    UPD -->|Yes| UPDATE[tags_n[i] = {up_did, valid=1}\ncontent_n[i].dc = up_content]
    UPD -->|No (wrong entry\nor DC.V=0)| UPD_SKIP[変更なし]

    style HIT       fill:#c8f7c5
    style MISS      fill:#fff3cd
    style FLUSH_ALL fill:#f7c5c5
    style FLUSH_ONE fill:#f7c5c5
    style UPDATE    fill:#c8f7c5
```

---

## 6. 条件分岐一覧

### 6.1 分岐マトリクス

| BR-ID | 所在 (file:line) | 条件式 | 真分岐の出力・副作用 | 偽分岐の出力・副作用 | 関連 T-ID |
|---|---|---|---|---|---|
| `BR01` | `rv_iommu_ddtc.sv:71` | `lookup_i` | for ループで各エントリを検索 | `lu_hit_o=0`, `lu_content_o=0` (デフォルト) | TBD |
| `BR02` | `rv_iommu_ddtc.sv:76` | `tags_q[i].valid && tags_q[i].device_id == lu_did_i` (for ループ内) | `lu_content_o=content_q[i].dc`, `lu_hit_o=1`, `lu_hit[i]=1` | 変更なし、次エントリへ | TBD |
| `BR03` | `rv_iommu_ddtc.sv:105` | `flush_i` (update_flush ブロック内、for ループ内) | DV 判定 (BR04/BR05) | BR06 の update チェックへ | TBD |
| `BR04` | `rv_iommu_ddtc.sv:108` | `!flush_dv_i` (flush_i=1 内) | `tags_n[i].valid=0` (全エントリを無効化) | BR05 へ (DID マッチ確認) | TBD |
| `BR05` | `rv_iommu_ddtc.sv:113` | `tags_q[i].device_id == flush_did_i` (flush_i=1, dv_i=1 内) | `tags_n[i].valid=0` (マッチエントリのみ無効化) | 変更なし | TBD |
| `BR06` | `rv_iommu_ddtc.sv:120` | `update_i && replace_en[i] && up_content_i[0]` (flush_i=0 内) | `tags_n[i]={up_did, valid=1}`, `content_n[i].dc=up_content_i` (PLRU 対象エントリを上書き) | 変更なし | TBD |
| `BR07` | `rv_iommu_ddtc.sv:167` | `lu_hit[i] && lookup_i` (PLRU ツリー更新、for ループ内) | ヒットエントリのパスに沿って `plru_tree_n` を更新 | 変更なし | TBD |
| `BR08` | `rv_iommu_ddtc.sv:204` | `new_index[0]` (PLRU ツリーデコード、各レベルのビット方向判定) | `en &= plru_tree_q[...]` (ビット=1 のノードが一致) | `en &= ~plru_tree_q[...]` (ビット=0 のノードが一致) | TBD |

### 6.2 複雑な分岐の詳細

#### `BR06`: DC 挿入条件 — `up_content_i[0]`

```systemverilog
// rv_iommu_ddtc.sv:120
else if (update_i && replace_en[i] && up_content_i[0]) begin
    tags_n[i] = '{device_id: up_did_i, valid: 1'b1};
    content_n[i].dc = up_content_i;
end
```

- `up_content_i[0]` は DC の bit[0] = DC の V (Valid) フィールドを確認している
- DC.V=0 の DC はキャッシュに挿入されない (無効な DC を保持しないための防護)
- **仕様対応**: IOMMU Spec §3.1.3 DC.tc.V bit — "If tc.V = 0, all inbound transactions for the device are disallowed"
- **テスト**: DC.V=0 の `update_i` を送っても `lu_hit_o` が立たないことの確認が必要

#### `BR04` / `BR05`: フラッシュ粒度

```systemverilog
// rv_iommu_ddtc.sv:108-115
if (!flush_dv_i) begin
    tags_n[i].valid = 1'b0;             // DV=0: 全無効化
end
else if (tags_q[i].device_id == flush_did_i) begin
    tags_n[i].valid = 1'b0;             // DV=1: DID マッチのみ無効化
end
```

- `content_q` は更新されない — `valid` bit を 0 にするだけ。次の `update_i` で上書きされる
- **仕様対応**: IOMMU Spec §3.8 IODIR.INVAL_DDT: "If DV is 0, invalidates all DDT and PDT entries cached for all devices. If DV is 1, invalidates cached leaf level DDT entry for the device identified by DID"

---

## 7. モジュール間連携

### 7.1 上流 (呼び出し元)

| 相手モジュール | 駆動される信号 | 戻す信号 | 発生条件 | BR-ID |
|---|---|---|---|---|
| `rv_iommu_tw_sv39x4_pc` (line 380) | `lookup_i`, `lu_did_i` | `lu_hit_o`, `lu_content_o` | `req_trans_i` & 事前エラーなし | BR01, BR02 |
| `rv_iommu_tw_sv39x4_pc` (line 380) | `update_i`, `up_did_i`, `up_content_i` | — | CDW が DC ウォーク完了時 | BR06 |
| `rv_iommu_tw_sv39x4_pc` (line 380) | `flush_i`, `flush_dv_i`, `flush_did_i` | — | IODIR.INVAL_DDT コマンド実行時 | BR03-BR05 |

### 7.2 下流 (呼び出し先)

なし (本モジュールは他モジュールをインスタンス化しない)。

### 7.3 横の連携

| 相手モジュール | 関係 | 備考 |
|---|---|---|
| `rv_iommu_cdw_pc` | DDTC ミス → CDW がフェッチ → DDTC update | CDW の update 完了後に `update_i=1` で本モジュールへ書き戻す |
| `rv_iommu_pdtc` | DDTC に同じ `flush_dv_i`/`flush_did_i` が渡る | IODIR.INVAL_DDT は DDT と PDT の両エントリを無効化する |

---

## 8. タイミング / プロトコル注意点

### 8.1 ハンドシェイク

- `lookup_i=1` と `lu_hit_o` / `lu_content_o` は同一サイクルに組合せで解決する (`always_comb : lookup`, line 63)
- `update_i=1` の翌サイクル (`posedge clk_i`) にエントリが `tags_q`/`content_q` へ書き込まれる。書き込みサイクルとルックアップが同一サイクルの場合、**ルックアップは古い値を参照する** (組合せ優先ではなくレジスタ読み出し)
- `flush_i=1` は `update_i` より優先される: `update_flush` の `if (flush_i)` が先 (line 105)。同一サイクルに `flush_i=1` と `update_i=1` が来ると flush が優先
- PLRU ツリー更新もルックアップヒット時に組合せで `plru_tree_n` が計算され、次の `posedge clk_i` に `plru_tree_q` に保存される

### 8.2 リセット時の挙動

- `rst_ni=0` 時: `tags_q`, `content_q`, `plru_tree_q` が全て `'0` にリセット (`rv_iommu_ddtc.sv:216-219`)
- 全エントリが `valid=0` となり、ルックアップは常にミスを返す

### 8.3 マルチクロック / 非同期要素

単一クロック同期。リセットは非同期アクティブ Low (`negedge rst_ni`)。

### 8.4 同時動作の制約

- 同一サイクルに `flush_i=1` と `update_i=1` が来ると flush が優先 (line 105-120)
- assertion (line 249): `lu_hit` は最大 1 ビットのみ立つ。複数ヒットはハードウェアエラー
- assertion (line 251): `replace_en` も最大 1 ビットのみ立つ

---

## 9. テストマトリクス

### 9.1 正常動作

| T-ID | 項目 | 入力 / トリガ | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T01 | — | — | — | TBD | — | - | ⏱ PENDING |

### 9.2 エッジケース

| T-ID | 項目 | 入力 / トリガ | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T10 | — | — | — | TBD | — | - | ⏱ PENDING |

### 9.3 フォルト系

| T-ID | 項目 | 入力 / トリガ | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T20 | — | — | — | TBD | — | - | ⏱ PENDING |

### 9.4 カバレッジサマリ

| カテゴリ | 計 | PASS | FAIL | SKIP | PENDING |
|---|---|---|---|---|---|
| 正常動作 | 0 | 0 | 0 | 0 | 0 |
| エッジケース | 0 | 0 | 0 | 0 | 0 |
| フォルト系 | 0 | 0 | 0 | 0 | 0 |
| **合計** | **0** | **0** | **0** | **0** | **0** |

---

## 10. テスト実装ノート

### 10.1 TB 構築上の注意

- `DC_WIDTH` は親モジュールから決まる。単体テストでは `rv_iommu::dc_base_t` のビット幅 (**推測:** 64 ビット) か `dc_ext_t` の幅を適切に設定する
- `up_content_i[0]` (DC.V) が 0 の場合は挿入されないため、テストデータは必ず bit[0]=1 で構築すること (line 120)
- 全エントリ埋まった状態での PLRU 置換テストは `DDTC_ENTRIES+1` 回の update で確認できる
- ルックアップとアップデートは組合せ/順序の違いに注意。アップデート後のルックアップは翌サイクル以降

### 10.2 Force 方式の適用

本モジュールは単純なキャッシュであり Force 方式の適用は不要。標準の cocotb ドライブで十分。

### 10.3 観測しづらい信号

| 信号 | 観測方法 |
|---|---|
| `lu_hit[i]` (内部ベクタ) | `dut.lu_hit.value` (階層参照) |
| `replace_en[i]` | `dut.replace_en.value` |
| `plru_tree_q` | `dut.plru_tree_q.value` |
| `tags_q[i].valid` | `dut.tags_q.value` |

---

## 11. ログパース用ヒント

TBD (TB 未作成)

---

## 12. 既知の挙動 / TODO / 要検証項目

### 12.1 実装の既知の制約

- **update + lookup 同一サイクル**: `update_i=1` で書いたエントリは同サイクルのルックアップには反映されない。組合せ (lookup) がレジスタ前の `tags_n` ではなく `tags_q` を参照するため (`rv_iommu_ddtc.sv:63-84`)
- **flush + update 同一サイクル**: flush が優先される (line 105 が update より先)。CDW が flush と同サイクルに update を発行するシナリオは実運用上ないと思われるが、**推測:** 設計意図的に flush が優先になっている
- **DDTC_ENTRIES 制約**: 2 の倍数かつ > 1 でなければ assertion 失敗 (line 236)。PLRU ツリーが 2 の累乗を前提としているため

### 12.2 仕様との差異 / 要検証項目

- [ ] **要検証**: DC.V=0 の DC を送ると `update_i` が無視される (`up_content_i[0]=0` の場合、line 120)。CDW が V=0 の DC を返す場面の仕様確認 (IOMMU Spec §3.1.3.1)
- [ ] **推測**: フラッシュ時に `content_q` は書き換えない (`tags_n[i].valid=0` のみ)。次の update で上書きされる前のゴミデータが残る設計だが、`valid=0` で参照されないため問題なし

### 12.3 TODO

- [ ] 単体 TB の作成 (`/create-tb rtl/translation_logic/rv_iommu_ddtc.sv`)
- [ ] PLRU 置換順序の網羅テスト (ENTRIES=4 の 8 パターン確認)
- [ ] flush (DV=0) → lookup で miss になることの確認
- [ ] flush (DV=1, DID マッチ) → 当該エントリのみ miss になることの確認

---

## 13. 関連仕様

| トピック | 参照ファイル |
|---|---|
| DDT Cache 無効化 (IODIR.INVAL_DDT) / Cache 動作仕様 §3.8 | `doc/spec/riscv-iommu/06-chapter-3.-data-structures.md` §3.8 |
| DC レイアウト (tc.V, iohgatp, fsc 等) | 同上 §3.1.3 |
| ソフトウェア側の IODIR.INVAL_DDT 発行順序 | `doc/spec/riscv-iommu/10-chapter-7.-software-guidelines.md` §7.4 |

---

## 14. 変更履歴

| 日付 | 変更者 | 内容 |
|---|---|---|
| `2026-04-27` | Claude | 初版作成 (RTL `rtl/translation_logic/rv_iommu_ddtc.sv` 257 行から解析、BR01-BR08 抽出) |
