---
description: テストプラン生成 → レビュー → TB 生成 → BR カバレッジ追跡 (tb_coco/test/ にミラー配置)
---

# /create-tb — テストベンチ自動生成 (プラン駆動)

**引数**: `$ARGUMENTS` = 対象 RTL ファイルパス

使用例:
```
/create-tb rtl/translation_logic/iotlb/rv_iommu_iotlb_sv39x4.sv
/create-tb rtl/translation_logic/cdw/rv_iommu_cdw_pc.sv
```

## 重要な前提

- モジュールカード `doc/modules/<module_name>.md` が **既に存在する** こと
  (無ければ "/create-module-card を先に実行" とエラー終了)

---

## ファイル配置規則 (絶対遵守)

### 出力先ディレクトリ

RTL のパスを `rtl/` → `tb_coco/test/` に置換したディレクトリ:

```
rtl/translation_logic/ptw/rv_iommu_ptw_sv39x4_pc.sv
  ↓
tb_coco/test/translation_logic/ptw/
```

```
rtl/software_interface/rv_iommu_fq_handler.sv
  ↓
tb_coco/test/software_interface/
```

### ファイル名

**全て `<module_name>` をベースにする** (モジュール名 = RTL 内の `module <name>` の `<name>`)。

例: module 名が `rv_iommu_ptw_sv39x4_pc` の場合:

| ファイル種別 | ファイル名 |
|---|---|
| TB ラッパ (SV) | `tb_rv_iommu_ptw_sv39x4_pc_wrapper.sv` |
| テスト本体 (Python) | `test_rv_iommu_ptw_sv39x4_pc.py` |
| Makefile | `Makefile` (共通) |
| Directed scenario | `scenario/test_directed.py` |
| Random scenario | `scenario/test_random.py` |
| Fault scenario | `scenario/test_fault.py` |

モジュール名が短ければ短縮形もあり得るが、**短縮せずフルで命名するのが原則**。

---

## ワークフロー

`doc/test-plan/<module_name>.md` の frontmatter `reviewed` を根拠に分岐:

| 状態 | 動作 |
|---|---|
| test plan **無** | → Phase A: プラン雛形生成 (reviewed: false で作成) |
| test plan **有、reviewed: false** | → 「レビューして reviewed:true にしてから再実行」と案内 |
| test plan **有、reviewed: true**、**TB 無** | → Phase B-new: TB 新規生成 |
| test plan **有、reviewed: true**、**TB 有** | → Phase B-merge: 既存 TB に差分追記/修正 |

## Review 状態のハンドリング (厳格)

Claude が test plan の **内容を変更** したら:

1. frontmatter の `reviewed:` を **必ず `false` に戻す**
2. `reviewed_by:`, `reviewed_date:` を `null` にクリア
3. `last_modified_by_claude:` を今日に更新
4. 本文冒頭の「レビュー状態バナー」を **⏳ レビュー待ち** に書き換え
5. §7 変更履歴に追記 (`reviewed 遷移: true → false`)

**例外: Status 列だけの変更** (`/update-test-status` 経由) は内容変更ではないので、`reviewed` は変更しない。

---

## Phase 0: 前提確認 & パス算出

1. $ARGUMENTS の RTL ファイル存在確認
2. **モジュール名抽出**:
    - RTL を Read し、冒頭で `module\s+(\w+)` を Grep
    - 見つからなければ `basename($ARGUMENTS .sv)` を使用
    - 取れた値を以下 `<module_name>` とする
3. **出力ディレクトリ算出**:
    - 入力: `rtl/<path>/<file>.sv`
    - 出力: `tb_coco/test/<path>/`
    - 例: `rtl/translation_logic/ptw/X.sv` → `tb_coco/test/translation_logic/ptw/`
    - 注意: `rtl/` を `tb_coco/test/` に置換するだけ。ファイル名部分は含めない
4. **モジュールカード**:
    - `doc/modules/<module_name>.md` 存在確認
    - 無ければエラー: "先に `/create-module-card $ARGUMENTS` を実行"
5. **test plan 状態確認**:
    - `doc/test-plan/<module_name>.md` の有無 + `reviewed` フラグ

---

## Phase A: テストプラン雛形生成 (高カバレッジ優先)

