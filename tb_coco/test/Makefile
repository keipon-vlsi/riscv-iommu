# =============================================================================
# Makefile — riscv_iommu cocotb 統合テスト (v5, FST default)
#
# 配置場所:  tb_coco/test/Makefile
#
# v5 変更点:
#   - デフォルト波形を VCD → FST に変更 (= file size 1/10, gtkwave 数倍速)
#   - WAVES env を廃止 (cocotb 2.0 の WAVES=1 は --trace を強制し VCD になる)
#   - WAVE_TRACE / WAVE_SCOPE 変数で trace 制御
#
# Usage:
#   make replay                          # FST trace, CDW scope (default)
#   make replay WAVE_TRACE=none          # trace 完全 OFF (= 最速)
#   make replay WAVE_SCOPE=full          # 全モジュール trace (= 重い)
#   make replay WAVE_TRACE=vcd           # 旧 VCD 形式に戻す (= 大きい)
#
# Tier:
#   smoke         : 12 ケース手書き / ~30 秒
#   replay        : quick tier / ~10-15 分     (default)
#   replay-full   : full tier  / ~60 分        (nightly CI)
# =============================================================================

# =============================================================================
# (0) Wave dump 制御 (= FST default)
# =============================================================================
# WAVE_TRACE: fst | vcd | none
# WAVE_SCOPE: cdw | full | none  (testbench 側の $dumpvars 範囲)
SHELL := /bin/bash

WAVE_TRACE ?= fst
WAVE_SCOPE ?= cdw

# cocotb 2.0 の WAVES=1 は --trace (VCD) を後付けする → 必ず unexport
unexport WAVES

ifeq ($(WAVE_TRACE),fst)
  COMPILE_ARGS += --trace-fst
  COMPILE_ARGS += --trace-threads 1
  COMPILE_ARGS += --trace-depth 8
  COMPILE_ARGS += --trace-structs
  COMPILE_ARGS += --trace-max-array 64
  COMPILE_ARGS += +define+ENABLE_WAVE_DUMP
endif
ifeq ($(WAVE_TRACE),vcd)
  COMPILE_ARGS += --trace
  COMPILE_ARGS += --trace-depth 8
  COMPILE_ARGS += --trace-structs
  COMPILE_ARGS += --trace-max-array 64
  COMPILE_ARGS += +define+ENABLE_WAVE_DUMP
  COMPILE_ARGS += +define+WAVE_FORMAT_VCD
endif
# WAVE_TRACE=none: trace flag 一切付けない

# Scope は SV testbench 側で if-define 分岐
ifeq ($(WAVE_SCOPE),cdw)
  COMPILE_ARGS += +define+WAVE_CDW
endif
ifeq ($(WAVE_SCOPE),full)
  COMPILE_ARGS += +define+WAVE_FULL
endif

COCOTB_HDL_TIMEUNIT = 1ps

TOPLEVEL_LANG = verilog
SIM           ?= verilator

# =============================================================================
# (1) Repo root を相対で確定
# =============================================================================
HERE      := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RTL_ROOT  ?= $(abspath $(HERE)/../..)

# =============================================================================
# (2) ソースファイル
# =============================================================================
VERILOG_SOURCES := \
  $(HERE)/tb_riscv_iommu_wrapper.sv \
  $(shell find $(RTL_ROOT)/rtl    -name "*.sv" \
                                  -not -path "*/temp/*" \
                                  -not -name "copy_*") \
  $(shell find $(RTL_ROOT)/vendor -name "*.sv")

# =============================================================================
# (3) インクルードパス
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
# (4) Verilator フラグ
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

# ---- RTL カバレッジ (= make RTL_COVERAGE=1 sim でカバレッジ取得) ----
ifeq ($(RTL_COVERAGE),1)
  COMPILE_ARGS += --coverage
  COMPILE_ARGS += --coverage-line --coverage-toggle
endif

# =============================================================================
# (5) cocotb 設定
# =============================================================================
TOPLEVEL = tb_riscv_iommu_wrapper

MODULE ?= test_smoke,test_ptw_normal,test_ptw_fault,test_ptw_access,test_iotlb

export PYTHONPATH := $(HERE):$(HERE)/scenarios:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim

# =============================================================================
# (6) 補助ターゲット
# =============================================================================
smoke:
	@set -o pipefail; \
	$(MAKE) sim MODULE=test_smoke 2>&1 | tee $@.log; \
	EXIT_CODE=$$?; \
	mv dump.fst $@.fst 2>/dev/null || true; \
	mv dump.vcd $@.vcd 2>/dev/null || true; \
	exit $$EXIT_CODE

# -----------------------------------------------------------------------------
# replay tier 設定
# -----------------------------------------------------------------------------
GOLDEN_DIR    ?= $(HERE)/reference/gen_vectors
RTL_LOG_JSONL ?= $(HERE)/rtl_log.jsonl
DIFF_TOOL     ?= $(RTL_ROOT)/scripts/diff_logs.py

ALL_CATEGORIES       := phase1_pte_flags iova_variation s2_only nested \
                        nested_full nested_full_quick \
                        pc_phase1_pte_flags pc_iova_variation pc_s2_only \
                        pc_nested pc_nested_full pc_nested_full_quick \
                        pte_reserved_s1 pte_reserved_s2 pte_reserved_nested \
                        access_matrix_s1 access_matrix_s2 access_matrix_nested \
                        bare_mixed msi_translation

FULL_ONLY_CATEGORIES := nested_full pc_nested_full
QUICK_CATEGORIES     := $(filter-out $(FULL_ONLY_CATEGORIES),$(ALL_CATEGORIES))

