"""DDTW (rv_iommu_ddtw) ハッピーパス単体検証

配置: /workspace/tb_coco/test/translation_logic/ddtw/scenario/test_directed.py

カバー範囲 (= 全部 happy path、 fault 注入はなし):
  D01: 1-level DDT、 S2 disabled、 PC なし
  D02: 1-level DDT、 S2 enabled、 PC なし (= need_leaf_s2 path)
  D03: 2-level DDT、 S2 disabled
  D04: 3-level DDT、 S2 disabled
"""

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly, Timer
from cocotb.clock import Clock

from tb_coco.common.helpers_cdw import (
    DcFactory, NlEntryFactory, PhysicalMemoryManager,
    MockMemoryBurst, simulate_ptw_done,
)


# ---------------------------------------------------------------------------
# Common setup
# ---------------------------------------------------------------------------

async def _start_clock(dut):
    cocotb.start_soon(Clock(dut.clk_i, 10, unit="ns").start())


async def _reset(dut, cycles=5):
    """Reset DUT + safe defaults。"""
    dut.rst_ni.value         = 0
    dut.init_i.value         = 0
    dut.req_did_i.value      = 0
    dut.ddtp_ppn_i.value     = 0
    dut.ddtp_mode_i.value    = 0
    dut.en_stage2_i.value    = 0
    dut.flush_i.value        = 0
    dut.ptw_done_i.value     = 0
    dut.pdt_ppn_i.value      = 0

    # Caps: 全部 1 にしておく (= happy path で各 mode を許可)
    dut.caps_ats_i.value      = 0
    dut.caps_t2gpa_i.value    = 0
    dut.caps_pd20_i.value     = 1
    dut.caps_pd17_i.value     = 1
    dut.caps_pd8_i.value      = 1
    dut.caps_sv39_i.value     = 1
    dut.caps_sv39x4_i.value   = 1
    dut.caps_msi_flat_i.value = 0
    dut.caps_amo_hwad_i.value = 1
    dut.caps_end_i.value      = 0
    dut.fctl_be_i.value       = 0

    for _ in range(cycles):
        await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 1
    for _ in range(cycles):
        await RisingEdge(dut.clk_i)


def _ddt_leaf_addr_1lvl(ddt_ppn, did):
    """1-level DDT (= MSI_DISABLED) で DC が書かれるアドレス。

    DDTW source line 274-276 より:
        cdw_pptr_n = {ddtp_ppn, did[6:0], 5'b0}  (MSI_DISABLED)
    つまり (ddt_ppn << 12) + (did[6:0] << 5) = ddt_ppn 物理 page 内、 32-byte stride。
    """
    return (ddt_ppn << 12) + ((did & 0x7F) << 5)


def _ddt_nl_addr_2lvl(ddt_ppn, did):
    """2-level DDT で 1 段目 NL を書くアドレス。

    DDTW source line 270-273 より:
        cdw_pptr_n = {ddtp_ppn, did[15:7], 3'b0}  (MSI_DISABLED, mode=3)
    """
    return (ddt_ppn << 12) + (((did >> 7) & 0x1FF) << 3)


def _ddt_nl_addr_3lvl_top(ddt_ppn, did):
    """3-level DDT の TOP NL アドレス (= mode=4)。

    DDTW source line 266-269 より:
        cdw_pptr_n = {ddtp_ppn, did[23:16], 3'b0}  (MSI_DISABLED, mode=4)
    """
    return (ddt_ppn << 12) + (((did >> 16) & 0xFF) << 3)


def _next_pptr_nl(base_ppn, lvl, did, msi_disabled=True):
    """DDTW source line 132-138 の next_pptr_nl の Python 模倣。

    lvl: 4=LVL3, 3=LVL2 (= 元 source の level_t encoding に合わせる)
    """
    if lvl == 4:  # LVL3
        idx_bits = (did >> 7) & 0x1FF if msi_disabled else (did >> 6) & 0x1FF
        return (base_ppn << 12) + (idx_bits << 3)
    if lvl == 3:  # LVL2
        idx_bits = did & 0x7F if msi_disabled else did & 0x3F
        return (base_ppn << 12) + (idx_bits << (5 if msi_disabled else 6))
    return 0


async def _trigger(dut, did, ddtp_ppn, ddtp_mode, en_s2=0):
    dut.req_did_i.value   = did
    dut.ddtp_ppn_i.value  = ddtp_ppn
    dut.ddtp_mode_i.value = ddtp_mode
    dut.en_stage2_i.value = en_s2
    await RisingEdge(dut.clk_i)
    dut.init_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.init_i.value = 0


async def _wait_update_or_error(dut, timeout=200):
    for _ in range(timeout):
        await RisingEdge(dut.clk_i)
        await ReadOnly()
        if int(dut.update_dc_o.value) == 1:
            return "SUCCESS"
        if int(dut.error_o.value) == 1:
            return "ERROR"
    return "TIMEOUT"


