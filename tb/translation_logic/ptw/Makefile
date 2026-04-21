# Makefile
TOPLEVEL_LANG = verilog
# シミュレータを明示的に指定
SIM = verilator

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
EXTRA_ARGS += -I/Users/keipon/Desktop/project/tt_pretraining/riscv-iommu-kawano/packages/dependencies

# 2. 波形出力(VCD)と、構造体の中身を波形にダンプするオプション
EXTRA_ARGS += --trace --trace-structs

# 3. lint（文法チェック）の警告を一部無視する（RTL由来の警告で止まらないようにするため）
EXTRA_ARGS += -Wno-fatal

# ==========================================
# コンパイル対象ファイル (順番はパッケージが先！)
# ==========================================
VERILOG_SOURCES = \
    /Users/keipon/Desktop/project/tt_pretraining/riscv-iommu-kawano/packages/dependencies/riscv_pkg.sv \
	/Users/keipon/Desktop/project/tt_pretraining/riscv-iommu-kawano/packages/dependencies/axi_pkg.sv \
    /Users/keipon/Desktop/project/tt_pretraining/riscv-iommu-kawano/packages/rv_iommu/rv_iommu_pkg.sv \
    /Users/keipon/Desktop/project/tt_pretraining/riscv-iommu-kawano/rtl/translation_logic/ptw/rv_iommu_ptw_sv39x4_pc.sv \
    $(PWD)/tb_ptw_wrapper.sv 

TOPLEVEL = tb_ptw_wrapper
# MODULE = scenario/*

include $(shell cocotb-config --makefiles)/Makefile.sim