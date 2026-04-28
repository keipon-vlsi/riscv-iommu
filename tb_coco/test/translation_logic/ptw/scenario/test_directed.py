"""Directed tests for rv_iommu_ptw_sv39x4_pc.
T01-T05: reset/control
T10, T30: normal S1/S2 walks
T50, T51: two-stage walks
T70-T74: edge cases
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly, Timer

from tb_coco.common.helpers import (
    PTWTester, PhysicalMemoryManager, PteFactory,
    build_s1_walk, build_s2_walk, build_nested_walk,
    log_br_hit, sign_extend_sv39,
)


# ---------------------------------------------------------------------------
# Common setup helper
# ---------------------------------------------------------------------------

async def _setup(dut):
    """Set extra DUT inputs to safe defaults (not covered by PTWTester.reset)."""
    dut.mem_ar_ready_i.value         = 1
    dut.cdw_implicit_access_i.value  = 0
    dut.pscid_i.value               = 0
    dut.gscid_i.value               = 0
    dut.msi_en_i.value              = 0
    dut.msi_addr_mask_i.value       = 0
    dut.msi_addr_pattern_i.value    = 0
    dut.pdt_gppn_i.value            = 0


# ---------------------------------------------------------------------------
# T01: initial reset
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t01_initial_reset(dut):
    """T01: Reset asserts and de-asserts cleanly. Covers: state=IDLE after rst."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    await ReadOnly()
    assert int(dut.ptw_active_o.value)  == 0, "ptw_active_o should be 0 after reset"
    assert int(dut.ptw_error_o.value)   == 0, "ptw_error_o should be 0 after reset"
    assert int(dut.update_o.value)      == 0, "update_o should be 0 after reset"
    dut._log.info("T01 PASS: ptw_active_o=0, ptw_error_o=0, update_o=0 after reset")


# ---------------------------------------------------------------------------
# T02: reset during walk
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t02_reset_during_walk(dut):
    """T02: Assert rst_ni=0 mid-walk; DUT must return to IDLE. Covers: async reset."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x1000000)
    build_s1_walk(tester.ram, pmm, s1_root_ppn, iova)

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
    dut.req_iova_i.value = iova
    dut.is_store_i.value = 0
    await RisingEdge(dut.clk_i)
    dut.init_ptw_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.init_ptw_i.value = 0

    # Assert reset immediately (before walk completes)
    await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 1
    for _ in range(3):
        await RisingEdge(dut.clk_i)

    await ReadOnly()
    assert int(dut.ptw_active_o.value) == 0, "ptw_active_o should be 0 after mid-walk reset"
    dut._log.info("T02 PASS: mid-walk reset clears ptw_active_o")


# ---------------------------------------------------------------------------
# T03: cache-miss trigger (init_ptw_i edge detection)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t03_cache_miss_trigger(dut):
    """T03: init_ptw_i rising edge starts walk (BR01/BR02 edge detection). Covers: BR01, BR02, BR03."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x2000000)
    build_s1_walk(tester.ram, pmm, s1_root_ppn, iova)

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
    await tester.trigger(iova=iova)

    # PTW should be active immediately after trigger
    await ReadOnly()
    assert int(dut.ptw_active_o.value) == 1, "ptw_active_o should be 1 after trigger"
    log_br_hit("BR01", dut)
    log_br_hit("BR02", dut)
    log_br_hit("BR03", dut)

    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T03: Expected SUCCESS, got {result}"
    # wait_completion() already ended in ReadOnly; read signals directly
    assert int(dut.ptw_error_o.value) == 0, "ptw_error_o should be 0"
    dut._log.info("T03 PASS: cache-miss trigger works")


