"""test_iotlb.py — Phase 4: IOTLB / IOTINVAL.VMA

IOMMU のキャッシュ (DDTC / IOTLB) と Command Queue 経由の
無効化コマンドの動作確認。
"""

import logging
import cocotb

from helpers import (
    IommuEnv,
    PTE_LEAF_RWX_AD,
)


# =============================================================================
# test_40: 同じ IOVA 2 回 → 2 回目は IOTLB hit
# =============================================================================
# @cocotb.test(timeout_time=50, timeout_unit="us")
# async def test_40_iotlb_hit(dut):
#     env = IommuEnv(dut); await env.setup()
#     await env.install_dc_sv39_s1(did=0)
#
#     iova, sp_ppn = 0x002_345, 0x100
#     env.map_sv39_4k(iova, sp_ppn=sp_ppn)
#     spa = (sp_ppn << 12) | (iova & 0xFFF)
#     env.comp_ram.write(spa, b"\x01" * 8)
#
#     # 1 回目: PTW 走る
#     op1 = await env.dev_tr_read(iova, 8)
#     # 2 回目: IOTLB hit (ds_arvalid が立たないことは波形で確認)
#     op2 = await env.dev_tr_read(iova, 8)
#     assert op1.data == op2.data
#     await env.fq.expect_no_record()


# =============================================================================
# test_41: IOTINVAL.VMA で IOTLB を flush → 2 回目は再 walk
# =============================================================================
# @cocotb.test(timeout_time=200, timeout_unit="us")
# async def test_41_iotinval_vma(dut):
#     env = IommuEnv(dut)
#     await env.setup(enable_cq=True)            # CQ も有効化
#     await env.install_dc_sv39_s1(did=0)
#
#     iova, sp_ppn = 0x002_345, 0x100
#     env.map_sv39_4k(iova, sp_ppn=sp_ppn)
#     env.comp_ram.write((sp_ppn << 12) | (iova & 0xFFF), b"\xaa" * 8)
#
#     # 1 回目 (PTW)
#     await env.dev_tr_read(iova, 8)
#
#     # IOTLB を invalidate
#     await env.cq.iotinval_vma(addr=iova, av=True)
#
#     # 2 回目: 再 PTW されるはず (波形で 4 ARVALID 観測)
#     await env.dev_tr_read(iova, 8)
#     await env.fq.expect_no_record()
