# Makefile for PDTW (rv_iommu_pdtw) unit verification
# 配置先: /workspace/tb_coco/test/translation_logic/pdtw/Makefile

TOPLEVEL_LANG = verilog
SIM           = verilator

MAKEFILE_DIR  := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
REPO_ROOT     := $(realpath $(MAKEFILE_DIR)../../../..)

export PYTHONPATH := $(REPO_ROOT)

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
    $(REPO_ROOT)/packages/dependencies/lint_wrapper_pkg.sv \
    $(REPO_ROOT)/packages/rv_iommu/rv_iommu_pkg.sv \
    $(REPO_ROOT)/rtl/translation_logic/cdw/rv_iommu_pdtw.sv \
    $(MAKEFILE_DIR)tb_rv_iommu_pdtw_wrapper.sv

TOPLEVEL = tb_rv_iommu_pdtw_wrapper

include $(shell cocotb-config --makefiles)/Makefile.sim

sim-log:
	$(MAKE) sim 2>&1 | tee sim.log

clean::
	rm -rf sim_build __pycache__ scenario/__pycache__
	rm -f results.xml dump.vcd dump.fst sim.log *.log

debug-paths:
	@echo "MAKEFILE_DIR = $(MAKEFILE_DIR)"
	@echo "REPO_ROOT    = $(REPO_ROOT)"
	@echo "COCOTB_TEST_MODULES = $(COCOTB_TEST_MODULES)"
