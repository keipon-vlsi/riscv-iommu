# =============================================================================
# Makefile for gen_vectors — drives ved-rivos/iommu-reference to enumerate
# Phase 1 test vectors for the cocotb testbench.
#
# 配置場所:  tb_coco/test/reference/gen_vectors/Makefile
#
# 前提:
#   - repo root に submodule として third_party/iommu-reference が置かれていること。
#   - libiommu / libtables を先にビルド済みであること。
#       cd third_party/iommu-reference
#       make -C libiommu
#       make -C libtables
#
# Docker/ホスト/CI のどこからでも動くよう、IOMMU_REF_DIR は __この Makefile からの
# 相対__ でデフォルトを解決する。明示的に上書きしたい場合は:
#       make IOMMU_REF_DIR=/abs/path/to/iommu_ref_model
# =============================================================================

HERE          := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
REPO_ROOT     := $(abspath $(HERE)/../../../..)

# riscv-non-isa/riscv-iommu repo はトップレベルにメタ情報を置き、
# 実際の C モデルは iommu_ref_model/ サブディレクトリにある:
#   third_party/iommu-reference/                ← submodule の clone 先
#     ├── iommu_ref_model/                       ← ここに libiommu/ libtables/ がある
#     │   ├── libiommu/   (libiommu.a)
#     │   └── libtables/  (libtables.a)
#     ├── src/  docs-resources/  ...             ← spec 側のリソース
#     └── ...
IOMMU_REF_DIR ?= $(REPO_ROOT)/third_party/iommu-reference/iommu_ref_model

CC      ?= gcc

# ---- libiommu / libtables は upstream の Makefile が --coverage 付きで
#      ビルドする (gcov 用 constructor/destructor が .a に埋まっている) ため、
#      gen_vectors 側でも常に --coverage を付けてリンクする必要がある。
#      これを付けないと __gcov_init / __gcov_exit / __gcov_merge_add の
#      undefined reference になる。
#
#      副作用として gen_vectors 自身も gcov 計測対象になり、実行時に .gcda が
#      出る — それは libiommu のカバレッジレポート (B) に取り込みたい情報なので
#      むしろ歓迎。
CFLAGS  := -O2 -g -Wall -Wno-error --coverage \
           -I$(IOMMU_REF_DIR)/libiommu/include \
           -I$(IOMMU_REF_DIR)/libtables/include
LDFLAGS := --coverage \
           -L$(IOMMU_REF_DIR)/libiommu \
           -L$(IOMMU_REF_DIR)/libtables
LDLIBS  := -liommu -ltables

# ---- B: 参照モデル (libiommu) のカバレッジ取得用フラグ ----
#  上記の通り --coverage は既定で入っているので COVERAGE=1 は実質 no-op。
#  upstream の libiommu/Makefile で --coverage を抜く構成にしたら、ここを
#  オプトイン側に移すこと。
ifeq ($(COVERAGE),1)
  # 何も追加しない (将来 upstream が変わったらここに --coverage を移す)
endif

TARGET  = gen_vectors
SRC     = gen_vectors.c
OBJ     = gen_vectors.o
JSONL   = golden_vectors.jsonl

.PHONY: all run clean show-vars

all: $(TARGET)

$(TARGET): $(OBJ)
	$(CC) -o $@ $^ $(LDFLAGS) $(LDLIBS)

$(OBJ): $(SRC)
	$(CC) $(CFLAGS) -c -o $@ $<

run: $(TARGET)
	./$(TARGET) > $(JSONL)
	@echo ""
	@echo "✓ wrote $$(wc -l < $(JSONL)) cases to $(JSONL)"
	@echo "  first line:"
	@head -n 1 $(JSONL)
	@echo "  last line:"
	@tail -n 1 $(JSONL)

# ---- 参照モデル側のカバレッジレポート ----
#  事前に make COVERAGE=1 で libiommu / libtables / gen_vectors を再ビルド &
#  ./gen_vectors を実行しておくこと。
coverage-report:
	lcov --capture --directory $(IOMMU_REF_DIR)/libiommu  \
	     --directory $(IOMMU_REF_DIR)/libtables          \
	     --directory $(HERE)                              \
	     --output-file libiommu_coverage.info
	genhtml libiommu_coverage.info --output-directory libiommu_coverage_html
	@echo ""
	@echo "✓ HTML report: $(HERE)/libiommu_coverage_html/index.html"

clean:
	rm -f $(TARGET) $(OBJ) $(JSONL)
	rm -f *.gcda *.gcno
	rm -rf libiommu_coverage.info libiommu_coverage_html

show-vars:
	@echo "HERE          = $(HERE)"
	@echo "REPO_ROOT     = $(REPO_ROOT)"
	@echo "IOMMU_REF_DIR = $(IOMMU_REF_DIR)"
	@echo "CC            = $(CC)"
	@echo "COVERAGE      = $(COVERAGE)"