### A-0: 必須ドキュメント読込

以下を順に Read:

1. `doc/_template/coverage_methodology.md` — 網羅戦略 6 ステップ
2. `doc/_template/test_plan_template.md` — 出力フォーマット
3. **`doc/test-plan/_must_test_<module_name>.md`** — 人間が書いた必須シナリオ
    - 存在すれば: その全項目を **T-ID として必ず含める**
    - 存在しなければ: AskUserQuestion で確認:
        - "must_test list がありません。先にドメイン固有のシナリオを書きますか?
           [Write: テンプレ生成 → ユーザ記入 → 再開, Skip: methodology のみで進む]"
4. `doc/design-log.md` (バグ履歴を再発防止用に参照)
5. `doc/feedback.md` 同上

methodology の **6 ステップを全実行** する (RTL 分析 → spec mining → cross-product →
edge case → random → プロジェクト固有)。
**must_test の項目は機械的網羅とは別カテゴリで、最優先で T-ID を割り当てる**。

### A-1: RTL 系統的分析 (Step 1)

1. モジュールカード §6 の全 BR-ID を抽出・カウント (N 個)
2. 各 BR-ID について:
    - **True パスの directed テスト** を追加
    - **False パスの directed テスト** を追加
3. モジュールカード §4.2 の全 FSM 遷移を抽出
4. 各遷移トリガに対するテスト追加

### A-2: 仕様書 Mining (Step 2)

1. モジュールカード §13 の参照仕様ファイルを列挙
2. 各ファイルを `Read` し、`Grep` で `Table \d+` を検索
3. 各 Table について:
    - 行数をカウント (K 行)
    - **各行に 1 テスト** を directed に追加
4. spec の "SHALL" / "MUST" を抽出し、違反ケースを fault 系に

### A-3: Cross-product 列挙 (Step 3)

典型的な交差を **全列挙**:
- PTE `R × W × X` (8 or 6 通り、reserved 除く)
- `priv_lvl × pte.U × SUM` (8 通り)
- `en_1S × en_2S` (4 通り)
- `access_type × stage_mode` (最大 12 通り)
- その他、当該モジュール固有の交差

### A-4: Edge case チェックリスト (Step 4)

Coverage methodology の「Edge case カタログ」を **全項目チェック**。該当すれば必ず T-ID 追加。

### A-5: Random 設計 (Step 5)

- ケース数: BR 数に応じて 100-300 件
- Seed 固定
- ゴールデンモデル経由で期待値

### A-6: プロジェクト固有 (Step 6)

- `req_trans_i` の High 保持制約
- MSITrans の各設定
- Force 方式適用点
- CDW 暗黙的変換

### A-7: ファイル書き出し

`doc/test-plan/<module_name>.md` を Write:
- frontmatter `reviewed: false`
- §3「BR-ID 全件対応表」に **全 BR を列挙**
- §4 テストマトリクスに **directed / edge / fault / random** の 4 カテゴリで T-ID を配置

### A-8: 自己チェックレポート (必須)

生成後、以下を構造化して報告:

```
✓ 生成完了。以下のチェック結果を確認してください:

Step 1 (RTL 分析):
  - BR カバー率: 100% (<N>/<N> BR に T-ID 割当済)
  - FSM 遷移カバー率: 100% (<M>/<M>)
  - 未カバー BR: なし

Step 2 (仕様書 mining):
  - 参照した Table:
    - IOMMU Spec Table 13: 15 行 → T20-T34 (15 件)
    - Priv ISA Table 8.4: 8 行 → T35-T42 (8 件)
  - SHALL 文: <N> 件 → 違反ケース <M> 件

Step 3 (Cross-product):
  - R×W×X: 6 通り (reserved 2 除く) → T50-T55
  - priv×U×SUM: 8 通り → T60-T67
  - en_1S×en_2S: 4 通り → T01-T04 (正常系に含む)

Step 4 (Edge case):
  ✓ Back-to-back request (T10)
  ✓ Reset during operation (T11)
  ✓ Backpressure (T12)
  ✗ Flush during lookup — 該当なし (本モジュールに flush なし)
  ...

Step 5 (Random):
  - R01: 100 ケース, seed=42
  - R02: 100 ケース, seed=43
  ...

Step 6 (プロジェクト固有):
  ✓ req_trans_i High 保持 (T13 で確認)
  ✓ MSITrans=DISABLED (本モジュールでは MSI 経路なし)
  ...

⚠ 未対応項目 (ユーザ判断を求む):
  - BR25: 現実装で到達不可能に見える → §5 に記録候補
  - <他>

総 T-ID 数: <X> 件
  - directed: <A> 件
  - edge: <B> 件
  - fault: <C> 件
  - random: <D> 件
```

