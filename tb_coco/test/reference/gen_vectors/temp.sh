cd /workspace/third_party/iommu-reference/iommu_ref_model/libtables
make clean && make

# libiommu も rebuild が必要
cd /workspace/third_party/iommu-reference/iommu_ref_model/libiommu
ls Makefile 2>/dev/null && make clean && make
# Makefile がなければ libtables の rebuild の中で自動で済んでいるか
# .o ファイルを直接消して再生成
rm -f src/iommu_second_stage_trans.o
# ↑ 該当 .o を消してから libtables make すると再 link される

# (4) gen_vectors も clean rebuild
cd /workspace/tb_coco/test/reference/gen_vectors
make clean && make run

# (5) replay
cd /workspace/tb_coco/test
rm -f rtl_log.jsonl
make replay 2>&1 > replay.log