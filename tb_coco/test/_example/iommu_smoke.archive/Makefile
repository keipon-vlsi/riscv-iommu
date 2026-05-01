# =============================================================================
# Makefile — riscv_iommu Phase 1 スモークテスト
#
# このファイルは「Makefile_iommu_smoke」として出力していますが、
# 実際に使うときは tb_coco/test/.../riscv_iommu/Makefile にリネームして配置してください。
# =============================================================================

# ---- 波形ダンプを有効化 ----
# cocotb 2.0 で VERILATOR_TRACE は deprecated になり、WAVES=1 が推奨。
# それでも保険として COMPILE_ARGS に --trace を直接足しておく
# (Makefile.verilator が WAVES を見落としても、これで確実に有効化される)。
WAVES := 1
export WAVES
COMPILE_ARGS += --trace --trace-structs

TOPLEVEL_LANG = verilog
SIM           ?= verilator

# ---- リポジトリのルート (絶対パスがおすすめ) ----
RTL_ROOT ?= /Users/keipon/Desktop/project/tt_pretraining/riscv-iommu-kawano

# =============================================================================
# (1) ソースファイル
#
# 戦略:
#   - パッケージは wrapper SV 内の `include で読み込まれる → VERILOG_SOURCES に入れない
#   - 実装ファイルだけ rtl/ と vendor/ から find で集める
#   - 最後に wrapper を追加 (toplevel)
# =============================================================================
VERILOG_SOURCES := \
  $(PWD)/tb_riscv_iommu_wrapper.sv \
  $(shell find $(RTL_ROOT)/rtl    -name "*.sv" \
                                  -not -path "*/temp/*" \
                                  -not -name "copy_*") \
  $(shell find $(RTL_ROOT)/vendor -name "*.sv")
# ★ ラッパを最初に置く理由:
#   ラッパ内の `include でパッケージ (rv_iommu_pkg.sv 等) が定義される。
#   Verilator はファイルをコマンドライン順に処理するため、
#   ラッパを最後に置くと rtl/ 内のファイルがパッケージを参照する時点で
#   まだ定義されておらず "Reference to ... before declaration" エラーになる。
#   ラッパを先頭にすることで、最初にパッケージが定義され、その後 rtl/ が
#   パッケージを正しく参照できるようになる。

# =============================================================================
# (2) インクルードパス
#
# lint_checks の Makefile からコピー + repo ルート (lint_wrapper_pkg.sv 用)
# =============================================================================
# ローカルスタブ用 include パス (common_cells/assertions.svh など、無いものを補う)
COMPILE_ARGS += -I$(PWD)/stub
COMPILE_ARGS += -I$(RTL_ROOT)
COMPILE_ARGS += -I$(RTL_ROOT)/packages/dependencies
COMPILE_ARGS += -I$(RTL_ROOT)/packages/rv_iommu
COMPILE_ARGS += -I$(RTL_ROOT)/vendor
COMPILE_ARGS += -I$(RTL_ROOT)/include
COMPILE_ARGS += -I$(RTL_ROOT)/rtl
COMPILE_ARGS += -I$(RTL_ROOT)/rtl/translation_logic
COMPILE_ARGS += -I$(RTL_ROOT)/rtl/translation_logic/cdw
COMPILE_ARGS += -I$(RTL_ROOT)/rtl/translation_logic/ptw
COMPILE_ARGS += -I$(RTL_ROOT)/rtl/translation_logic/wrapper
COMPILE_ARGS += -I$(RTL_ROOT)/rtl/software_interface
COMPILE_ARGS += -I$(RTL_ROOT)/rtl/software_interface/regmap
COMPILE_ARGS += -I$(RTL_ROOT)/rtl/software_interface/wrapper
COMPILE_ARGS += -I$(RTL_ROOT)/rtl/ext_interfaces

# =============================================================================
# (3) Verilator 警告抑制
#
# ・LATCH: lint Makefile も付けてる
# ・WIDTH 系: cocotb シミュレーションでは WIDTHTRUNC をエラー扱いしないと
#             この規模の repo は通らないことが多い
# ・CASEINCOMPLETE: enum default case 省略の警告 (この repo によくある)
# ・UNUSED / UNDRIVEN: タイオフした信号への警告対策
# =============================================================================
# SystemVerilog バージョンを 1800-2017 に固定
# Verilator 5.046 の default は 1800-2023 で、パッケージ型の暗黙参照に厳しい。
# repo は 1800-2017 時代の書き方が多いので、こちらに合わせる。
COMPILE_ARGS += --language 1800-2017

COMPILE_ARGS += -Wno-LATCH
COMPILE_ARGS += -Wno-WIDTH
COMPILE_ARGS += -Wno-WIDTHTRUNC
COMPILE_ARGS += -Wno-WIDTHEXPAND
COMPILE_ARGS += -Wno-CASEINCOMPLETE
COMPILE_ARGS += -Wno-UNUSED
COMPILE_ARGS += -Wno-UNDRIVEN
COMPILE_ARGS += -Wno-UNOPTFLAT

# =============================================================================
# (4) cocotb 設定
# =============================================================================
TOPLEVEL = tb_riscv_iommu_wrapper
MODULE   = test_smoke

# ---- cocotb 共通 Makefile を include ----
include $(shell cocotb-config --makefiles)/Makefile.sim

# =============================================================================
# (5) 補助ターゲット
# =============================================================================
sim-log:
	$(MAKE) sim 2>&1 | tee sim.log

# 波形ファイル探し
find-waves:
	@find . \( -name "*.vcd" -o -name "*.fst" \) -print 2>/dev/null

# 波形のテキストスナップショット (vcdvcd 使用、要 pip install vcdvcd)
wave-report:
	@python3 wave_snapshot.py --all -o wave_report.md
	@echo "✓ wrote: wave_report.md"

# 単一テストのスナップショット表示 (例: make wave-test TEST=test_06)
wave-test:
	@python3 wave_snapshot.py --test $(TEST)

# テスト & グループ一覧
wave-list:
	@python3 wave_snapshot.py --list-tests
	@echo ""
	@python3 wave_snapshot.py --list-groups

# 全テスト分の SVG 波形画像を wave_images/ に生成
wave-images:
	@python3 wave_image.py --all
	@echo "✓ wrote: wave_images/*.svg"

# 単一テストの SVG (例: make wave-image TEST=test_06)
wave-image:
	@python3 wave_image.py --test $(TEST) -o wave_$(TEST).svg
	@echo "✓ wrote: wave_$(TEST).svg"

# 完全クリーン
clean::
	rm -rf sim_build __pycache__
	rm -f  results.xml dump.vcd dump.fst sim.log
	@echo "✓ cleaned"

# デバッグ: パスや変数の確認
show-vars:
	@echo "RTL_ROOT        = $(RTL_ROOT)"
	@echo "TOPLEVEL        = $(TOPLEVEL)"
	@echo "MODULE          = $(MODULE)"
	@echo "VERILATOR_TRACE = $(VERILATOR_TRACE)"
	@echo ""
	@echo "VERILOG_SOURCES (count): $(words $(VERILOG_SOURCES))"
	@echo "VERILOG_SOURCES (head):"
	@for f in $(wordlist 1,5,$(VERILOG_SOURCES)); do echo "  $$f"; done
	@echo "  ..."
	@echo ""
	@echo "COMPILE_ARGS:"
	@for f in $(COMPILE_ARGS); do echo "  $$f"; done