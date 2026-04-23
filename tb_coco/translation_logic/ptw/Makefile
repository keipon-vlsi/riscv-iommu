# Makefile
TOPLEVEL_LANG = verilog
# シミュレータを明示的に指定
SIM = verilator

# このMakefileが置かれているディレクトリ
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
# リポジトリルート (tb_coco/translation_logic/ptw/ の3階層上)
REPO_ROOT    := $(realpath $(MAKEFILE_DIR)../../..)
# cocotb venv (tb_coco/venv/ — Makefileの2階層上)
VENV_DIR     := $(realpath $(MAKEFILE_DIR)../../venv)
# venv/bin を PATH に追加して cocotb-config を Makefile.sim から見つけられるようにする
export PATH  := $(VENV_DIR)/bin:$(PATH)

# 1. scenarioフォルダ内の test_*.py を全て取得
SCENARIO_FILES := $(wildcard scenario/test_*.py)

# 2. "scenario/test_a.py" を "scenario.test_a" に変換
MODULES_DOTS := $(subst /,.,$(SCENARIO_FILES:.py=))

# 3. スペース区切りをカンマ区切りに変換
empty :=
space := $(empty) $(empty)
comma := ,
export COCOTB_TEST_MODULES := $(subst $(space),$(comma),$(MODULES_DOTS))

# ==========================================
# Verilator用のコンパイルオプション
# ==========================================
# 1. Includeディレクトリの指定 (-I を使用)
EXTRA_ARGS += -I$(REPO_ROOT)/packages/dependencies

# 2. 波形出力(VCD)と、構造体の中身を波形にダンプするオプション
EXTRA_ARGS += --trace --trace-structs

# 3. lint（文法チェック）の警告を一部無視する（RTL由来の警告で止まらないようにするため）
EXTRA_ARGS += -Wno-fatal

# ==========================================
# コンパイル対象ファイル (順番はパッケージが先！)
# ==========================================
VERILOG_SOURCES = \
    $(REPO_ROOT)/packages/dependencies/riscv_pkg.sv \
    $(REPO_ROOT)/packages/dependencies/axi_pkg.sv \
    $(REPO_ROOT)/packages/rv_iommu/rv_iommu_pkg.sv \
    $(REPO_ROOT)/rtl/translation_logic/ptw/rv_iommu_ptw_sv39x4_pc.sv \
    $(MAKEFILE_DIR)/tb_ptw_wrapper.sv

TOPLEVEL = tb_ptw_wrapper
# MODULE = scenario/*

include $(shell cocotb-config --makefiles)/Makefile.sim