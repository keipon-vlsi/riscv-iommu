# 1. tw_sv39x4_pc.sv 全 pdt_gppn 関連を抽出
grep -n "pdt_gppn\|cdw_pdt_gppn" /workspace/rtl/translation_logic/wrapper/rv_iommu_tw_sv39x4_pc.sv

# 2. DDTW/PDTW での pdt_gppn 出力の駆動
grep -n "pdt_gppn_o\b" /workspace/rtl/translation_logic/cdw/rv_iommu_ddtw.sv
grep -n "pdt_gppn_o\b" /workspace/rtl/translation_logic/cdw/rv_iommu_pdtw.sv

# 3. translation_wrapper でも同様
grep -n "pdt_gppn" /workspace/rtl/translation_logic/wrapper/rv_iommu_translation_wrapper.sv