---
description: 指定モジュールの RTL を解析して doc/modules/<rtl_subdir>/<name>.md を生成 (RTL パスをミラーリング)
---

# /create-module-card — モジュールカード生成

引数: **$ARGUMENTS** (対象 RTL ファイルの絶対/相対パス、例: `rtl/translation_logic/rv_iommu_ddtc.sv`)

以下の手順に **厳密に** 従ってください。推測禁止、file:line 引用必須。

---

## Phase 0: 出力パス算出 (最初に必ず)

引数 `$ARGUMENTS` から出力先パスを以下のルールで算出する:

1. `$ARGUMENTS` の中から `rtl/` 以降の相対パスを抽出する
   - 例: `/path/to/repo/rtl/translation_logic/cdw/rv_iommu_cdw_pc.sv` → `translation_logic/cdw/rv_iommu_cdw_pc.sv`
   - 例: `rtl/riscv_iommu.sv` → `riscv_iommu.sv`
2. 拡張子を `.sv` → `.md` に変換
3. `doc/modules/` をプレフィックスとして付加
4. これを **`OUTPUT_DOC_PATH`** とする

| 入力例 | `OUTPUT_DOC_PATH` |
|---|---|
| `rtl/translation_logic/cdw/rv_iommu_cdw_pc.sv` | `doc/modules/translation_logic/cdw/rv_iommu_cdw_pc.md` |
| `rtl/translation_logic/rv_iommu_ddtc.sv` | `doc/modules/translation_logic/rv_iommu_ddtc.md` |
| `rtl/ext_interfaces/rv_iommu_prog_if.sv` | `doc/modules/ext_interfaces/rv_iommu_prog_if.md` |
| `rtl/riscv_iommu.sv` | `doc/modules/riscv_iommu.md` |

5. `OUTPUT_DOC_PATH` の **親ディレクトリを Bash で `mkdir -p` 作成** する (既存でも問題なし)

---

## Phase 1: 準備確認

1. `doc/_template/module_card_template.md` を Read で読み込む
2. `CLAUDE.md` の "Specification Navigation" と "Working Rules" を確認
3. `OUTPUT_DOC_PATH` が既に存在する場合はユーザに上書き確認を取る (AskUserQuestion)

---

## Phase 2: RTL の特定

1. `$ARGUMENTS` で指定された RTL ファイルを直接 `Read` する
2. **見つからない**場合は `Glob` で `rtl/**/*<module_name>*.sv` を探す
3. **複数候補**がある場合は `AskUserQuestion` でユーザに選択確認
4. 確定したファイルを `Read` で全文読み込む

---

## Phase 3: 関連情報の収集

並列で以下を実行 (可能な限り 1 メッセージ内で):

- **親モジュール**: `Grep` で `"<module_name>\s*#?\s*\(" rtl/` を検索 (インスタンス化箇所)
- **既存 TB**: `Glob` で `tb_coco/**/*<module_name>*` と `tb/**/*<module_name>*` を探す
- **パッケージ依存**: RTL の `import` 文を確認
- **パラメータ定義**: RTL の `parameter` 宣言を抽出

---

## Phase 4: 仕様書参照

CLAUDE.md の Specification Navigation から該当トピックのファイルを特定し、必要な章だけ `Read` する。
モジュール種別と参照先の目安:

- **PTW 系** → `doc/spec/riscv-iommu/06-chapter-3.-data-structures.md` §3.3
- **CDW 系** → 同上 §3.1 / §3.2
- **キャッシュ系 (IOTLB/DDTC/PDTC)** → 同上 §3.8 + `10-chapter-7.-software-guidelines.md`
- **CQ/FQ 系** → `07-chapter-4.-in-memory-queue-interface.md`
- **MSI 系** → `06-chapter-3.-data-structures.md` 内の msiptp 節
- **AXI interface** → `doc/spec/IHI0022L_amba_axi_protocol_spec/` の該当章
- **PTE 形式 / A/D / SUM** → `doc/spec/riscv-privileged/14-chapter-12.-supervisor-level-isa-version-1.13.md`
- **G-stage (Sv39x4)** → `doc/spec/riscv-privileged/24-chapter-22.-h-extension-for-hypervisor-support-version-1.0.md`