# ---------------------------------------------------------------------------
# T04: CDW implicit trigger
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t04_cdw_trigger(dut):
    """T04: cdw_implicit_access_i=1 triggers S2 walk for CDW. Covers: BR03, BR05."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root_ppn = pmm.alloc_ppn()
    # pdt_gppn_i = 0x4 (29-bit), GPA = 0x4000
    pdt_gppn = 0x4
    build_s2_walk(tester.ram, pmm, s2_root_ppn, pdt_gppn << 12)

    dut.en_1S_i.value            = 0
    dut.en_2S_i.value            = 1
    dut.iohgatp_ppn_i.value      = s2_root_ppn
    dut.pdt_gppn_i.value         = pdt_gppn
    dut.cdw_implicit_access_i.value = 0
    await RisingEdge(dut.clk_i)

    # Trigger via CDW implicit (no init_ptw_i pulse)
    dut.cdw_implicit_access_i.value = 1
    await RisingEdge(dut.clk_i)

    log_br_hit("BR03", dut)
    log_br_hit("BR05", dut)

    for _ in range(150):
        await RisingEdge(dut.clk_i)
        await ReadOnly()
        if int(dut.cdw_done_o.value) == 1:
            assert int(dut.update_o.value) == 0, "update_o must be 0 for CDW walk"
            dut._log.info("T04 PASS: CDW implicit trigger -> cdw_done_o=1")
            return
        if int(dut.ptw_error_o.value) == 1:
            assert False, f"T04: Unexpected error cause={int(dut.cause_code_o.value)}"
    assert False, "T04: Timeout waiting for CDW completion"


# ---------------------------------------------------------------------------
# T05: MSI disabled (gpaddr_is_msi_o stays 0)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t05_msi_disabled(dut):
    """T05: MSITrans=DISABLED ensures gpaddr_is_msi_o=0 throughout. Covers: BR32 False-path."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x5000000)
    build_s1_walk(tester.ram, pmm, s1_root_ppn, iova)

    dut.msi_en_i.value = 0
    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T05: walk failed: {result}"
    assert int(dut.gpaddr_is_msi_o.value) == 0, "gpaddr_is_msi_o must be 0 when MSITrans=DISABLED"
    dut._log.info("T05 PASS: gpaddr_is_msi_o=0 confirmed (MSITrans=DISABLED)")


# ---------------------------------------------------------------------------
# T10: S1-only normal walk (4K page, multiple IOVAs)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t10_s1_normal_walk(dut):
    """T10: S1-only 3-level walk for multiple IOVAs. Covers: BR04, BR06, BR07, BR10, BR14, BR19, BR21."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()

    test_iovas = [
        sign_extend_sv39(0x0000_1000),    # low address
        sign_extend_sv39(0x1FFF_F000),    # upper half of low canonical range
        sign_extend_sv39(0x0040_0000),    # crosses VPN[1] boundary
        sign_extend_sv39(0x4000_0000),    # crosses VPN[2] boundary
    ]

    for iova in test_iovas:
        build_s1_walk(tester.ram, pmm, s1_root_ppn, iova)

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)

    log_br_hit("BR04", dut)
    log_br_hit("BR06", dut)
    log_br_hit("BR07", dut)
    log_br_hit("BR10", dut)
    log_br_hit("BR14", dut)
    log_br_hit("BR19", dut)
    log_br_hit("BR21", dut)

    for iova in test_iovas:
        await tester.trigger(iova=iova)
        result = await tester.wait_completion()
        assert result == "SUCCESS", f"T10: walk failed for iova={hex(iova)}: {result}"
        assert int(dut.update_o.value) == 1,    f"T10: update_o=0 for iova={hex(iova)}"
        assert int(dut.ptw_error_o.value) == 0, f"T10: ptw_error_o=1 for iova={hex(iova)}"
        dut._log.info(f"T10: iova={hex(iova)} -> SUCCESS")
        await RisingEdge(dut.clk_i)

    dut._log.info("T10 PASS: S1 normal walk verified for all IOVAs")


# ---------------------------------------------------------------------------
# T30: S2-only normal walk
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t30_s2_normal_walk(dut):
    """T30: S2-only (Sv39x4) 3-level walk for multiple GPAs. Covers: BR04, BR06, BR07, BR10, BR14, BR19, BR21."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root_ppn = pmm.alloc_ppn()

    # GPAs that exercise different VPN2 values (11-bit for Sv39x4)
    test_gpas = [
        0x0000_1000,     # low GPA
        0x4000_0000,     # 1GiB boundary
        0x1_0000_0000,   # uses vpn2 > 256
    ]

    for gpa in test_gpas:
        build_s2_walk(tester.ram, pmm, s2_root_ppn, gpa)

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root_ppn)

    log_br_hit("BR04", dut)

    for gpa in test_gpas:
        # In S2-only mode, req_iova_i is the GPA
        await tester.trigger(iova=gpa)
        result = await tester.wait_completion()
        assert result == "SUCCESS", f"T30: walk failed for gpa={hex(gpa)}: {result}"
        assert int(dut.update_o.value) == 1,    f"T30: update_o=0 for gpa={hex(gpa)}"
        assert int(dut.ptw_error_o.value) == 0, f"T30: ptw_error_o=1 for gpa={hex(gpa)}"
        dut._log.info(f"T30: gpa={hex(gpa)} -> SUCCESS")
        await RisingEdge(dut.clk_i)

    dut._log.info("T30 PASS: S2 normal walk verified")