### A-9: ユーザ通知

```
次の手順:
  1. doc/test-plan/<module_name>.md をレビュー
  2. §2-§4 を確認、必要なら追記/修正
  3. §3 の BR 全件対応表に漏れが無いか検証
  4. 未対応項目 (上記 ⚠) の判断
  5. OK なら frontmatter の `reviewed: true` に変更
  6. /create-tb $ARGUMENTS で再実行 (TB 生成へ)
```

---

## Phase B-new: TB 新規生成

### B-new-1: ディレクトリ作成

```
tb_coco/test/<path>/
├── Makefile
├── tb_<module_name>_wrapper.sv
├── test_<module_name>.py
└── scenario/
    ├── test_directed.py
    ├── test_random.py
    └── test_fault.py
```

`mkdir -p` で作成。既存ファイルを上書きしない (念のため `ls` で確認)。

### B-new-2: Makefile 生成

**clean ターゲット必須**。既存 TB (例: `tb_coco/test/translation_logic/ptw/` の旧 Makefile) があれば構造を参考にする。

```makefile
TOPLEVEL_LANG = verilog
SIM           = verilator

# <module_name> の RTL と TB は tb_coco/test/<path>/ にある (repo 根から 3 階層下)
MAKEFILE_DIR  := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
REPO_ROOT     := $(realpath $(MAKEFILE_DIR)../../../..)

# Python import root for tb_coco.common.helpers
export PYTHONPATH := $(REPO_ROOT)

# Auto-discover scenario/test_*.py
SCENARIO_FILES      := $(wildcard scenario/test_*.py)
MODULES_DOTS        := $(subst /,.,$(SCENARIO_FILES:.py=))
empty               :=
space               := $(empty) $(empty)
comma               := ,
export COCOTB_TEST_MODULES := $(subst $(space),$(comma),$(MODULES_DOTS))

EXTRA_ARGS += +incdir+$(REPO_ROOT)/packages/dependencies
EXTRA_ARGS += --trace --trace-structs
EXTRA_ARGS += -Wno-fatal

VERILOG_SOURCES = \
    $(REPO_ROOT)/packages/dependencies/riscv_pkg.sv \
    $(REPO_ROOT)/packages/dependencies/axi_pkg.sv \
    $(REPO_ROOT)/packages/rv_iommu/rv_iommu_pkg.sv \
    $(REPO_ROOT)/<$ARGUMENTS の実パス> \
    $(MAKEFILE_DIR)tb_<module_name>_wrapper.sv

TOPLEVEL = tb_<module_name>_wrapper

# cocotb の Makefile.sim を include (sim がデフォルトターゲットに)
include $(shell cocotb-config --makefiles)/Makefile.sim

# ログ保存
sim-log:
	$(MAKE) sim 2>&1 | tee sim.log

# クリーンアップ (:: で cocotb の既定 clean に追記)
clean::
	rm -rf sim_build
	rm -rf __pycache__
	rm -rf scenario/__pycache__
	rm -f  results.xml
	rm -f  dump.vcd dump.fst
	rm -f  sim.log *.log
	@echo "✓ cleaned sim_build, __pycache__, logs, waveforms"

distclean:: clean
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ distclean done"

# デバッグ用
debug-paths:
	@echo "MAKEFILE_DIR = $(MAKEFILE_DIR)"
	@echo "REPO_ROOT    = $(REPO_ROOT)"
	@echo "VERILOG[0]   = $(word 1,$(VERILOG_SOURCES))"
	@echo "PYTHONPATH   = $(PYTHONPATH)"
```

