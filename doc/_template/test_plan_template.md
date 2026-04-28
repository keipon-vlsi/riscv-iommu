<!--
===================================================================
テストプランテンプレート
===================================================================

用途:
  - /create-tb で生成するテスト計画の雛形
  - BR-ID → T-ID → TB 実装の対応表
  - sim ログから Status 列を自動更新可

フィールド規約:
  - frontmatter の `reviewed` はユーザが手動で true に変更 (レビュー完了の合図)
  - Claude が内容を変更した場合、必ず reviewed を false に戻す
  - Status 列のみの更新 (sim.log パース結果反映) は reviewed を変更しない

更新ルール (Claude 向け):
  - 既存の T-ID / BR-ID は renumber しない (追加は末尾)
  - 既存の Status 列を手動で書き換えない (自動更新ツール経由のみ)
  - 内容 (シナリオ・制約・期待値) を変更したら frontmatter の
    last_modified_by_claude を今日に、reviewed を false に
===================================================================
-->

---
module: <module_name>
source: rtl/<path>/<file>.sv
module_card: doc/modules/<module_name>.md
tb_dir: tb_coco/test/<path>/
reviewed: false
reviewed_by: null
reviewed_date: null
last_modified_by_claude: <YYYY-MM-DD>
last_status_update: null
generated: <YYYY-MM-DD>
---

# テスト計画: `<module_name>`

<!-- レビュー状態バナー (Claude は reviewed の値に応じて書き換えること) -->

> ⚠️ **レビュー状態: ⏳ レビュー待ち (reviewed: false)**
>
> このテストプランは Claude が生成/更新した直後の状態です。
> 内容を確認したら frontmatter の `reviewed: true` に変更してください。
> Claude は `reviewed: true` の状態でないと TB 生成に進みません。
>
> <!-- reviewed: true になったら下記に書き換え -->
> <!-- > ✅ **レビュー状態: 承認済み (reviewed: true, by <name> on <date>)** -->

---

## 1. テスト目標

- モジュールカード §6 の **BR01–BR<NN>** を網羅する
- (正常系の方針)
- (異常系の方針)
- (ランダムの方針)
- **スコープ外**: (関係するが別レイヤでテストすべき項目)

---

## 2. テスト設定

| 項目 | 値 |
|---|---|
| **シミュレータ** | Verilator (cocotb) |
| **TB ディレクトリ** | `tb_coco/test/<path>/` |
| **トップモジュール** | `tb_<module_name>_wrapper` |
| **実行コマンド** | `cd tb_coco/test/<path> && make` |
| **ログ保存** | `cd tb_coco/test/<path> && make sim-log` |
| **Status 更新** | `/update-test-status <module_name>` (sim.log から自動) |
| **ゴールデンモデル** | `tb_coco/common/helpers.py::translate_sv39_golden` |

---

## 3. BR カバレッジ計画

| BR-ID | 概要 | カバー方法 | T-ID |
|---|---|---|---|
| BR01 | `<概要>` | `<approach>` | T01, R01 |
| BR02 | ... | ... | ... |

<!-- 必ずモジュールカード §6 の全 BR-ID がこの表の左列に出現すること -->

---

## 4. テストマトリクス

### 4.1 正常系 (Directed)

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T01 | <scenario> | <inputs> | <expected> | `scenario/test_directed.py::test_xxx` | BR01 | - | ⏱ PENDING |

### 4.2 エッジケース

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T10 | ... | ... | ... | ... | ... | - | ⏱ PENDING |

### 4.3 フォルト系

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T20 | ... | ... | ... | ... | ... | - | ⏱ PENDING |

### 4.4 ランダム

| R-ID | シナリオ | ケース数 | Seed | TB 場所 | Last Run | Status |
|---|---|---|---|---|---|---|
| R01 | <scenario> | 100 | 42 | `scenario/test_random.py::test_xxx` | - | ⏱ PENDING |

### 4.5 カバレッジサマリ

<!-- /update-test-status による自動更新対象。手動編集しない。 -->

| カテゴリ | 計 | PASS | FAIL | SKIP | PENDING |
|---|---|---|---|---|---|
| 正常系 (Directed) | 0 | 0 | 0 | 0 | 0 |
| エッジケース | 0 | 0 | 0 | 0 | 0 |
| フォルト系 | 0 | 0 | 0 | 0 | 0 |
| ランダム | 0 | 0 | 0 | 0 | 0 |
| **合計** | **0** | **0** | **0** | **0** | **0** |

---

## 5. 未カバー BR と今後の追加計画

<!-- /check-br-coverage による自動追記も受け付けるセクション -->

| 優先 | BR-ID | 追加すべきテスト | T-ID 候補 |
|---|---|---|---|
| - | - | - | - |

---

## 6. ゴールデンモデルの制限

(`translate_sv39_golden` が対応していないモード等があればここに記載)

---

## 7. 変更履歴

| 日付 | 変更者 | 内容 | reviewed 遷移 |
|---|---|---|---|
| <YYYY-MM-DD> | Claude | 初版作成 | (新規) false |
| <YYYY-MM-DD> | user | レビュー完了 | false → true |
| <YYYY-MM-DD> | Claude (auto-status) | Status 列更新 (sim.log 反映) | 変化なし |

<!--
Claude が内容を変更するたびに必ず追加する。
書式:
  | 日付 | Claude | <変更内容> | true → false (要再レビュー) |
Status 列のみの更新時:
  | 日付 | Claude (auto-status) | Status 列更新 | 変化なし |
-->