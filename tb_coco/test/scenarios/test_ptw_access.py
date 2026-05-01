"""test_ptw_access.py — Phase 3: AXI アクセスフォルト系

PT 読み出しで AXI が SLVERR/DECERR を返した時に、IOMMU が
LOAD_ACCESS_FAULT (cause=5) を上げるかを確認。

cocotbext-axi の AxiRam は region_lookup で特定アドレス範囲を
SLVERR エリアに指定できる。これを使って leaf PT のページを
"読むと SLVERR を返す穴" にする。
"""

import logging
import cocotb

from helpers import (
    IommuEnv,
    PTE_LEAF_RWX_AD,
    CAUSE_LOAD_ACCESS_FAULT,
    TTYP_UNTRANSLATED_RD,
)


# =============================================================================
# test_30: leaf PT を SLVERR 領域に置く
# =============================================================================
# ★ skeleton — region_lookup の API は cocotbext-axi の version で
#   揺れるので、最初に手動確認してから生かしてください。
# =============================================================================
# @cocotb.test(timeout_time=50, timeout_unit="us")
# async def test_30_leaf_pt_slverr(dut):
#     env = IommuEnv(dut); await env.setup()
#     await env.install_dc_sv39_s1(did=0)
#
#     iova = 0x002_345
#     env.map_sv39_4k(iova, sp_ppn=0x100, perms=PTE_LEAF_RWX_AD)
#
#     # leaf PT が置かれているページを SLVERR エリアに登録
#     leaf_pt_start = env.s1_leaf_ppn << 12
#     env.ds_ram.read_if.region_lookup.add(
#         start=leaf_pt_start,
#         end  =leaf_pt_start + 4096,
#         resp =0b10,                       # SLVERR
#     )
#
#     await env.expect_fault_on_read(iova, cause=CAUSE_LOAD_ACCESS_FAULT,
#                                      ttyp=TTYP_UNTRANSLATED_RD)