**注意**: `REPO_ROOT` の `../..` の階層数は **`tb_coco/test/<path>/` からの深さ** に応じて調整:
- `tb_coco/test/translation_logic/ptw/` → 4 階層 → `../../../..`
- `tb_coco/test/software_interface/` → 3 階層 → `../../..`
- Python で算出: `"../" * ("tb_coco/test/" + path).count("/")` 相当

### B-new-3: TB ラッパ生成

`tb_<module_name>_wrapper.sv`:

```systemverilog
// tb_<module_name>_wrapper.sv
// Auto-generated by /create-tb. Wraps <module_name> for cocotb testing.

module tb_<module_name>_wrapper #(
    // 元モジュールのパラメータをミラー (モジュールカード §2 から)
    ...
) (
    // 元モジュールの全ポートをそのまま外出し
    ...
    // (必要なら) force 制御ポート
    ...
);
    <module_name> #(
        ...
    ) i_dut (
        .clk_i, .rst_ni,
        ...
    );
endmodule
```

### B-new-4: Python テスト本体生成

`test_<module_name>.py` (ドライバクラスとカバレッジレポート):

```python
"""Top test driver for <module_name>.
Auto-generated by /create-tb. Individual test cases live in scenario/.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from tb_coco.common.helpers import (
    MockMemory, PteFactory, PhysicalMemoryManager,
    log_br_hit, report_br_coverage,
    # ...
)


class <ModuleName>Tester:
    """Reset, configure, trigger, observe."""
    def __init__(self, dut):
        ...
    async def reset(self): ...
    async def trigger(self, ...): ...
    async def wait_completion(self): ...


@cocotb.test()
async def test_zzz_coverage_summary(dut):
    """Reports BR coverage. Keep last in file."""
    EXPECTED_BRS = ["BR01", "BR02", ..., "BR<N>"]   # module card §6 から抽出
    report_br_coverage(dut, EXPECTED_BRS)
```

### B-new-5: Scenario 生成

`scenario/test_directed.py`, `test_random.py`, `test_fault.py`:

test plan §2 の各 T-ID を 1:1 で実装。各関数に:
- docstring で `"""T01: scenario. Covers: BR01, BR02."""`
- 先頭で `log_br_hit("BR01", dut)` を全カバー BR に対して呼ぶ
- 期待値は golden model 経由

### B-new-6: test plan 更新

`doc/test-plan/<module_name>.md` の §3「BR-ID 全件対応表」の "TB 対応" 列を埋める:

```markdown
| BR-ID | 位置 | カバー T-ID | TB 対応 |
| BR01 | ptw.sv:123 | T01, T90 | `tb_coco/test/.../scenario/test_directed.py::test_t01_basic_walk` |
```

### B-new-7: 報告

```
✓ <module_name> の TB 新規生成完了

生成ファイル:
  tb_coco/test/<path>/Makefile
  tb_coco/test/<path>/tb_<module_name>_wrapper.sv    (<N> 行)
  tb_coco/test/<path>/test_<module_name>.py          (<N> 行)
  tb_coco/test/<path>/scenario/test_directed.py      (<N> テスト)
  tb_coco/test/<path>/scenario/test_random.py        (<N> テスト × <M> ケース)
  tb_coco/test/<path>/scenario/test_fault.py         (<N> テスト)

helpers.py への追加: (承認済み関数のみ)

test plan 更新: §3 に TB 対応列追記

実行:
  cd tb_coco/test/<path> && make           (sim)
  cd tb_coco/test/<path> && make sim-log   (ログ保存)
  cd tb_coco/test/<path> && make clean     (掃除)

次: /check-br-coverage <module_name>
```

---

## Phase B-merge: 既存 TB への差分追記/修正

既に TB が存在する場合、**上書きせず差分対応**。

### B-merge-1: 既存物の読み込み

- `tb_coco/test/<path>/` 以下の全ファイルを Read
- 各ファイルから「既に実装されている T-ID」を抽出
    - docstring の `T\d+:` パターン
    - コメントの `T\d+` 参照
- 既存の helpers.py import も確認

### B-merge-2: test plan との差分算出

1. test plan §2 の全 T-ID を取得
2. 既存 TB に実装済の T-ID と突き合わせ
3. **新規 T-ID** (plan にあるが実装なし) を列挙
4. **T-ID の期待値や制約が変わったもの** を列挙 (plan の記述と TB コードを比較)
5. **plan に無い T-ID が TB にある** → ユーザに確認 (削除 or plan に追加)

