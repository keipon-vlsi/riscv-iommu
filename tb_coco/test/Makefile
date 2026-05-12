# =============================================================================
# Makefile — riscv_iommu cocotb 統合テスト (v6)
#
# 配置場所:  tb_coco/test/Makefile
#
# v6 のポリシ:
#   - ターミナル出力: 最終 PASS / FAIL の 1 行だけ
#   - <target>.log : cocotb 出力 + golden vector 生成ログ + diff_logs.py の
#                    match / mismatch 詳細を全て格納
#   - <target>.fst : 波形 (FST 形式、 デフォルト)
#   - cocotb 2.0 の make sim が「テスト PASS でも non-zero exit」 する問題に対応
#     → make exit code ではなく log 中の "TESTS=N PASS=N FAIL=0" で PASS/FAIL 判定
#   - FST trace に必要な zlib を pkg-config / NIX_CFLAGS_COMPILE で自動検出
#
# Usage:
#   make smoke                           # 12 ケース / ~30 秒
#   make replay                          # quick tier / ~10-30 分
#   make replay-full                     # full tier / nightly CI
#   make replay-category CAT=s2_only     # 単一カテゴリ
#   make replay-fail-fast                # 最初の mismatch で停止
#
# Knobs:
#   WAVE_TRACE = fst | vcd | none        (default: fst)
#   WAVE_SCOPE = cdw | full | none       (default: cdw)
#   RTL_COVERAGE = 0 | 1                 (default: 0)
#
# 必要な nix package (= 一度だけ shell.nix に追加 or nix-shell -p で起動):
#   zlib pkg-config
# =============================================================================

SHELL := /bin/bash

# =============================================================================
# (1) Wave dump 制御
# =============================================================================
WAVE_TRACE ?= fst
WAVE_SCOPE ?= cdw

# cocotb 2.0 の WAVES=1 は --trace (VCD) を強制するので unexport
unexport WAVES

ifeq ($(WAVE_TRACE),fst)
  COMPILE_ARGS += --trace-fst
  COMPILE_ARGS += --trace-threads 1
  COMPILE_ARGS += --trace-depth 8
  COMPILE_ARGS += --trace-structs
  COMPILE_ARGS += --trace-max-array 64
  COMPILE_ARGS += +define+ENABLE_WAVE_DUMP

  # ---- FST trace の C++ ビルドには zlib.h が必要 ----
  # 検出優先順:
  #   1. pkg-config zlib    (= 一番きれい、 -I/-L が明示で得られる)
  #   2. NIX_CFLAGS_COMPILE (= nix-shell で zlib があれば -I が入っている)
  #   3. system default     (= /usr/include/zlib.h が居れば gcc は黙って拾う、 Docker や生 Ubuntu)
  # 1 と 2 で取れたら -CFLAGS で明示注入、 3 のみ取れたときは注入しない (= 黙ってシステム解決)
  ZLIB_CFLAGS := $(shell pkg-config --cflags zlib 2>/dev/null)
  ifeq ($(strip $(ZLIB_CFLAGS)),)
    ZLIB_CFLAGS := $(filter -I%,$(NIX_CFLAGS_COMPILE))
  endif
  ifneq ($(strip $(ZLIB_CFLAGS)),)
    COMPILE_ARGS += -CFLAGS "$(ZLIB_CFLAGS)"
  endif

  ZLIB_LIBS := $(shell pkg-config --libs zlib 2>/dev/null)
  ifeq ($(strip $(ZLIB_LIBS)),)
    ZLIB_LIBS := -lz
  endif
  COMPILE_ARGS += -LDFLAGS "$(ZLIB_LIBS)"

  # 警告は「 pkg-config / NIX_CFLAGS / system の全てで見つからない」 ときだけ出す
  _ZLIB_SYS := $(shell [ -f /usr/include/zlib.h ] && echo yes)
  ifeq ($(strip $(ZLIB_CFLAGS)),)
    ifneq ($(_ZLIB_SYS),yes)
      $(warning ⚠️  WAVE_TRACE=fst だが zlib が見つからない。 build が失敗する可能性あり。)
      $(warning   → nix-shell の buildInputs に "zlib pkg-config" を追加するか、)
      $(warning     apt-get install zlib1g-dev pkg-config 等で zlib.h を入れて下さい。)
    endif
  endif
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
# (2) Repo root を相対で確定
# =============================================================================
HERE      := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RTL_ROOT  ?= $(abspath $(HERE)/../..)

# =============================================================================
# (3) ソースファイル
# =============================================================================
VERILOG_SOURCES := \
  $(HERE)/tb_riscv_iommu_wrapper.sv \
  $(shell find $(RTL_ROOT)/rtl    -name "*.sv" \
                                  -not -path "*/temp/*" \
                                  -not -name "copy_*") \
  $(shell find $(RTL_ROOT)/vendor -name "*.sv")

# =============================================================================
# (4) インクルードパス
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
# (5) Verilator フラグ
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

ifeq ($(RTL_COVERAGE),1)
  COMPILE_ARGS += --coverage
  COMPILE_ARGS += --coverage-line --coverage-toggle