# ---------------------------------------------------------------------------
# T50: Two-stage S2-INTERMED walk check
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t50_twostage_s2_walk(dut):
    """T50: Two-stage nested walk – S2-INTERMED correctly resolves S1 page table addresses. Covers: BR04, BR11, BR12, BR19, BR20, BR21, BR22."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root_ppn  = pmm.alloc_ppn()    # 0x1000 (bits[1:0]=0 ✓)
    s1_root_gppn = pmm.alloc_ppn()    # 0x1001
    iova = sign_extend_sv39(0x1000_0000)

    build_nested_walk(tester.ram, pmm, s1_root_gppn, s2_root_ppn, iova)

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root_ppn)

    log_br_hit("BR04", dut)
    log_br_hit("BR11", dut)
    log_br_hit("BR12", dut)
    log_br_hit("BR19", dut)
    log_br_hit("BR20", dut)
    log_br_hit("BR21", dut)
    log_br_hit("BR22", dut)

    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "SUCCESS", f"T50: nested walk failed: {result}"
    assert int(dut.update_o.value) == 1, "T50: update_o must be 1 after nested walk"
    dut._log.info("T50 PASS: Two-stage S2-INTERMED walk succeeded")


# ---------------------------------------------------------------------------
# T51: Two-stage full walk (S1 LVL1,2,3 + S2-FINAL)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t51_twostage_full_walk(dut):
    """T51: Full nested walk – verify update_o=1 and up_1S/up_2S content valid. Covers: BR04, BR11, BR12, BR14, BR19-BR22."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root_ppn  = pmm.alloc_ppn()
    s1_root_gppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x2000_0000)
    final_spa = 0xDEAD_0000

    build_nested_walk(tester.ram, pmm, s1_root_gppn, s2_root_ppn, iova,
                      final_spa=final_spa)

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root_ppn)

    log_br_hit("BR14", dut)

    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "SUCCESS", f"T51: nested walk failed: {result}"
    assert int(dut.update_o.value)      == 1, "T51: update_o must be 1"
    assert int(dut.ptw_error_o.value)   == 0, "T51: ptw_error_o must be 0"
    assert int(dut.ptw_error_2S_o.value) == 0, "T51: ptw_error_2S_o must be 0"

    # up_1S_content_o should contain the S1 leaf PTE (pointing to final_gppn)
    s1_pte = int(dut.up_1S_content_o.value)
    assert (s1_pte & 0x1) == 1, f"T51: S1 leaf PTE V-bit should be 1, pte={hex(s1_pte)}"
    # up_2S_content_o should contain the S2 leaf PTE (pointing to final_spa)
    s2_pte = int(dut.up_2S_content_o.value)
    assert (s2_pte & 0x1) == 1, f"T51: S2 leaf PTE V-bit should be 1, pte={hex(s2_pte)}"

    dut._log.info(f"T51 PASS: full nested walk, s1_pte={hex(s1_pte)}, s2_pte={hex(s2_pte)}")