### B-merge-3: 差分適用の計画提示

AskUserQuestion で提示:

```
既存 TB に対して以下の変更を適用します:

追加する T-ID (plan にあるが未実装): N 件
  - T05 → scenario/test_directed.py の末尾に追加
  - T45 → scenario/test_fault.py の末尾に追加

修正する T-ID (制約/期待が変わった): M 件
  - T02: 期待 cause code が 13 → 15 に変更 (scenario/test_directed.py)

plan 側に追記する項目: L 件
  - test_t99_legacy (plan 未登録) → T?? として plan §2 に追加候補

進めて良いですか?
  [All: 全部適用, Review: 差分を diff 形式で見せて, Partial: 項目選択, Cancel: 中止]
```

### B-merge-4: ファイル単位の差分適用

- **追加**: 既存ファイルの **末尾** に追記 (既存関数は触らない)
- **修正**: Edit で該当関数のみ差し替え (周辺は保持)
- **削除**: しない (plan に無い T-ID でも警告のみ、実装は残す)
- **Makefile**: `clean` ターゲットが無ければ追加。`VERILOG_SOURCES` に不足があれば追加
- **test plan §3**: TB 対応列を新規 T-ID 分だけ更新

### B-merge-5: 報告

```
✓ <module_name> の TB 差分適用完了

追加:
  - test_directed.py: +3 テスト (T05, T06, T07)
  - test_fault.py: +5 テスト (T45, T46, ...)

修正:
  - test_directed.py::test_t02_xxx: 期待 cause を 13→15
  - Makefile: clean ターゲット追加

変更無し: 既存 42 テストはそのまま保持

test plan 更新: 新規 T-ID 分の TB 対応列を追記

実行:
  cd tb_coco/test/<path> && make clean && make
```

---

## 共通禁止事項

- ❌ test plan 未生成 or `reviewed: false` の状態で TB 生成
- ❌ 出力先を `tb_coco/test/` 以外に置く
- ❌ `tb_<module>_wrapper.sv` / `test_<module>.py` 以外の命名を使う
- ❌ Makefile に `clean` を入れない
- ❌ 既存 TB を無断で上書きする (必ず差分として追記)
- ❌ BR hook (`log_br_hit`) を埋め込まない
- ❌ helpers.py を無断編集する

---

## 設置後ディレクトリ構造イメージ

```
riscv-iommu-kawano/
├── rtl/
│   └── translation_logic/
│       └── ptw/
│           └── rv_iommu_ptw_sv39x4_pc.sv   ← 対象
├── doc/
│   ├── modules/rv_iommu_ptw_sv39x4_pc.md
│   └── test-plan/rv_iommu_ptw_sv39x4_pc.md
└── tb_coco/
    ├── common/
    │   └── helpers.py
    └── test/                                 ← ★ ここ以下にミラー
        └── translation_logic/
            └── ptw/                          ← RTL の /ptw/ に対応
                ├── Makefile
                ├── tb_rv_iommu_ptw_sv39x4_pc_wrapper.sv
                ├── test_rv_iommu_ptw_sv39x4_pc.py
                └── scenario/
                    ├── test_directed.py
                    ├── test_random.py
                    └── test_fault.py
```

---

## 実行例

### 初回 (Phase A → Phase B-new)

```
# 1 回目: プラン雛形生成
/create-tb rtl/translation_logic/ptw/rv_iommu_ptw_sv39x4_pc.sv
→ doc/test-plan/rv_iommu_ptw_sv39x4_pc.md 生成
→ ユーザがレビュー、reviewed:true に変更

# 2 回目: TB 新規生成
/create-tb rtl/translation_logic/ptw/rv_iommu_ptw_sv39x4_pc.sv
→ tb_coco/test/translation_logic/ptw/ 配下に一式生成
```

### TB が既にある (Phase B-merge)

```
# test plan を手動編集で T-ID 追加済み
/create-tb rtl/translation_logic/ptw/rv_iommu_ptw_sv39x4_pc.sv
→ 既存 TB 検出
→ 追加/修正差分を提示
→ ユーザ承認 → 該当ファイルに append or Edit
```