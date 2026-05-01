"""test_ptw_fault.py — Phase 2: PTW ページフォルト

leaf PTE を意図的に壊して、IOMMU が正しい cause で fault を上げるかを確認。
共通骨格はどれも同じなので、コピペで増やしやすい。
"""

import logging
import cocotb

from helpers import (
    IommuEnv,
    PTE_V, PTE_R, PTE_W, PTE_X, PTE_U, PTE_A, PTE_D,
    PTE_LEAF_RWX_AD, PTE_LEAF_R_AD,
    CAUSE_LOAD_PAGE_FAULT, CAUSE_STORE_PAGE_FAULT,
    TTYP_UNTRANSLATED_RD, TTYP_UNTRANSLATED_WR,
)


# =============================================================================
# test_20: 最小フォルトケース — leaf PTE.V=0
# =============================================================================
@cocotb.test(timeout_time=50, timeout_unit="us")
async def test_20_pte_invalid(dut):
    """leaf PTE の V=0 で LOAD_PAGE_FAULT (cause=13)。"""
    log = logging.getLogger("cocotb.tb")
    log.setLevel(logging.INFO)

    env = IommuEnv(dut)
    await env.setup()
    await env.install_dc_sv39_s1(did=0)

    iova = 0x002_345
    env.map_sv39_4k(iova, sp_ppn=0x100, perms=0)   # V=0

    rec = await env.expect_fault_on_read(
        iova,
        cause=CAUSE_LOAD_PAGE_FAULT,
        ttyp=TTYP_UNTRANSLATED_RD,        # = 2 (普通の load) — spec table 14
        # iotval は env が iova を auto-fill する (spec §4.2 通り)
        did=0,
    )
    log.info(f"  ✓ {rec}")


# =============================================================================
# test_21 以降のテンプレ (コメントアウト — 必要なものから外して使う)
# =============================================================================
# @cocotb.test(timeout_time=50, timeout_unit="us")
# async def test_21_pte_w_without_r(dut):
#     """W=1, R=0 は reserved encoding → LOAD_PAGE_FAULT。"""
#     env = IommuEnv(dut); await env.setup()
#     await env.install_dc_sv39_s1(did=0)
#     iova = 0x002_345
#     env.map_sv39_4k(iova, sp_ppn=0x100,
#                     perms=PTE_V | PTE_W | PTE_U | PTE_A | PTE_D)
#     await env.expect_fault_on_read(iova, cause=CAUSE_LOAD_PAGE_FAULT)
#
# @cocotb.test(timeout_time=50, timeout_unit="us")
# async def test_22_misaligned_2m(dut):
#     """2M leaf で PPN 下位 9 bit 非ゼロ → LOAD_PAGE_FAULT。"""
#     env = IommuEnv(dut); await env.setup()
#     await env.install_dc_sv39_s1(did=0)
#     iova = 0x123_456
#     env.map_sv39_2m(iova, sp_ppn=0x201)              # 2M aligned でない
#     await env.expect_fault_on_read(iova, cause=CAUSE_LOAD_PAGE_FAULT)
#
# @cocotb.test(timeout_time=50, timeout_unit="us")
# async def test_23_perm_deny_write(dut):
#     """R-only PTE に store して STORE_PAGE_FAULT。"""
#     env = IommuEnv(dut); await env.setup()
#     await env.install_dc_sv39_s1(did=0)
#     iova = 0x002_345
#     env.map_sv39_4k(iova, sp_ppn=0x100, perms=PTE_LEAF_R_AD)
#     await env.expect_fault_on_write(iova, b"\xff" * 8,
#                                       cause=CAUSE_STORE_PAGE_FAULT,
#                                       ttyp=TTYP_UNTRANSLATED_WR)