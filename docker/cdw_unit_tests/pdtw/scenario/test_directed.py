"""PDTW (rv_iommu_pdtw) ハッピーパス単体検証

配置: /workspace/tb_coco/test/translation_logic/pdtw/scenario/test_directed.py

カバー範囲 (= 全部 happy path):
  P01: PD8 mode (= 1-level)、 S2 disabled
  P02: PD20 mode (= 3-level)、 S2 disabled
  P03: PD8 mode、 S2 enabled (= need_leaf_s2 path)
"""

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly
from cocotb.clock import Clock

from tb_coco.common.helpers_cdw import (
    PcFactory, NlEntryFactory, PhysicalMemoryManager,
    MockMemoryBurst, simulate_ptw_done,
)


# ---------------------------------------------------------------------------
# Common setup
# ---------------------------------------------------------------------------

async def _start_clock(dut):
    cocotb.start_soon(Clock(dut.clk_i, 10, unit="ns").start())


async def _reset(dut, cycles=5):
    dut.rst_ni.value     = 0
    dut.init_i.value     = 0
    dut.req_did_i.value  = 0
    dut.req_pid_i.value  = 0
    dut.pdtp_ppn_i.value = 0
    dut.pdtp_mode_i.value = 0
    dut.en_stage2_i.value = 0
    dut.flush_i.value    = 0
    dut.ptw_done_i.value = 0
    dut.pdt_ppn_i.value  = 0

    for _ in range(cycles):
        await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 1
    for _ in range(cycles):
        await RisingEdge(dut.clk_i)


def _pdt_leaf_addr_pd8(pdtp_ppn, pid):
    """PD8 mode (= mode 1): cdw_pptr = {pdtp_ppn, pid[7:0], 4'b0}
       1 page = 256 entries × 16 bytes (= PC は 2 × 8 byte = 16 byte stride)。
    """
    return (pdtp_ppn << 12) + ((pid & 0xFF) << 4)


def _pdt_nl_addr_pd17(pdtp_ppn, pid):
    """PD17 mode (= mode 2): top NL は {pdtp_ppn, pid[16:8], 3'b0}。"""
    return (pdtp_ppn << 12) + (((pid >> 8) & 0x1FF) << 3)


def _pdt_nl_addr_pd20(pdtp_ppn, pid):
    """PD20 mode (= mode 3): top NL は {pdtp_ppn, 6'b0, pid[19:17], 3'b0}。

    DDTW source line 187-188 から:
        cdw_pptr_n = {pdtp_ppn_i, 6'b0, req_pid_i[19:17], 3'b0}
    """
    return (pdtp_ppn << 12) + (((pid >> 17) & 0x7) << 3)


def _pdt_next_pptr(base_ppn, curr_lvl, pid):
    """PDTW source line 127-138 の next_pptr の Python 模倣。

    curr_lvl: 4 (LVL3) → next index = pid[16:8], stride 8
              3 (LVL2) → next index = pid[7:0], stride 16
    """
    if curr_lvl == 4:  # LVL3 → LVL2 (= mid)
        return (base_ppn << 12) + (((pid >> 8) & 0x1FF) << 3)
    if curr_lvl == 3:  # LVL2 → LVL1 (= leaf)
        return (base_ppn << 12) + ((pid & 0xFF) << 4)
    return 0


async def _trigger(dut, did, pid, pdtp_ppn, pdtp_mode, en_s2=0):
    dut.req_did_i.value   = did
    dut.req_pid_i.value   = pid
    dut.pdtp_ppn_i.value  = pdtp_ppn
    dut.pdtp_mode_i.value = pdtp_mode
    dut.en_stage2_i.value = en_s2
    await RisingEdge(dut.clk_i)
    dut.init_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.init_i.value = 0


async def _wait_update_or_error(dut, timeout=300):
    for _ in range(timeout):
        await RisingEdge(dut.clk_i)
        await ReadOnly()
        if int(dut.update_pc_o.value) == 1:
            return "SUCCESS"
        if int(dut.error_o.value) == 1:
            return "ERROR"
    return "TIMEOUT"


# ---------------------------------------------------------------------------
# P01: PD8 mode, S2 disabled
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_p01_pd8_s2_disabled(dut):
    """シンプル: PD8 (= 1 段)、 S2 disabled、 pc.fsc=Sv39。"""
    await _start_clock(dut)
    ram = MockMemoryBurst(dut)
    await _reset(dut)

    pmm = PhysicalMemoryManager(start_ppn=0x400)
    pdt_ppn = pmm.alloc_ppn()
    s1_root = pmm.alloc_ppn()
    pid     = 0x07
    did     = 0x05

    pc_words = PcFactory.build(
        v=1, ens=0, sum_bit=0,
        pscid=0x123,
        fsc_mode=8, fsc_ppn=s1_root,
    )

    pc_addr = _pdt_leaf_addr_pd8(pdt_ppn, pid)
    ram.write_words(pc_addr, pc_words)

    dut._log.info(f"P01: PC @ 0x{pc_addr:x}, pid={pid}, s1_root=0x{s1_root:x}")

    await _trigger(dut, did=did, pid=pid, pdtp_ppn=pdt_ppn, pdtp_mode=1, en_s2=0)

    result = await _wait_update_or_error(dut)
    assert result == "SUCCESS", f"P01: expected SUCCESS, got {result}"
    assert int(dut.up_did_o.value) == did
    assert int(dut.up_pid_o.value) == pid

    dut._log.info("P01 PASS")


