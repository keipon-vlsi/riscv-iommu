---
description: sim.log を読んで test plan §4 の Status / Last Run / カバレッジサマリを自動更新
---

# /update-test-status — シミュレーション結果の反映

**引数**: `$ARGUMENTS` = モジュール名 (例: `rv_iommu_ptw_sv39x4_pc`)

## 動作概要

`make test` 実行後に呼び出す。以下を自動更新:

- §4 の各 T-ID の **Status 列** (✅ PASS / ❌ FAIL / ⏸ SKIP)
- §4 の各 T-ID の **Last Run 列** (YYYY-MM-DD HH:MM)
- §4.5 カバレッジサマリ (数値再計算)
- §7 変更履歴に「auto-status」エントリを追記
- frontmatter の `last_status_update` を今日に

**`reviewed` フラグは変更しない** (Status 更新は内容変更ではないため)。

---

## Phase 1: ファイル特定

1. test plan を Read:
    - `doc/test-plan/$ARGUMENTS.md`
    - 無ければエラー: "先に `/create-tb` でプラン生成を"
2. sim.log を Glob で探す:
    - frontmatter の `tb_dir` を確認
    - `<tb_dir>/sim.log` を Read
    - 無ければエラー: "先に `make sim-log` を実行"

## Phase 2: テスト結果抽出

cocotb のログから PASS/FAIL を抽出。典型的な書式:

```
0000.00ns INFO     cocotb.regression       test_xxx passed
0000.00ns FAIL     cocotb.regression       test_xxx failed
0000.00ns INFO     cocotb.regression       test_xxx skipped
```

正規表現:
- PASS: `(test_\w+)\s+(passed|failed|skipped)`
- sim.log を全行 Grep して `{関数名: 結果}` の dict を作る

## Phase 3: T-ID → 関数名マッピング

test plan §4 の各テーブルの「TB 場所」列から `::test_xxx` 部分を抽出:

```
scenario/test_directed.py::test_s1_4k
                          ^^^^^^^^^^^^ ← 関数名
```

得られるマップ:
```
T01 → test_s1_4k
T02 → test_s1_2M
...
```

## Phase 4: Status 列の更新

各 T-ID について:
- 関数名が sim.log に現れない → **⏱ PENDING** (変化なし)
- `passed` → **✅ PASS**
- `failed` → **❌ FAIL**
- `skipped` → **⏸ SKIP**

Last Run 列に今日の日時 (`YYYY-MM-DD HH:MM`) を入れる。

**既存 Status を上書きする時の例外**:
- 前回 **🚧 WIP** の項目は変更しない (ユーザが意図的に設定した)

## Phase 5: §4.5 カバレッジサマリ再計算

各カテゴリ (正常系/エッジ/フォルト/ランダム) について:
- 計 = 当該 T/R-ID の総数
- PASS/FAIL/SKIP = 各状態の数
- PENDING = 残り

合計行も同様に集計。

## Phase 6: frontmatter 更新

- `last_status_update: <今日>`
- `reviewed` は **変更しない**
- `last_modified_by_claude` も **変更しない** (内容変更ではないため)

## Phase 7: §7 変更履歴追記

以下を **追記 (既存行を変更しない)**:

```
| <今日> | Claude (auto-status) | Status 列更新: PASS +N, FAIL +M (sim.log から) | 変化なし |
```

## Phase 8: 報告

```
✓ doc/test-plan/$ARGUMENTS.md の Status を更新しました

結果サマリ (前回との比較):
  ✅ PASS    : <N> 件  (前回比 +X / -Y)
  ❌ FAIL    : <N> 件  (前回比 +X / -Y)
  ⏸ SKIP    : <N> 件
  ⏱ PENDING : <N> 件

今回新たに FAIL した T-ID:
  - T05: test_xxx (前回 PASS → FAIL)

今回新たに PASS した T-ID:
  - T08: test_yyy (前回 PENDING → PASS)

次アクション:
  - FAIL の項目を確認してください (ログ: tb_coco/test/<path>/sim.log)
  - PENDING の項目は関数未実装の可能性、TB を確認
  - /check-br-coverage $ARGUMENTS で BR-ID カバレッジも確認
```

---

## 禁止事項

- ❌ `reviewed` フラグを変更する (Status 更新のみでは内容変化なし)
- ❌ §4 の **シナリオ/入力条件/期待出力** 列を変更する (Status と Last Run のみ)
- ❌ 既存の T-ID を消す
- ❌ `last_modified_by_claude` を書き換える (内容変更時のみ)
- ❌ BR-ID 全件対応表 (§3) を変更する

---

## 補助: WIP マークの使い方

ユーザが一時的にテストを止めたい場合、**手動で Status を 🚧 WIP に設定**する。このコマンドは **WIP を上書きしない** ので、スキップ扱いで進められる。

---

## 補助: 一括確認のワンライナー (参考)

Claude が使わなくても、ユーザが手軽に確認したい場合:

```bash
# sim.log から結果一覧
grep -E "test_\w+\s+(passed|failed)" tb_coco/test/<path>/sim.log

# T-ID ごとの結果
grep -oE "test_\w+" doc/test-plan/<module>.md | sort -u > /tmp/tids.txt
grep -oE "test_\w+\s+(passed|failed)" tb_coco/test/<path>/sim.log
```