endif

# =============================================================================
# (6) cocotb 設定
# =============================================================================
TOPLEVEL = tb_riscv_iommu_wrapper

MODULE ?= test_smoke,test_ptw_normal,test_ptw_fault,test_ptw_access,test_iotlb

export PYTHONPATH := $(HERE):$(HERE)/scenarios:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim

# =============================================================================
# (7) replay tier 設定
# =============================================================================
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

# =============================================================================
# (8) smoke target  (= cocotb-only, diff なし)
# =============================================================================
smoke:
	@echo "Running smoke test... (log: $@.log, wave: $@.fst)"
	@rm -f $@.log $@.fst $@.vcd
	@$(MAKE) sim MODULE=test_smoke > $@.log 2>&1 || true
	@mv dump.fst $@.fst 2>/dev/null || true
	@mv dump.vcd $@.vcd 2>/dev/null || true
	@# cocotb 2.0 はサマリ行に ANSI color codes を埋め込む場合がある。
	@# "TESTS=N ... FAIL=0<非数字>" を寛容にマッチ (= color codes 越しでも OK)
	@if grep -qE 'TESTS=[0-9]+.*FAIL=0[^0-9]' $@.log; then \
	   echo "✅ smoke: PASS  (see $@.log)"; \
	 else \
	   echo "❌ smoke: FAIL  (see $@.log)"; \
	   echo "--- last 20 lines of $@.log ---"; tail -20 $@.log; \
	   exit 1; \
	 fi

# =============================================================================
# (9) replay target  (= QUICK tier, default)
# =============================================================================
replay:
	@echo "Running replay test (QUICK)... (log: $@.log, wave: $@.fst)"
	@rm -f $@.log $@.fst $@.vcd
	@printf "==== Golden vector generation (QUICK) ====\n" > $@.log
	@$(MAKE) -C $(GOLDEN_DIR) run-quick >> $@.log 2>&1 || \
	   { echo "❌ replay: golden vector generation FAILED  (see $@.log)"; exit 1; }
	@printf "\n==== cocotb sim ====\n" >> $@.log
	@GOLDEN_FILES="$(QUICK_GOLDEN)" RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	   $(MAKE) sim MODULE=test_replay_golden >> $@.log 2>&1 || true
	@mv dump.fst $@.fst 2>/dev/null || true
	@mv dump.vcd $@.vcd 2>/dev/null || true
	@if ! grep -qE 'TESTS=[0-9]+.*FAIL=0[^0-9]' $@.log; then \
	   echo "❌ replay: cocotb FAIL  (see $@.log)"; \
	   echo "--- last 30 lines of $@.log ---"; tail -30 $@.log; \
	   exit 1; \
	 fi
	@printf "\n==== Diff RTL vs reference (QUICK tier) ====\n" >> $@.log
	@python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) $(_quick_ref_args) \
	   >> $@.log 2>&1; \
	 DIFF_EXIT=$$?; \
	 if [ $$DIFF_EXIT -eq 0 ]; then \
	   echo "✅ replay: PASS  (see $@.log for match/mismatch detail)"; \
	 else \
	   echo "❌ replay: mismatch detected (diff exit=$$DIFF_EXIT, see $@.log)"; \
	   exit $$DIFF_EXIT; \
	 fi

# =============================================================================
# (10) replay-full target  (= FULL tier, nightly)
# =============================================================================
replay-full:
	@echo "Running replay test (FULL)... (log: $@.log, wave: $@.fst)"
	@rm -f $@.log $@.fst $@.vcd
	@printf "==== Golden vector generation (FULL) ====\n" > $@.log
	@$(MAKE) -C $(GOLDEN_DIR) run >> $@.log 2>&1 || \
	   { echo "❌ replay-full: golden vector generation FAILED  (see $@.log)"; exit 1; }
	@printf "\n==== cocotb sim ====\n" >> $@.log
	@GOLDEN_FILES="$(FULL_GOLDEN)" RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	   $(MAKE) sim MODULE=test_replay_golden >> $@.log 2>&1 || true
	@mv dump.fst $@.fst 2>/dev/null || true
	@mv dump.vcd $@.vcd 2>/dev/null || true
	@if ! grep -qE 'TESTS=[0-9]+.*FAIL=0[^0-9]' $@.log; then \
	   echo "❌ replay-full: cocotb FAIL  (see $@.log)"; \
	   echo "--- last 30 lines of $@.log ---"; tail -30 $@.log; \
	   exit 1; \
	 fi
	@printf "\n==== Diff RTL vs reference (FULL tier) ====\n" >> $@.log
	@python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) $(_full_ref_args) \
	   >> $@.log 2>&1; \
	 DIFF_EXIT=$$?; \
	 if [ $$DIFF_EXIT -eq 0 ]; then \
	   echo "✅ replay-full: PASS  (see $@.log for match/mismatch detail)"; \
	 else \
	   echo "❌ replay-full: mismatch detected (diff exit=$$DIFF_EXIT, see $@.log)"; \
	   exit $$DIFF_EXIT; \
	 fi