# ---------------------------------------------------------------------------
# P02: PD20 mode (= 3-level), S2 disabled
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_p02_pd20_s2_disabled(dut):
    """PD20: top NL → mid NL → leaf PC。 3 段全部を経由する。"""
    await _start_clock(dut)
    ram = MockMemoryBurst(dut)
    await _reset(dut)

    pmm = PhysicalMemoryManager(start_ppn=0x500)
    pdt_root_ppn = pmm.alloc_ppn()    # 0x500 (= top NL page)
    pdt_mid_ppn  = pmm.alloc_ppn()    # 0x501
    pdt_leaf_ppn = pmm.alloc_ppn()    # 0x502 (= PC が並ぶ page)
    s1_root      = pmm.alloc_ppn()    # 0x503
    pid          = 0x12345
    did          = 0x11

    # Top NL (= mode=3 = PD20 で、 cdw_lvl_q starts at LVL3 (= 4))
    top_addr = _pdt_nl_addr_pd20(pdt_root_ppn, pid)
    ram.write(top_addr, NlEntryFactory.build(v=1, ppn=pdt_mid_ppn))

    # Mid NL (= LVL3 → LVL2 遷移後の位置: pid[16:8] index、 stride 8)
    mid_addr = _pdt_next_pptr(pdt_mid_ppn, 4, pid)
    ram.write(mid_addr, NlEntryFactory.build(v=1, ppn=pdt_leaf_ppn))

    # Leaf PC (= LVL2 → LVL1 遷移後の位置: pid[7:0] index、 stride 16)
    pc_addr = _pdt_next_pptr(pdt_leaf_ppn, 3, pid)
    pc_words = PcFactory.build(
        v=1, pscid=0x456,
        fsc_mode=8, fsc_ppn=s1_root,
    )
    ram.write_words(pc_addr, pc_words)

    dut._log.info(f"P02: top NL @ 0x{top_addr:x} → 0x{pdt_mid_ppn:x}")
    dut._log.info(f"P02: mid NL @ 0x{mid_addr:x} → 0x{pdt_leaf_ppn:x}")
    dut._log.info(f"P02: leaf PC @ 0x{pc_addr:x}")

    await _trigger(dut, did=did, pid=pid, pdtp_ppn=pdt_root_ppn, pdtp_mode=3, en_s2=0)

    result = await _wait_update_or_error(dut, timeout=500)
    assert result == "SUCCESS", f"P02: expected SUCCESS, got {result}"
    assert int(dut.up_pid_o.value) == pid

    dut._log.info("P02 PASS")


# ---------------------------------------------------------------------------
# P03: PD8 mode, S2 enabled → leaf S2 walk simulation
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_p03_pd8_with_s2(dut):
    """S2 enabled + pc.fsc.mode=Sv39 → need_leaf_s2、 PTW_done を simulate。"""
    await _start_clock(dut)
    ram = MockMemoryBurst(dut)
    await _reset(dut)

    pmm = PhysicalMemoryManager(start_ppn=0x600)
    pdt_ppn      = pmm.alloc_ppn()
    s1_root_gppn = pmm.alloc_ppn()    # = pc.fsc.PPN (GPPN)
    s1_root_spa  = pmm.alloc_ppn()    # = S2 翻訳結果
    pid = 0x33
    did = 0x22

    pc_words = PcFactory.build(
        v=1, pscid=0x77,
        fsc_mode=8, fsc_ppn=s1_root_gppn,
    )
    pc_addr = _pdt_leaf_addr_pd8(pdt_ppn, pid)
    ram.write_words(pc_addr, pc_words)

    dut._log.info(f"P03: PC @ 0x{pc_addr:x}, pc.fsc.ppn(GPPN)=0x{s1_root_gppn:x}, "
                  f"sim PTW returns SPA=0x{s1_root_spa:x}")

    # PTW done を simulate (= cdw_implicit_access が立ったら指定 PPN を返す)
    cocotb.start_soon(simulate_ptw_done(dut, s1_root_spa))

    await _trigger(dut, did=did, pid=pid, pdtp_ppn=pdt_ppn, pdtp_mode=1, en_s2=1)

    result = await _wait_update_or_error(dut, timeout=500)
    assert result == "SUCCESS", f"P03: expected SUCCESS, got {result}"
    assert int(dut.up_pid_o.value) == pid

    dut._log.info("P03 PASS")