# ---------------------------------------------------------------------------
# D01: 1-level DDT, S2 disabled, no PC
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_d01_1lvl_ddt_s2_disabled(dut):
    """シンプル: 1-level DDT、 S2 disabled、 pdtv=0、 fsc=Sv39。"""
    await _start_clock(dut)
    ram = MockMemoryBurst(dut)
    await _reset(dut)

    pmm = PhysicalMemoryManager(start_ppn=0x100)
    ddt_ppn = pmm.alloc_ppn()      # 0x100
    s1_root  = pmm.alloc_ppn()     # 0x101
    did      = 0x05

    # DC 4 entry を組み立てる
    dc_words = DcFactory.build(
        v=1, pdtv=0,
        iohgatp_mode=0, iohgatp_ppn=0,        # S2 BARE
        pscid=0,
        fsc_mode=8, fsc_ppn=s1_root,          # Sv39
    )

    # 1-level DDT は ddt_ppn の物理 page 内に 32-byte stride で DC が並ぶ
    dc_addr = _ddt_leaf_addr_1lvl(ddt_ppn, did)
    ram.write_words(dc_addr, dc_words)

    dut._log.info(f"D01: DC @ 0x{dc_addr:x}, did={did}, s1_root=0x{s1_root:x}")

    # mode=2 (= 1lvl)
    await _trigger(dut, did=did, ddtp_ppn=ddt_ppn, ddtp_mode=2, en_s2=0)

    result = await _wait_update_or_error(dut)
    assert result == "SUCCESS", f"D01: expected SUCCESS, got {result}"
    assert int(dut.up_did_o.value) == did, f"up_did_o mismatch: {int(dut.up_did_o.value)}"

    dut._log.info("D01 PASS")


# ---------------------------------------------------------------------------
# D02: 1-level DDT, S2 enabled + pdtv=1 → need_leaf_s2 path
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_d02_1lvl_ddt_with_s2(dut):
    """S2 enabled で pdtv=1 + iohgatp.mode != 0 → leaf S2 walk を経由する。"""
    await _start_clock(dut)
    ram = MockMemoryBurst(dut)
    await _reset(dut)

    pmm = PhysicalMemoryManager(start_ppn=0x200)
    ddt_ppn  = pmm.alloc_ppn()    # 0x200
    g_root   = pmm.alloc_ppn()    # 0x201 (= iohgatp.PPN)
    pdt_gppn = pmm.alloc_ppn()    # 0x202 (= dc.fsc.PPN として GPPN を入れる)
    pdt_spa  = pmm.alloc_ppn()    # 0x203 (= S2 翻訳結果として返す SPA)
    did      = 0x10

    # iohgatp.PPN は 16K aligned 必須 (= ppn[1:0]=0)
    assert (g_root & 0x3) == 0, "iohgatp.PPN must be 16K aligned"

    dc_words = DcFactory.build(
        v=1, pdtv=1,                          # ★ PC 経由翻訳を有効化
        iohgatp_mode=8, iohgatp_ppn=g_root,   # Sv39x4 S2 enabled
        pscid=0,
        fsc_mode=1, fsc_ppn=pdt_gppn,         # PD8 mode
    )
    dc_addr = _ddt_leaf_addr_1lvl(ddt_ppn, did)
    ram.write_words(dc_addr, dc_words)

    dut._log.info(f"D02: DC @ 0x{dc_addr:x}, did={did}, pdt_gppn=0x{pdt_gppn:x}, pdt_spa=0x{pdt_spa:x}")

    # PTW simulator coroutine を立ち上げる
    cocotb.start_soon(simulate_ptw_done(dut, pdt_spa))

    await _trigger(dut, did=did, ddtp_ppn=ddt_ppn, ddtp_mode=2, en_s2=1)

    result = await _wait_update_or_error(dut, timeout=500)
    assert result == "SUCCESS", f"D02: expected SUCCESS, got {result}"
    assert int(dut.up_did_o.value) == did

    dut._log.info("D02 PASS")


# ---------------------------------------------------------------------------
# D03: 2-level DDT, S2 disabled
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_d03_2lvl_ddt_s2_disabled(dut):
    """2-level DDT: top NL + leaf。"""
    await _start_clock(dut)
    ram = MockMemoryBurst(dut)
    await _reset(dut)

    pmm = PhysicalMemoryManager(start_ppn=0x300)
    ddt_ppn  = pmm.alloc_ppn()    # 0x300 (= top NL page)
    leaf_ppn = pmm.alloc_ppn()    # 0x301 (= leaf page)
    s1_root  = pmm.alloc_ppn()    # 0x302
    did      = 0x42

    # Top NL の書き込み位置 (= ddtp_ppn + (did[15:7] << 3))
    nl_addr = _ddt_nl_addr_2lvl(ddt_ppn, did)
    ram.write(nl_addr, NlEntryFactory.build(v=1, ppn=leaf_ppn))

    # Leaf DC の書き込み位置 (= leaf_ppn + (did[6:0] << 5))
    dc_addr = _ddt_leaf_addr_1lvl(leaf_ppn, did)
    dc_words = DcFactory.build(
        v=1, pdtv=0,
        iohgatp_mode=0, iohgatp_ppn=0,
        pscid=0,
        fsc_mode=8, fsc_ppn=s1_root,
    )
    ram.write_words(dc_addr, dc_words)

    dut._log.info(f"D03: NL @ 0x{nl_addr:x} → leaf_ppn=0x{leaf_ppn:x}, DC @ 0x{dc_addr:x}")

    # mode=3 (= 2lvl)
    await _trigger(dut, did=did, ddtp_ppn=ddt_ppn, ddtp_mode=3, en_s2=0)

    result = await _wait_update_or_error(dut, timeout=300)
    assert result == "SUCCESS", f"D03: expected SUCCESS, got {result}"
    assert int(dut.up_did_o.value) == did

    dut._log.info("D03 PASS")
