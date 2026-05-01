"""test_ptw_normal.py — Phase 1: PTW 正常系テスト

DC = Sv39 1-stage (G=Bare) を共通にして、PTE の権限・サイズを変えていく。
書き方の雛形は test_template_normal を参照。
"""

import logging
import cocotb

from helpers import (
    IommuEnv,
    PTE_LEAF_RWX_AD, PTE_LEAF_R_AD, PTE_LEAF_RW_AD,
    PTE_V, PTE_R, PTE_W, PTE_X, PTE_U, PTE_A, PTE_D,
)


# =============================================================================
# test_13: 4K page を read (Phase 1 の動作確認用に test_10 を新 API で書き直し)
# =============================================================================
@cocotb.test(timeout_time=50, timeout_unit="us")
async def test_13_4k_read(dut):
    """4K mapping の read。inframigration の sanity-check 兼任。"""
    log = logging.getLogger("cocotb.tb")
    log.setLevel(logging.INFO)

    env = IommuEnv(dut)
    await env.setup()
    await env.install_dc_sv39_s1(did=0)

    iova   = 0x002_345
    sp_ppn = 0x100
    env.map_sv39_4k(iova, sp_ppn=sp_ppn)

    spa = (sp_ppn << 12) | (iova & 0xFFF)
    expected = 0xC0FFEE_BABE0123
    env.comp_ram.write(spa, expected.to_bytes(8, "little"))

    op = await env.dev_tr_read(iova, 8)
    got = int.from_bytes(op.data, "little")
    assert got == expected, f"got 0x{got:016x}"
    await env.fq.expect_no_record()


# ★ 以下、追加例 (まだ実装されていない) — 必要なものから書いてください ★
# @cocotb.test(timeout_time=50, timeout_unit="us")
# async def test_14_4k_write(dut):
#     env = IommuEnv(dut); await env.setup()
#     await env.install_dc_sv39_s1(did=0)
#     iova, sp_ppn = 0x002_345, 0x100
#     env.map_sv39_4k(iova, sp_ppn, perms=PTE_LEAF_RW_AD | PTE_X)
#     data = (0xDEADBEEF).to_bytes(8, "little")
#     await env.dev_tr_write(iova, data)
#     spa = (sp_ppn << 12) | (iova & 0xFFF)
#     readback = bytes(env.comp_ram.read(spa, 8))
#     assert readback == data
#     await env.fq.expect_no_record()