# =============================================================================
# (11) replay-fail-fast target  (= 最初の mismatch で停止)
# =============================================================================
replay-fail-fast:
	@echo "Running replay test (QUICK, fail-fast)... (log: $@.log, wave: $@.fst)"
	@rm -f $@.log $@.fst $@.vcd
	@printf "==== Golden vector generation (QUICK) ====\n" > $@.log
	@$(MAKE) -C $(GOLDEN_DIR) run-quick >> $@.log 2>&1 || \
	   { echo "❌ $@: golden vector generation FAILED  (see $@.log)"; exit 1; }
	@printf "\n==== cocotb sim ====\n" >> $@.log
	@GOLDEN_FILES="$(QUICK_GOLDEN)" RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	   $(MAKE) sim MODULE=test_replay_golden >> $@.log 2>&1 || true
	@mv dump.fst $@.fst 2>/dev/null || true
	@mv dump.vcd $@.vcd 2>/dev/null || true
	@if ! grep -qE 'TESTS=[0-9]+.*FAIL=0[^0-9]' $@.log; then \
	   echo "❌ $@: cocotb FAIL  (see $@.log)"; \
	   echo "--- last 30 lines of $@.log ---"; tail -30 $@.log; \
	   exit 1; \
	 fi
	@printf "\n==== Diff RTL vs reference (QUICK tier, fail-fast) ====\n" >> $@.log
	@python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) $(_quick_ref_args) --fail-fast \
	   >> $@.log 2>&1; \
	 DIFF_EXIT=$$?; \
	 if [ $$DIFF_EXIT -eq 0 ]; then \
	   echo "✅ $@: PASS  (see $@.log)"; \
	 else \
	   echo "❌ $@: first mismatch (diff exit=$$DIFF_EXIT, see $@.log)"; \
	   exit $$DIFF_EXIT; \
	 fi

# =============================================================================
# (12) replay-category target  (= 単一カテゴリ、 log: replay-<CAT>.log)
# =============================================================================
replay-category:
	@if [ -z "$(CAT)" ]; then echo "Usage: make replay-category CAT=<name>"; exit 1; fi
	@echo "Running replay test (CAT=$(CAT))... (log: replay-$(CAT).log, wave: replay-$(CAT).fst)"
	@rm -f replay-$(CAT).log replay-$(CAT).fst replay-$(CAT).vcd
	@printf "==== Golden vector generation ($(CAT)) ====\n" > replay-$(CAT).log
	@$(MAKE) -C $(GOLDEN_DIR) run-$(CAT) >> replay-$(CAT).log 2>&1 || \
	   { echo "❌ replay-$(CAT): golden vector generation FAILED  (see replay-$(CAT).log)"; exit 1; }
	@printf "\n==== cocotb sim ====\n" >> replay-$(CAT).log
	@GOLDEN_JSONL=$(GOLDEN_DIR)/golden_$(CAT).jsonl RTL_LOG_JSONL=$(RTL_LOG_JSONL) \
	   $(MAKE) sim MODULE=test_replay_golden >> replay-$(CAT).log 2>&1 || true
	@mv dump.fst replay-$(CAT).fst 2>/dev/null || true
	@mv dump.vcd replay-$(CAT).vcd 2>/dev/null || true
	@if ! grep -qE 'TESTS=[0-9]+.*FAIL=0[^0-9]' replay-$(CAT).log; then \
	   echo "❌ replay-$(CAT): cocotb FAIL  (see replay-$(CAT).log)"; \
	   echo "--- last 30 lines of replay-$(CAT).log ---"; tail -30 replay-$(CAT).log; \
	   exit 1; \
	 fi
	@printf "\n==== Diff RTL vs reference (CAT=$(CAT)) ====\n" >> replay-$(CAT).log
	@python3 $(DIFF_TOOL) --rtl $(RTL_LOG_JSONL) \
	    --ref $(GOLDEN_DIR)/golden_$(CAT).jsonl --category $(CAT) \
	   >> replay-$(CAT).log 2>&1; \
	 DIFF_EXIT=$$?; \
	 if [ $$DIFF_EXIT -eq 0 ]; then \
	   echo "✅ replay-$(CAT): PASS  (see replay-$(CAT).log)"; \
	 else \
	   echo "❌ replay-$(CAT): mismatch detected (diff exit=$$DIFF_EXIT, see replay-$(CAT).log)"; \
	   exit $$DIFF_EXIT; \
	 fi

# =============================================================================
# (13) golden_*.jsonl 生成 (= reference model から直接)
# =============================================================================
golden-vectors:
	@$(MAKE) -C $(GOLDEN_DIR) run

golden-vectors-quick:
	@$(MAKE) -C $(GOLDEN_DIR) run-quick

# =============================================================================
# (14) モジュール単体テスト (= 補助、 出力ポリシは silent ではない)
# =============================================================================
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

# =============================================================================
# (15) Coverage / Wave 補助
# =============================================================================
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

# =============================================================================
# (16) clean / show-vars
# =============================================================================
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
	@echo "ZLIB_CFLAGS           = $(ZLIB_CFLAGS)"
	@echo "ZLIB_LIBS             = $(ZLIB_LIBS)"
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