QUICK_GOLDEN := $(addprefix $(GOLDEN_DIR)/golden_,$(addsuffix .jsonl,$(QUICK_CATEGORIES)))
FULL_GOLDEN  := $(addprefix $(GOLDEN_DIR)/golden_,$(addsuffix .jsonl,$(ALL_CATEGORIES)))

_quick_ref_args := $(addprefix --ref ,$(QUICK_GOLDEN))
_full_ref_args  := $(addprefix --ref ,$(FULL_GOLDEN))

# -----------------------------------------------------------------------------
# replay (= quick tier, default)
# -----------------------------------------------------------------------------
replay:
	$(MAKE) -C $(GOLDEN_DIR) run-quick
	@set -o pipefail; \
	GOLDEN_FILES="$(QUICK_GOLDEN)" RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	$(MAKE) sim MODULE=test_replay_golden 2>&1 | tee $@.log; \
	EXIT_CODE=$$?; \
	mv dump.fst $@.fst 2>/dev/null || true; \
	mv dump.vcd $@.vcd 2>/dev/null || true; \
	if [ $$EXIT_CODE -ne 0 ]; then exit $$EXIT_CODE; fi; \
	echo ""; echo "==== Diff RTL vs reference (QUICK tier) ===="; \
	python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) $(_quick_ref_args)

replay-full:
	$(MAKE) -C $(GOLDEN_DIR) run
	@set -o pipefail; \
	GOLDEN_FILES="$(FULL_GOLDEN)" RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	$(MAKE) sim MODULE=test_replay_golden 2>&1 | tee $@.log; \
	EXIT_CODE=$$?; \
	mv dump.fst $@.fst 2>/dev/null || true; \
	mv dump.vcd $@.vcd 2>/dev/null || true; \
	if [ $$EXIT_CODE -ne 0 ]; then exit $$EXIT_CODE; fi; \
	echo ""; echo "==== Diff RTL vs reference (FULL tier) ===="; \
	python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) $(_full_ref_args)

replay-fail-fast:
	$(MAKE) -C $(GOLDEN_DIR) run-quick
	GOLDEN_FILES="$(QUICK_GOLDEN)" RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	  $(MAKE) sim MODULE=test_replay_golden
	@python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) $(_quick_ref_args) --fail-fast

replay-category:
	@if [ -z "$(CAT)" ]; then echo "Usage: make replay-category CAT=<name>"; exit 1; fi
	$(MAKE) -C $(GOLDEN_DIR) run-$(CAT)
	GOLDEN_JSONL=$(GOLDEN_DIR)/golden_$(CAT).jsonl RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	  $(MAKE) sim MODULE=test_replay_golden
	@python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) \
	    --ref $(GOLDEN_DIR)/golden_$(CAT).jsonl --category $(CAT)

# -----------------------------------------------------------------------------
# golden_*.jsonl 生成
# -----------------------------------------------------------------------------
golden-vectors:
	$(MAKE) -C $(GOLDEN_DIR) run

golden-vectors-quick:
	$(MAKE) -C $(GOLDEN_DIR) run-quick

# -----------------------------------------------------------------------------
# モジュール単体テスト
# -----------------------------------------------------------------------------
ptw-normal:
	$(MAKE) sim MODULE=test_ptw_normal

ptw-fault:
	$(MAKE) sim MODULE=test_ptw_fault

ptw-access:
	$(MAKE) sim MODULE=test_ptw_access

iotlb:
	$(MAKE) sim MODULE=test_iotlb

one:
	$(MAKE) sim MODULE=$(MODULE) TESTCASE=$(TEST)

sim-log:
	$(MAKE) sim 2>&1 | tee sim.log

# -----------------------------------------------------------------------------
# Coverage / Wave 補助
# -----------------------------------------------------------------------------
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
	rm -f results.xml *.vcd *.fst *.log
	rm -rf coverage.info coverage_html

show-vars:
	@echo "==== Build / runtime ===="
	@echo "HERE                  = $(HERE)"
	@echo "RTL_ROOT              = $(RTL_ROOT)"
	@echo "TOPLEVEL              = $(TOPLEVEL)"
	@echo "MODULE                = $(MODULE)"
	@echo "PYTHONPATH            = $(PYTHONPATH)"
	@echo "RTL_COVERAGE          = $(RTL_COVERAGE)"
	@echo ""
	@echo "==== Wave configuration ===="
	@echo "WAVE_TRACE            = $(WAVE_TRACE)   (fst | vcd | none)"
	@echo "WAVE_SCOPE            = $(WAVE_SCOPE)   (cdw | full | none)"
	@echo ""
	@echo "==== Test tier configuration ===="
	@echo "ALL_CATEGORIES        = $(ALL_CATEGORIES)"
	@echo "FULL_ONLY_CATEGORIES  = $(FULL_ONLY_CATEGORIES)"
	@echo "QUICK_CATEGORIES      = $(QUICK_CATEGORIES)"
	@echo ""
	@echo "QUICK tier ($(words $(QUICK_GOLDEN)) files): make replay"
	@for f in $(QUICK_GOLDEN); do echo "  $$f"; done
	@echo ""
	@echo "FULL  tier ($(words $(FULL_GOLDEN)) files): make replay-full"
	@for f in $(FULL_GOLDEN); do echo "  $$f"; done

.PHONY: smoke replay replay-full replay-fail-fast replay-category \
        golden-vectors golden-vectors-quick \
        ptw-normal ptw-fault ptw-access iotlb one sim-log \
        find-waves wave-report wave-test wave-list wave-images wave-image \
        coverage-report show-vars