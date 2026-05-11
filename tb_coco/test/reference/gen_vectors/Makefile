# =============================================================================
# Makefile for gen_vectors — マルチカテゴリビルド + tier 別 run target
#
# Tier 概念:
#   - quick tier : 日中の iter で頻繁に走らせるケース群 (~10 分以内)
#   - full tier  : nightly CI / release 前に走らせる徹底版 (~1 時間)
#
#   ALL_CATEGORIES から FULL_ONLY_CATEGORIES を引いたものが quick tier。
#   FULL_ONLY_CATEGORIES に分類するのは「ケース数が大きすぎて日中に流せない」もの。
#
# 新カテゴリを足すときは:
#   1. gen_<NEW>.c を作る (header コメントで可変軸/固定軸を明記)
#   2. ALL_CATEGORIES に <NEW> を追加
#   3. ケース数が ~12,000 以下なら quick tier にも自動で入る (= 何もしない)
#   4. ケース数が ~12,000 を超える場合:
#      a. <NEW> を FULL_ONLY_CATEGORIES に追加
#      b. gen_<NEW>_quick.c を別途作って、そちらは ALL_CATEGORIES に入れる
# =============================================================================

HERE          := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
REPO_ROOT     := $(abspath $(HERE)/../../../..)
IOMMU_REF_DIR ?= $(REPO_ROOT)/third_party/iommu-reference/iommu_ref_model

CC      ?= gcc

CFLAGS  := -O2 -g -Wall -Wno-error --coverage \
           -I$(HERE) \
           -I$(IOMMU_REF_DIR)/libiommu/include \
           -I$(IOMMU_REF_DIR)/libtables/include
LDFLAGS := --coverage
LDLIBS  := $(IOMMU_REF_DIR)/libiommu/libiommu.a \
            $(IOMMU_REF_DIR)/libtables/libtables.a

# =============================================================================
# カテゴリ定義 — 全カテゴリ + full tier 専用カテゴリ
# =============================================================================
ALL_CATEGORIES       := phase1_pte_flags iova_variation s2_only nested \
                        nested_full nested_full_quick \
                        pc_phase1_pte_flags pc_iova_variation pc_s2_only pc_nested \
                        pc_nested_full pc_nested_full_quick
ALL_CATEGORIES += pte_reserved_s1 pte_reserved_s2 pte_reserved_nested
ALL_CATEGORIES += access_matrix_s1 access_matrix_s2 access_matrix_nested
ALL_CATEGORIES += bare_mixed
ALL_CATEGORIES += msi_translation

# Full tier だけで走らせる (= ケース数が大きすぎて quick tier に含めないもの)
FULL_ONLY_CATEGORIES := nested_full pc_nested_full

# Quick tier = 全部 - Full only
QUICK_CATEGORIES := $(filter-out $(FULL_ONLY_CATEGORIES),$(ALL_CATEGORIES))

# 各カテゴリの実行ファイル名 / 出力 JSONL 名
ALL_EXECS    := $(addprefix gen_,$(ALL_CATEGORIES))
ALL_JSONLS   := $(addprefix golden_,$(addsuffix .jsonl,$(ALL_CATEGORIES)))
QUICK_JSONLS := $(addprefix golden_,$(addsuffix .jsonl,$(QUICK_CATEGORIES)))

# 共通オブジェクト
COMMON_OBJ := gen_common.o

# =============================================================================
# ターゲット
# =============================================================================
.PHONY: all run run-quick clean show-vars $(addprefix run-,$(ALL_CATEGORIES))

all: $(ALL_EXECS)

# Full tier (= 全カテゴリ) — make replay-full から呼ばれる
run: $(ALL_JSONLS)

# Quick tier (= ケース数の小さいもの + nested_full_quick) — make replay から呼ばれる
run-quick: $(QUICK_JSONLS)

# 個別カテゴリ実行: make run-iova_variation など
$(addprefix run-,$(ALL_CATEGORIES)): run-%: golden_%.jsonl
	@echo "✓ $< ready"

# 共通オブジェクトのコンパイル
$(COMMON_OBJ): gen_common.c gen_common.h
	$(CC) $(CFLAGS) -c -o $@ $<

# 各実行ファイルのリンク
gen_%: gen_%.c $(COMMON_OBJ) gen_common.h
	$(CC) $(CFLAGS) -o $@ $< $(COMMON_OBJ) $(LDFLAGS) $(LDLIBS)

# 各 JSONL の生成
golden_%.jsonl: gen_%
	./$< > $@
	@echo "  ✓ $@ ($$(wc -l < $@) cases)"

# =============================================================================
# 補助
# =============================================================================
coverage-report:
	lcov --capture \
	     --directory $(IOMMU_REF_DIR)/libiommu \
	     --directory $(IOMMU_REF_DIR)/libtables \
	     --directory $(HERE) \
	     --output-file libiommu_coverage.info
	genhtml libiommu_coverage.info --output-directory libiommu_coverage_html
	@echo ""
	@echo "✓ HTML report: $(HERE)/libiommu_coverage_html/index.html"

clean:
	rm -f $(ALL_EXECS) $(COMMON_OBJ) $(ALL_JSONLS) *.gcda *.gcno
	rm -rf libiommu_coverage.info libiommu_coverage_html
	rm -f gen_vectors gen_vectors.o golden_vectors.jsonl

show-vars:
	@echo "HERE                  = $(HERE)"
	@echo "REPO_ROOT             = $(REPO_ROOT)"
	@echo "IOMMU_REF_DIR         = $(IOMMU_REF_DIR)"
	@echo "ALL_CATEGORIES        = $(ALL_CATEGORIES)"
	@echo "FULL_ONLY_CATEGORIES  = $(FULL_ONLY_CATEGORIES)"
	@echo "QUICK_CATEGORIES      = $(QUICK_CATEGORIES)"