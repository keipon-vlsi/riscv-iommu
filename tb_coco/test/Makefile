# =============================================================================
# Makefile — riscv_iommu cocotb 統合テスト (v4, Docker / 相対パス対応)
#
# 配置場所:  tb_coco/test/Makefile        ← v4 で _example/iommu_smoke/ から昇格
#
# ディレクトリ構成 (repo を /workspace に bind-mount した場合):
#   /workspace/                              ← REPO_ROOT
#   ├── rtl/  packages/  vendor/  include/   ← RTL
#   ├── third_party/iommu-reference/         ← submodule
#   └── tb_coco/test/                        ← この Makefile はここ
#       ├── helpers/      補助関数パッケージ
#       ├── scenarios/    test_*.py
#       ├── stub/         common_cells/assertions.svh など
#       ├── reference/gen_vectors/   ← 参照モデルからベクタ生成
#       ├── translation_logic/ptw/   ← モジュール単位のテスト (ptw 単体)
#       └── tb_riscv_iommu_wrapper.sv
#
# RTL_ROOT は __この Makefile からの相対__ で解決する。
# Docker / ホスト / CI どこでも動く。
# =============================================================================

# ---- 波形ダンプ ----
WAVES := 1
export WAVES
COMPILE_ARGS += --trace --trace-structs

TOPLEVEL_LANG = verilog
SIM           ?= verilator

# ---- repo root を相対で確定 ----
#  この Makefile は tb_coco/test/Makefile に置かれる前提なので、
#  そこから 2 階層上 (= ../../) が repo root。
HERE      := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RTL_ROOT  ?= $(abspath $(HERE)/../..)

# =============================================================================
# (1) ソースファイル
# =============================================================================
VERILOG_SOURCES := \
  $(HERE)/tb_riscv_iommu_wrapper.sv \
  $(shell find $(RTL_ROOT)/rtl    -name "*.sv" \
                                  -not -path "*/temp/*" \
                                  -not -name "copy_*") \
  $(shell find $(RTL_ROOT)/vendor -name "*.sv")

# =============================================================================
# (2) インクルードパス
# =============================================================================
COMPILE_ARGS += -I$(HERE)/stub
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
# (3) Verilator フラグ
# =============================================================================
COMPILE_ARGS += --language 1800-2017
COMPILE_ARGS += -Wno-LATCH
COMPILE_ARGS += -Wno-WIDTH
COMPILE_ARGS += -Wno-WIDTHTRUNC
COMPILE_ARGS += -Wno-WIDTHEXPAND
COMPILE_ARGS += -Wno-CASEINCOMPLETE
COMPILE_ARGS += -Wno-UNUSED
COMPILE_ARGS += -Wno-UNDRIVEN
COMPILE_ARGS += -Wno-UNOPTFLAT

# ---- RTL カバレッジ (A: 自作 RTL のカバレッジ) ----
#  make COVERAGE=1 sim  で line + toggle カバレッジ取得。
ifeq ($(COVERAGE),1)
  COMPILE_ARGS += --coverage
  COMPILE_ARGS += --coverage-line --coverage-toggle
endif

# =============================================================================
# (4) cocotb 設定
# =============================================================================
TOPLEVEL = tb_riscv_iommu_wrapper

# ★ MODULE はカンマ区切り。新ファイルを足したらここに追記。
MODULE ?= test_smoke,test_ptw_normal,test_ptw_fault,test_ptw_access,test_iotlb

# ---- PYTHONPATH ----
#  HERE             … 'helpers' パッケージが見える (from helpers import IommuEnv)
#  HERE/scenarios   … cocotb の MODULE=test_xxx で短名 import できる
export PYTHONPATH := $(HERE):$(HERE)/scenarios:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim

# =============================================================================
# (5) 補助ターゲット
# =============================================================================
smoke:
	$(MAKE) sim MODULE=test_smoke

# =============================================================================
# replay — golden_vectors.jsonl の 1124 ケースを RTL に流して diff
# =============================================================================
GOLDEN_JSONL  ?= $(HERE)/reference/gen_vectors/golden_vectors.jsonl
RTL_LOG_JSONL ?= $(HERE)/rtl_log.jsonl
DIFF_TOOL     ?= $(RTL_ROOT)/scripts/diff_logs.py

# golden_vectors.jsonl が無ければ自動生成
$(GOLDEN_JSONL):
	$(MAKE) -C $(HERE)/reference/gen_vectors run

replay: $(GOLDEN_JSONL)
	GOLDEN_JSONL=$(GOLDEN_JSONL) RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	  $(MAKE) sim MODULE=test_replay_golden
	@echo ""
	@echo "==== Diff RTL vs reference ===="
	@python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) --ref $(GOLDEN_JSONL)

# 1 件目のミスマッチで停止 (デバッグ用)
replay-fail-fast: $(GOLDEN_JSONL)
	GOLDEN_JSONL=$(GOLDEN_JSONL) RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	  $(MAKE) sim MODULE=test_replay_golden
	@python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) --ref $(GOLDEN_JSONL) --fail-fast

# golden_vectors.jsonl だけ作りたい (RTL は触らない)
golden-vectors:
	$(MAKE) -C $(HERE)/reference/gen_vectors run

ptw-normal:
	$(MAKE) sim MODULE=test_ptw_normal

ptw-fault:
	$(MAKE) sim MODULE=test_ptw_fault

ptw-access:
	$(MAKE) sim MODULE=test_ptw_access

iotlb:
	$(MAKE) sim MODULE=test_iotlb

# 1 ケースだけ実行: make one MODULE=test_ptw_fault TEST=test_20_pte_invalid
one:
	$(MAKE) sim MODULE=$(MODULE) TESTCASE=$(TEST)

sim-log:
	$(MAKE) sim 2>&1 | tee sim.log

# ---- RTL カバレッジレポート (Verilator + lcov) ----
#  COVERAGE=1 で sim を回した後に呼ぶ。
coverage-report:
	verilator_coverage --write-info coverage.info sim_build/coverage.dat
	genhtml coverage.info --output-directory coverage_html
	@echo ""
	@echo "✓ HTML report: $(HERE)/coverage_html/index.html"

find-waves:
	@find . \( -name "*.vcd" -o -name "*.fst" \) -print 2>/dev/null

wave-report:
	@python3 wave_snapshot.py --all -o wave_report.md
	@echo "✓ wrote: wave_report.md"

wave-test:
	@python3 wave_snapshot.py --test $(TEST)

wave-list:
	@python3 wave_snapshot.py --list-tests
	@echo ""
	@python3 wave_snapshot.py --list-groups

wave-images:
	@python3 wave_image.py --all
	@echo "✓ wrote: wave_images/*.svg"

wave-image:
	@python3 wave_image.py --test $(TEST) -o wave_$(TEST).svg

clean::
	rm -rf sim_build __pycache__ helpers/__pycache__ scenarios/__pycache__
	rm -f  results.xml dump.vcd dump.fst sim.log
	rm -rf coverage.info coverage_html

show-vars:
	@echo "HERE       = $(HERE)"
	@echo "RTL_ROOT   = $(RTL_ROOT)"
	@echo "TOPLEVEL   = $(TOPLEVEL)"
	@echo "MODULE     = $(MODULE)"
	@echo "PYTHONPATH = $(PYTHONPATH)"
	@echo "COVERAGE   = $(COVERAGE)"

.PHONY: smoke replay replay-fail-fast golden-vectors \
        ptw-normal ptw-fault ptw-access iotlb one sim-log \
        find-waves wave-report wave-test wave-list wave-images wave-image \
        coverage-report show-vars