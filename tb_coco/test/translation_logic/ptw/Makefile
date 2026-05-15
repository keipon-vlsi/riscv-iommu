# Makefile for PTW (rv_iommu_ptw_sv39x4_pc) unit verification — v4 compatible
#
# v4 changes:
#   - rv_iommu_ptw_sv39x4_pc が pt_walker + walk_ctrl の sub-module を持つように
#     なったので、 両者を VERILOG_SOURCES に追加
#   - rv_iommu_pkg.sv はそのまま使うが、 walk_ctrl が import rv_iommu::* するので必須

TOPLEVEL_LANG = verilog
SIM           = verilator

MAKEFILE_DIR  := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
REPO_ROOT     := $(realpath $(MAKEFILE_DIR)../../../..)

export PYTHONPATH := $(REPO_ROOT)

SCENARIO_FILES      := $(wildcard scenario/test_*.py)
MODULES_DOTS        := $(subst /,.,$(SCENARIO_FILES:.py=)) test_rv_iommu_ptw_sv39x4_pc
empty               :=
space               := $(empty) $(empty)
comma               := ,
export COCOTB_TEST_MODULES := $(subst $(space),$(comma),$(MODULES_DOTS))

EXTRA_ARGS += +incdir+$(REPO_ROOT)/packages/dependencies
EXTRA_ARGS += --trace --trace-structs
EXTRA_ARGS += -Wno-fatal

# ── v4 PTW は sub-module を 2 つ持つので、 全部明示的にリストする ──
VERILOG_SOURCES = \
    $(REPO_ROOT)/packages/dependencies/riscv_pkg.sv \
    $(REPO_ROOT)/packages/dependencies/axi_pkg.sv \
    $(REPO_ROOT)/packages/dependencies/lint_wrapper_pkg.sv \
    $(REPO_ROOT)/packages/rv_iommu/rv_iommu_pkg.sv \
    $(REPO_ROOT)/rtl/translation_logic/ptw/rv_iommu_pt_walker.sv \
    $(REPO_ROOT)/rtl/translation_logic/ptw/rv_iommu_walk_ctrl.sv \
    $(REPO_ROOT)/rtl/translation_logic/ptw/rv_iommu_ptw_sv39x4_pc.sv \
    $(MAKEFILE_DIR)tb_rv_iommu_ptw_sv39x4_pc_wrapper.sv

TOPLEVEL = tb_rv_iommu_ptw_sv39x4_pc_wrapper

include $(shell cocotb-config --makefiles)/Makefile.sim

sim-log:
	$(MAKE) sim 2>&1 | tee sim.log

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

debug-paths:
	@echo "MAKEFILE_DIR = $(MAKEFILE_DIR)"
	@echo "REPO_ROOT    = $(REPO_ROOT)"
	@echo "PYTHONPATH   = $(PYTHONPATH)"
	@echo "COCOTB_TEST_MODULES = $(COCOTB_TEST_MODULES)"
	