# ---------------------------------------------------------------------------
# T70: G-bit (global mapping) propagation
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t70_global_bit(dut):
    """T70: G=1 on intermediate PTE propagates to up_1S_content_o. Covers: BR08."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x3000_0000)

    # Build normal walk but place G=1 at the root non-leaf PTE
    vpn2 = (iova >> 30) & 0x1FF
    vpn1 = (iova >> 21) & 0x1FF
    vpn0 = (iova >> 12) & 0x1FF

    l2_ppn = pmm.alloc_ppn()
    l1_ppn = pmm.alloc_ppn()
    leaf_ppn = pmm.alloc_ppn()

    # Root level: G=1 non-leaf
    root_pte = PteFactory.build(v=1, g=1, ppn=l2_ppn)
    tester.ram.write((s1_root_ppn << 12) + vpn2 * 8, root_pte)
    # L2 level: normal non-leaf
    tester.ram.write((l2_ppn << 12) + vpn1 * 8, PteFactory.non_leaf(ppn=l1_ppn))
    # Leaf
    tester.ram.write((l1_ppn << 12) + vpn0 * 8, PteFactory.s1_leaf(ppn=leaf_ppn))

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)

    log_br_hit("BR08", dut)

    await tester.trigger(iova=iova)
    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T70: walk failed: {result}"
    s1_pte = int(dut.up_1S_content_o.value)
    g_bit = (s1_pte >> 5) & 1
    assert g_bit == 1, f"T70: G-bit not propagated to up_1S_content_o: pte={hex(s1_pte)}"
    dut._log.info(f"T70 PASS: G-bit propagated, leaf_pte={hex(s1_pte)}")


# ---------------------------------------------------------------------------
# T71: CDW implicit translation success
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t71_cdw_implicit_success(dut):
    """T71: CDW implicit access succeeds → cdw_done_o=1, update_o=0. Covers: BR03, BR05, BR15."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root_ppn = pmm.alloc_ppn()
    pdt_gppn = 0x8   # 29-bit GPA PPN, GPA = 0x8000

    build_s2_walk(tester.ram, pmm, s2_root_ppn, pdt_gppn << 12)

    dut.en_1S_i.value               = 0
    dut.en_2S_i.value               = 1
    dut.iohgatp_ppn_i.value         = s2_root_ppn
    dut.pdt_gppn_i.value            = pdt_gppn
    dut.cdw_implicit_access_i.value = 0
    await RisingEdge(dut.clk_i)

    dut.cdw_implicit_access_i.value = 1
    await RisingEdge(dut.clk_i)

    log_br_hit("BR03", dut)
    log_br_hit("BR05", dut)
    log_br_hit("BR15", dut)

    for _ in range(150):
        await RisingEdge(dut.clk_i)
        await ReadOnly()
        if int(dut.cdw_done_o.value) == 1:
            assert int(dut.update_o.value) == 0, "update_o must be 0 for CDW walk"
            assert int(dut.ptw_error_o.value) == 0, "ptw_error_o must be 0 on CDW success"
            dut._log.info("T71 PASS: CDW implicit success, cdw_done_o=1")
            return
        if int(dut.ptw_error_o.value) == 1:
            assert False, f"T71: CDW failed with cause={int(dut.cause_code_o.value)}"
    assert False, "T71: Timeout waiting for CDW completion"


# ---------------------------------------------------------------------------
# T73: Back-to-back walks
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t73_back_to_back(dut):
    """T73: Two consecutive S1 walks with immediate re-trigger. Covers: BR01, BR02."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    iovas = [sign_extend_sv39(0x0100_0000), sign_extend_sv39(0x0200_0000)]
    for iova in iovas:
        build_s1_walk(tester.ram, pmm, s1_root_ppn, iova)

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)

    log_br_hit("BR01", dut)
    log_br_hit("BR02", dut)

    for i, iova in enumerate(iovas):
        await tester.trigger(iova=iova)
        result = await tester.wait_completion()
        assert result == "SUCCESS", f"T73: walk {i} failed: {result}"
        assert int(dut.update_o.value) == 1, f"T73: update_o=0 for walk {i}"
        dut._log.info(f"T73: walk {i} -> SUCCESS")
        # Clock edge between iterations (cocotb v2 ReadOnly phase requirement)
        await RisingEdge(dut.clk_i)

    dut._log.info("T73 PASS: back-to-back walks both succeeded")


# ---------------------------------------------------------------------------
# T74: Backpressure (ar_ready delayed)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t74_backpressure(dut):
    """T74: ar_ready=0 for 10 cycles then 1 – walk must eventually complete. Covers: BR06."""
    tester = PTWTester(dut)
    await _setup(dut)
    dut.mem_ar_ready_i.value = 0   # Start with ar_ready=0 (backpressure)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0500_0000)
    build_s1_walk(tester.ram, pmm, s1_root_ppn, iova)

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
    await tester.trigger(iova=iova)

    # Hold ar_ready=0 for 10 cycles, then release
    for _ in range(10):
        await RisingEdge(dut.clk_i)
    dut.mem_ar_ready_i.value = 1

    log_br_hit("BR06", dut)

    result = await tester.wait_completion(timeout_cycles=250)
    assert result == "SUCCESS", f"T74: walk failed after backpressure: {result}"
    assert int(dut.update_o.value) == 1, "T74: update_o must be 1 after backpressure recovery"
    dut._log.info("T74 PASS: backpressure walk succeeded")
