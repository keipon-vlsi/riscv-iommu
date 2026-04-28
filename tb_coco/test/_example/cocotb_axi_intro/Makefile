# =============================================================================
# Makefile — cocotbext-axi 入門サンプル
#
# 使い方:
#   make           # シミュレーション実行 + dump.vcd 生成
#   make sim-log   # 実行 + ログを sim.log に保存
#   make wave      # GTKWave で波形を開く
#   make clean     # ビルド成果物削除
# =============================================================================

# ---- 波形ダンプを有効化 ----
# ★ Makefile.verilator:44 ifeq ($(VERILATOR_TRACE),1) で --trace --trace-structs が
#   COMPILE_ARGS / SIM_ARGS に追加される。
#   `?=` だと cocotb 側で空文字が先に入るのか効かない。`:=` で強制上書き。
#   無効化したい場合は `make VERILATOR_TRACE=0 ...` でオーバーライド可。
VERILATOR_TRACE := 1
export VERILATOR_TRACE

TOPLEVEL_LANG = verilog
SIM           ?= verilator      # icarus に変えれば iverilog で実行可

# ---- RTL ソース ----
VERILOG_SOURCES = $(PWD)/simple_axil_ram.sv

# ---- トップモジュール (RTL) と Python テスト module 名 ----
TOPLEVEL = simple_axil_ram
MODULE   = test_simple_axil_ram

# ---- Icarus 用オプション ----
ifeq ($(SIM),icarus)
    COMPILE_ARGS += -DCOCOTB_SIM
endif

# ---- cocotb 共通 Makefile を include (sim ターゲットを取り込む) ----
include $(shell cocotb-config --makefiles)/Makefile.sim

# ---- ログ保存 ----
sim-log:
	$(MAKE) sim 2>&1 | tee sim.log

# ---- 波形を GTKWave で開く ----
# ★ Verilator は sim_build/ で実行されるため、$dumpfile("dump.vcd") の出力先は
#    sim_build/dump.vcd になる。両方のパスを探す。
WAVE_CANDIDATES = sim_build/dump.vcd sim_build/dump.fst dump.vcd dump.fst

wave:
	@for f in $(WAVE_CANDIDATES); do \
		if [ -f $$f ]; then \
			echo "Opening $$f in GTKWave..."; \
			gtkwave $$f & \
			exit 0; \
		fi; \
	done; \
	echo "✗ 波形ファイルが見つかりません。先に 'make' を実行してください。"; \
	echo "  探した場所: $(WAVE_CANDIDATES)"; \
	echo "  実際にあるファイル:"; \
	find . -name "*.vcd" -o -name "*.fst" 2>/dev/null | sed 's/^/    /'; \
	exit 1

# 波形がどこに出ているか調べる用
find-waves:
	@echo "VCD/FST ファイル一覧:"
	@find . \( -name "*.vcd" -o -name "*.fst" \) -print 2>/dev/null

# ---- 完全クリーン (cocotb の clean に追記) ----
clean::
	rm -rf sim_build __pycache__
	rm -f  results.xml dump.vcd dump.fst sim.log
	@echo "✓ cleaned"

# ---- デバッグ: パスや変数の確認 ----
# ★ 注意: `debug` という名前は Verilator の Makefile.sim が既に使っているため
#         衝突する。ここでは `show-vars` にリネームしてある。
show-vars:
	@echo "SIM             = $(SIM)"
	@echo "TOPLEVEL        = $(TOPLEVEL)"
	@echo "MODULE          = $(MODULE)"
	@echo "VERILOG_SOURCES = $(VERILOG_SOURCES)"
	@echo "VERILATOR_TRACE = $(VERILATOR_TRACE)"
	@echo "COMPILE_ARGS    = $(COMPILE_ARGS)"
	@echo "EXTRA_ARGS      = $(EXTRA_ARGS)"
	@which cocotb-config
	@cocotb-config --version