---

## Phase 5: カード生成

テンプレートをベースに、以下を埋めて **`OUTPUT_DOC_PATH`** に Write:

### 埋める範囲
- ✅ Quick Reference (全項目)
- ✅ §1 概要
- ✅ §2 パラメータ
- ✅ §3 I/O ポート (Inputs / Outputs / 双方向すべて)
- ✅ §4 内部状態 (FSM がある場合は Mermaid で、無ければ節削除)
- ✅ §5 データフロー / 分岐図 (Mermaid flowchart)
- ✅ §6 条件分岐一覧 (RTL の if/else/case を BR-ID 付きで網羅)
- ✅ §7 モジュール間連携 (上流/下流/横、BR-ID と連動)
- ✅ §8 タイミング / プロトコル注意点
- ⏸ §9 テストマトリクス (**骨組みのみ** — 表ヘッダと空行 1 つだけ)
- ⏸ §10 テスト実装ノート (わかる範囲だけ)
- ⏸ §11 ログパース用ヒント (空でOK、T-ID 設計時に埋める)
- ✅ §12 既知の挙動 / 要検証項目 (RTL 読解中に見つけたもの)
- ✅ §13 関連仕様 (実ファイル名で)
- ✅ §14 変更履歴 (初版作成の記録)

### 埋め方のルール
- すべての RTL 参照は `file:line` で引用
- 推測は `**推測:**` プレフィックス付き
- 不明な項目は **TBD** と書いて空欄にしない
- BR-ID は 01 から連番 (RTL 出現順)
- §5 Mermaid flowchart は **正常系=緑、エラー系=赤** で色分け

### Mermaid 安全規則 (生成時に必ず守る)

- **`()` をラベルテキスト内で使わない** — `(line 123)` → `line 123`、`(superpage)` → `superpage`。特に diamond `{...}` ラベルと subgraph タイトルでは必ず排除する。
- **`[i]`, `[0]` 等の `[変数名]` をラベルテキスト内で使わない** — Mermaid がノード参照として誤解析する。`tags_n[i]` → `tags_n_i`、`new_index[0]` → `new_index_0`。
- **`||` を diamond `{...}` ラベル内で使わない** — パイプ構文と衝突する。`is_1G || is_2M` → `is_1G or is_2M`。
- **subgraph タイトル文字列に `(` `)` を含めない** — `["name (detail)"]` → `["name detail"]`。
- **`stateDiagram-v2` の遷移ラベルに `\n` を使わない** — 遷移ラベルは1行。複数情報は ` / ` や ` ` で区切る。`A --> B : label\n(comment)` → `A --> B : label comment`。
- **flowchart のエッジラベル `|...|` 内に `\n` を使わない** — Mermaid がソース改行として解釈し、その後の `(` を形状構文として誤解析する。`|cond &\n(sub)|` → `|cond & sub|`。改行が必要なら引用符付き `|"cond &\nsub"|` にする。

---

## Phase 6: 完了報告

以下を **構造化して** 報告:

```
✓ <OUTPUT_DOC_PATH> を生成しました

対象 RTL:
  - <file1.sv> (<N> 行)
  - <file2.sv> (<N> 行)

埋めたセクション: §1-§8, §12-§14
骨組みのみ: §9-§11 (テスト設計時に別途)

検出した分岐: <N> 個 (BR01-BR<NN>)
検出した既知制約: <N> 件

次のアクションの提案:
  1. 生成内容をレビュー (特に §6 条件分岐の見落としチェック)
  2. §9 Test Matrix をテスト計画に従って埋める
  3. TB 作成に進む (/create-tb $ARGUMENTS 想定)

TBD として残した項目:
  - <list>
```
