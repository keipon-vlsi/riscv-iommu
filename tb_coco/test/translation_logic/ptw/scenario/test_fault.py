"""Fault injection tests for rv_iommu_ptw_sv39x4_pc.
T11-T22: S1-only faults
T31-T41: S2-only faults
T52-T63: Two-stage faults
T72: CDW implicit error
"""

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly

from tb_coco.common.helpers import (
    PTWTester, PhysicalMemoryManager, PteFactory,
    build_s1_walk, build_s2_walk, build_nested_walk,
    log_br_hit, sign_extend_sv39,
)

# Cause codes
LOAD_PAGE_FAULT   = 13
STORE_PAGE_FAULT  = 15
LOAD_GUEST_PF     = 21
STORE_GUEST_PF    = 23
PT_DATA_CORRUPT   = 274


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------

async def _setup(dut):
    dut.mem_ar_ready_i.value         = 1
    dut.cdw_implicit_access_i.value  = 0
    dut.pscid_i.value               = 0
    dut.gscid_i.value               = 0
    dut.msi_en_i.value              = 0
    dut.msi_addr_mask_i.value       = 0
    dut.msi_addr_pattern_i.value    = 0
    dut.pdt_gppn_i.value            = 0


def _write_invalid_pte(ram, addr, pattern):
    """Write an invalid PTE at addr. pattern: 0=v=0, 1=v=1,W=1,R=0, 2=v=0,W=1."""
    if pattern == 0:
        pte = PteFactory.build(v=0, r=0, w=0)
    elif pattern == 1:
        pte = PteFactory.build(v=1, r=0, w=1)   # R=0,W=1 reserved encoding
    else:
        pte = PteFactory.build(v=0, r=0, w=1)
    ram.write(addr, pte)
    return addr


# ---------------------------------------------------------------------------
# T11: S1 LVL1/2/3 invalid PTE
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t11_s1_invalid_pte(dut):
    """T11: S1 invalid PTE (v=0 / R=0,W=1) at each walk level. Covers: BR09, BR29(False)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR09", dut)

    # --- LVL1 invalid ---
    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0100_0000)
    vpn2 = (iova >> 30) & 0x1FF
    tester.ram.write((s1_root_ppn << 12) + vpn2 * 8, PteFactory.build(v=0))

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
    await tester.trigger(iova=iova, is_store=False)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T11/LVL1: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value)    == 1, "ptw_error_o must be 1"
    assert int(dut.ptw_error_2S_o.value) == 0, "ptw_error_2S_o must be 0 for S1 fault"
    assert int(dut.cause_code_o.value)   == LOAD_PAGE_FAULT, \
        f"expected {LOAD_PAGE_FAULT}, got {int(dut.cause_code_o.value)}"
    await RisingEdge(dut.clk_i)
    await tester.reset()

    # --- LVL2 invalid (R=0,W=1) ---
    pmm = PhysicalMemoryManager(start_ppn=0x2000)
    s1_root_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0200_0000)
    vpn2 = (iova >> 30) & 0x1FF
    vpn1 = (iova >> 21) & 0x1FF
    l2_ppn = pmm.alloc_ppn()
    tester.ram.write((s1_root_ppn << 12) + vpn2 * 8, PteFactory.non_leaf(ppn=l2_ppn))
    tester.ram.write((l2_ppn << 12) + vpn1 * 8, PteFactory.build(v=1, r=0, w=1))

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
    await tester.trigger(iova=iova, is_store=True)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T11/LVL2: expected ERROR, got {result}"
    assert int(dut.cause_code_o.value) == STORE_PAGE_FAULT, \
        f"expected {STORE_PAGE_FAULT}, got {int(dut.cause_code_o.value)}"
    await RisingEdge(dut.clk_i)
    await tester.reset()

    # --- LVL3 invalid ---
    pmm2 = PhysicalMemoryManager(start_ppn=0x3100)
    s1_root2 = pmm2.alloc_ppn()
    iova2 = sign_extend_sv39(0x0310_0000)
    l2b = pmm2.alloc_ppn()
    l1b = pmm2.alloc_ppn()
    vpn2b = (iova2 >> 30) & 0x1FF
    vpn1b = (iova2 >> 21) & 0x1FF
    vpn0b = (iova2 >> 12) & 0x1FF
    tester.ram.write((s1_root2 << 12) + vpn2b * 8, PteFactory.non_leaf(ppn=l2b))
    tester.ram.write((l2b << 12) + vpn1b * 8, PteFactory.non_leaf(ppn=l1b))
    tester.ram.write((l1b << 12) + vpn0b * 8, PteFactory.build(v=0))  # invalid leaf

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root2)
    await tester.trigger(iova=iova2, is_store=False)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T11/LVL3: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value) == 1, "ptw_error_o must be 1"
    assert int(dut.cause_code_o.value) == LOAD_PAGE_FAULT

    dut._log.info("T11 PASS: S1 invalid PTE faults at LVL1/2/3")


# ---------------------------------------------------------------------------
# T12: S1 reserved bits non-zero
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t12_s1_reserved_bits(dut):
    """T12: S1 PTE bits[63:54] non-zero triggers PAGE_FAULT. Covers: BR25."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR25", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0400_0000)
    vpn2 = (iova >> 30) & 0x1FF
    vpn1 = (iova >> 21) & 0x1FF
    vpn0 = (iova >> 12) & 0x1FF

    l2_ppn = pmm.alloc_ppn()
    l1_ppn = pmm.alloc_ppn()
    leaf_ppn = pmm.alloc_ppn()

    tester.ram.write((s1_root_ppn << 12) + vpn2 * 8, PteFactory.non_leaf(ppn=l2_ppn))
    tester.ram.write((l2_ppn << 12) + vpn1 * 8, PteFactory.non_leaf(ppn=l1_ppn))
    # Leaf with reserved bits[63:54] set
    leaf_pte = PteFactory.build(v=1, r=1, w=1, a=1, d=1, ppn=leaf_ppn, reserved=0x3FF)
    tester.ram.write((l1_ppn << 12) + vpn0 * 8, leaf_pte)

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T12: expected ERROR for reserved bits, got {result}"
    assert int(dut.ptw_error_o.value)    == 1
    assert int(dut.ptw_error_2S_o.value) == 0
    assert int(dut.cause_code_o.value)   == LOAD_PAGE_FAULT

    dut._log.info("T12 PASS: reserved bits detected at LVL3")


# ---------------------------------------------------------------------------
# T13: S1 AXI error → PT_DATA_CORRUPTION (274)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t13_s1_axi_error(dut):
    """T13: AXI SLVERR during S1 walk → cause_code=274. Covers: BR27, BR28."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR27", dut)
    log_br_hit("BR28", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0500_0000)
    build_s1_walk(tester.ram, pmm, s1_root_ppn, iova)

    # Inject SLVERR for the root-level PTE read
    vpn2 = (iova >> 30) & 0x1FF
    root_pte_addr = (s1_root_ppn << 12) + vpn2 * 8
    tester.ram.inject_axi_error(root_pte_addr, resp_code=2)  # SLVERR=2

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T13: expected ERROR on AXI error, got {result}"
    assert int(dut.ptw_error_o.value)  == 1
    assert int(dut.cause_code_o.value) == PT_DATA_CORRUPT, \
        f"expected {PT_DATA_CORRUPT}, got {int(dut.cause_code_o.value)}"

    dut._log.info("T13 PASS: AXI error → PT_DATA_CORRUPTION=274")


# ---------------------------------------------------------------------------
# T14: S1 non-leaf (LVL1/2) with A/D/U bits set
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t14_s1_nonleaf_adu(dut):
    """T14: Non-leaf PTE at LVL1/LVL2 with A or D or U set → PAGE_FAULT. Covers: BR23."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR23", dut)

    # A=1 on LVL1 non-leaf
    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()
    l2_ppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0600_0000)
    vpn2 = (iova >> 30) & 0x1FF
    # Non-leaf with A=1 (invalid)
    tester.ram.write((s1_root_ppn << 12) + vpn2 * 8,
                     PteFactory.build(v=1, r=0, w=0, x=0, a=1, ppn=l2_ppn))

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
    await tester.trigger(iova=iova, is_store=False)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T14/A-bit: expected ERROR, got {result}"
    assert int(dut.cause_code_o.value) == LOAD_PAGE_FAULT
    await RisingEdge(dut.clk_i)
    await tester.reset()

    # D=1 on LVL2 non-leaf
    pmm2 = PhysicalMemoryManager(start_ppn=0x2000)
    s1_root2 = pmm2.alloc_ppn()
    l2b = pmm2.alloc_ppn()
    l1b = pmm2.alloc_ppn()
    iova2 = sign_extend_sv39(0x0700_0000)
    vpn2b = (iova2 >> 30) & 0x1FF
    vpn1b = (iova2 >> 21) & 0x1FF
    tester.ram.write((s1_root2 << 12) + vpn2b * 8, PteFactory.non_leaf(ppn=l2b))
    tester.ram.write((l2b << 12) + vpn1b * 8,
                     PteFactory.build(v=1, r=0, w=0, x=0, d=1, ppn=l1b))

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root2)
    await tester.trigger(iova=iova2, is_store=False)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T14/D-bit: expected ERROR, got {result}"
    assert int(dut.cause_code_o.value) == LOAD_PAGE_FAULT

    dut._log.info("T14 PASS: non-leaf A/D bits trigger fault")


# ---------------------------------------------------------------------------
# T15: S1 LVL3 non-leaf (depth exceeded)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t15_s1_lvl3_nonleaf(dut):
    """T15: LVL3 PTE with R=X=0 (non-leaf at max depth) → PAGE_FAULT. Covers: BR24."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR24", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root = pmm.alloc_ppn()
    l2 = pmm.alloc_ppn()
    l1 = pmm.alloc_ppn()
    l0_target = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0800_0000)
    vpn2 = (iova >> 30) & 0x1FF
    vpn1 = (iova >> 21) & 0x1FF
    vpn0 = (iova >> 12) & 0x1FF
    tester.ram.write((s1_root << 12) + vpn2 * 8, PteFactory.non_leaf(ppn=l2))
    tester.ram.write((l2 << 12) + vpn1 * 8, PteFactory.non_leaf(ppn=l1))
    # LVL3 entry is a non-leaf (R=X=0, V=1) — at this depth, must be leaf
    tester.ram.write((l1 << 12) + vpn0 * 8, PteFactory.non_leaf(ppn=l0_target))

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T15: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value)    == 1
    assert int(dut.ptw_error_2S_o.value) == 0
    assert int(dut.cause_code_o.value)   == LOAD_PAGE_FAULT

    dut._log.info("T15 PASS: LVL3 non-leaf triggers fault")


# ---------------------------------------------------------------------------
# T16: S1 superpage misalignment
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t16_s1_superpage_misalign(dut):
    """T16: 1G leaf ppn[17:0]!=0 and 2M leaf ppn[8:0]!=0 → PAGE_FAULT. Covers: BR16, BR17."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR16", dut)
    log_br_hit("BR17", dut)

    # --- 1G superpage misaligned (LVL1 leaf with ppn[17:0]!=0) ---
    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x4000_0000)  # 1G-aligned IOVA
    vpn2 = (iova >> 30) & 0x1FF
    # 1G leaf: PPN that is NOT 1G-aligned (ppn[17:0] != 0)
    misaligned_ppn = 0x8001  # bit 0 set → misaligned
    tester.ram.write((s1_root << 12) + vpn2 * 8,
                     PteFactory.build(v=1, r=1, w=1, a=1, d=1, ppn=misaligned_ppn))

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T16/1G: expected ERROR, got {result}"
    assert int(dut.cause_code_o.value) == LOAD_PAGE_FAULT
    await RisingEdge(dut.clk_i)
    await tester.reset()

    # --- 2M superpage misaligned (LVL2 leaf with ppn[8:0]!=0) ---
    pmm2 = PhysicalMemoryManager(start_ppn=0x2000)
    s1_root2 = pmm2.alloc_ppn()
    l2 = pmm2.alloc_ppn()
    iova2 = sign_extend_sv39(0x0020_0000)  # 2M-aligned IOVA
    vpn2b = (iova2 >> 30) & 0x1FF
    vpn1b = (iova2 >> 21) & 0x1FF
    misaligned_ppn_2m = 0x9001  # ppn[8:0] != 0
    tester.ram.write((s1_root2 << 12) + vpn2b * 8, PteFactory.non_leaf(ppn=l2))
    tester.ram.write((l2 << 12) + vpn1b * 8,
                     PteFactory.build(v=1, r=1, w=1, a=1, d=1, ppn=misaligned_ppn_2m))

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root2)
    await tester.trigger(iova=iova2)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T16/2M: expected ERROR, got {result}"
    assert int(dut.cause_code_o.value) == LOAD_PAGE_FAULT

    dut._log.info("T16 PASS: superpage misalignment faults")


# ---------------------------------------------------------------------------
# T17-T20: PTW scope-out tests (Wrapper-layer checks, PTW returns update_o=1)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t17_s1_leaf_a_cleared(dut):
    """T17: Leaf A=0 – PTW succeeds (update_o=1). Wrapper checks A-bit. Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0900_0000)
    build_s1_walk(tester.ram, pmm, s1_root, iova, leaf_flags={"a": 0, "d": 1})

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T17: PTW should succeed (a=0 is Wrapper scope), got {result}"
    assert int(dut.update_o.value) == 1, "T17: update_o must be 1 (Wrapper handles A-bit)"
    dut._log.info("T17 PASS: leaf A=0 → PTW update_o=1 (Wrapper scope)")


@cocotb.test()
async def test_t18_s1_leaf_r_cleared(dut):
    """T18: Leaf R=0, X=1 (execute-only) – PTW succeeds. Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0A00_0000)
    build_s1_walk(tester.ram, pmm, s1_root, iova, leaf_flags={"r": 0, "x": 1, "w": 0})

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T18: PTW should succeed for R=0,X=1 execute-only, got {result}"
    assert int(dut.update_o.value) == 1, "T18: update_o must be 1"
    dut._log.info("T18 PASS: leaf R=0,X=1 → PTW update_o=1")


@cocotb.test()
async def test_t19_s1_store_d_cleared(dut):
    """T19: STORE with leaf D=0 – PTW succeeds. Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0B00_0000)
    build_s1_walk(tester.ram, pmm, s1_root, iova,
                  leaf_flags={"r": 1, "w": 1, "d": 0, "a": 1})

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root)
    await tester.trigger(iova=iova, is_store=True)
    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T19: PTW should succeed (D-bit is Wrapper scope), got {result}"
    assert int(dut.update_o.value) == 1
    dut._log.info("T19 PASS: STORE D=0 → PTW update_o=1 (Wrapper scope)")


@cocotb.test()
async def test_t20_s1_store_w_cleared(dut):
    """T20: STORE with leaf W=0 (read-only) – PTW succeeds. Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0C00_0000)
    build_s1_walk(tester.ram, pmm, s1_root, iova,
                  leaf_flags={"r": 1, "w": 0, "d": 1, "a": 1})

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root)
    await tester.trigger(iova=iova, is_store=True)
    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T20: PTW should succeed (W-bit is Wrapper scope), got {result}"
    assert int(dut.update_o.value) == 1
    dut._log.info("T20 PASS: STORE W=0 → PTW update_o=1 (Wrapper scope)")


# ---------------------------------------------------------------------------
# T21: S1 fault priority (AXI error wins over PAGE_FAULT)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t21_s1_fault_priority(dut):
    """T21: AXI SLVERR on same fetch as invalid PTE → cause=274. Covers: BR27, BR28, BR09."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR27", dut)
    log_br_hit("BR28", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0D00_0000)
    vpn2 = (iova >> 30) & 0x1FF
    pte_addr = (s1_root << 12) + vpn2 * 8
    # Write invalid PTE AND inject AXI error for same address
    tester.ram.write(pte_addr, PteFactory.build(v=0))
    tester.ram.inject_axi_error(pte_addr, resp_code=2)

    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T21: expected ERROR, got {result}"
    assert int(dut.cause_code_o.value) == PT_DATA_CORRUPT, \
        f"T21: AXI error should win, expected {PT_DATA_CORRUPT}, got {int(dut.cause_code_o.value)}"
    dut._log.info("T21 PASS: AXI error priority over PAGE_FAULT")


# ---------------------------------------------------------------------------
# T22: S1 fault classification (LOAD vs STORE cause codes)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t22_s1_fault_classification(dut):
    """T22: is_store=0 → cause=13, is_store=1 → cause=15. Covers: BR28, BR29."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR29", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0E00_0000)
    vpn2 = (iova >> 30) & 0x1FF
    tester.ram.write((s1_root << 12) + vpn2 * 8, PteFactory.build(v=0))

    # LOAD fault
    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root)
    await tester.trigger(iova=iova, is_store=False)
    result = await tester.wait_completion()
    assert result == "ERROR"
    assert int(dut.cause_code_o.value) == LOAD_PAGE_FAULT, \
        f"T22: LOAD expected {LOAD_PAGE_FAULT}, got {int(dut.cause_code_o.value)}"
    await RisingEdge(dut.clk_i)
    await tester.reset()

    # STORE fault
    await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root)
    await tester.trigger(iova=iova, is_store=True)
    result = await tester.wait_completion()
    assert result == "ERROR"
    assert int(dut.cause_code_o.value) == STORE_PAGE_FAULT, \
        f"T22: STORE expected {STORE_PAGE_FAULT}, got {int(dut.cause_code_o.value)}"

    dut._log.info("T22 PASS: LOAD→13 and STORE→15 verified")


# ===========================================================================
# S2-only fault tests
# ===========================================================================

# ---------------------------------------------------------------------------
# T31: S2 invalid PTE
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t31_s2_invalid_pte(dut):
    """T31: S2 invalid PTE at LVL1 → ptw_error_2S_o=1. Covers: BR09, BR29(True)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR09", dut)
    log_br_hit("BR29", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    gpa = 0x1000_0000
    vpn2 = (gpa >> 30) & 0x7FF   # 11-bit VPN2 for Sv39x4
    tester.ram.write((s2_root << 12) + vpn2 * 8, PteFactory.build(v=0))

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa, is_store=False)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T31: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value)    == 1
    assert int(dut.ptw_error_2S_o.value) == 1, "ptw_error_2S_o must be 1 for S2 fault"
    assert int(dut.cause_code_o.value)   == LOAD_GUEST_PF, \
        f"expected {LOAD_GUEST_PF}, got {int(dut.cause_code_o.value)}"
    await RisingEdge(dut.clk_i)
    await tester.reset()

    # STORE → cause=23
    pmm2 = PhysicalMemoryManager(start_ppn=0x2000)
    s2_root2 = pmm2.alloc_ppn()
    gpa2 = 0x2000_0000
    vpn2b = (gpa2 >> 30) & 0x7FF
    tester.ram.write((s2_root2 << 12) + vpn2b * 8, PteFactory.build(v=1, r=0, w=1))

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root2)
    await tester.trigger(iova=gpa2, is_store=True)
    result = await tester.wait_completion()
    assert result == "ERROR"
    assert int(dut.ptw_error_2S_o.value) == 1
    assert int(dut.cause_code_o.value) == STORE_GUEST_PF

    dut._log.info("T31 PASS: S2 invalid PTE → ptw_error_2S_o=1")


# ---------------------------------------------------------------------------
# T32: S2 reserved bits
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t32_s2_reserved_bits(dut):
    """T32: S2 leaf reserved bits → GUEST_PAGE_FAULT. Covers: BR25, BR29(True)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR25", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    gpa = 0x3000_0000
    vpn2 = (gpa >> 30) & 0x7FF
    vpn1 = (gpa >> 21) & 0x1FF
    vpn0 = (gpa >> 12) & 0x1FF
    l1 = pmm.alloc_ppn()
    l0 = pmm.alloc_ppn()
    leaf_ppn = pmm.alloc_ppn()
    tester.ram.write((s2_root << 12) + vpn2 * 8, PteFactory.non_leaf(ppn=l1))
    tester.ram.write((l1 << 12) + vpn1 * 8, PteFactory.non_leaf(ppn=l0))
    # S2 leaf with reserved bits set
    tester.ram.write((l0 << 12) + vpn0 * 8,
                     PteFactory.build(v=1, r=1, w=1, u=1, a=1, d=1,
                                      ppn=leaf_ppn, reserved=0x1))

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T32: expected ERROR, got {result}"
    assert int(dut.ptw_error_2S_o.value) == 1
    assert int(dut.cause_code_o.value)   == LOAD_GUEST_PF

    dut._log.info("T32 PASS: S2 reserved bits → GUEST_PAGE_FAULT")


# ---------------------------------------------------------------------------
# T33: S2 AXI error → PT_DATA_CORRUPTION
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t33_s2_axi_error(dut):
    """T33: AXI SLVERR during S2 walk → cause_code=274. Covers: BR27, BR28."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    gpa = 0x4000_0000
    build_s2_walk(tester.ram, pmm, s2_root, gpa)

    vpn2 = (gpa >> 30) & 0x7FF
    root_pte_addr = (s2_root << 12) + vpn2 * 8
    tester.ram.inject_axi_error(root_pte_addr, resp_code=2)

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T33: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value)  == 1
    assert int(dut.cause_code_o.value) == PT_DATA_CORRUPT

    dut._log.info("T33 PASS: S2 AXI error → PT_DATA_CORRUPTION=274")


# ---------------------------------------------------------------------------
# T34: S2 non-leaf A/D/U bits
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t34_s2_nonleaf_adu(dut):
    """T34: S2 non-leaf PTE with U=1 → GUEST_PAGE_FAULT. Covers: BR23, BR29(True)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR23", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    l1 = pmm.alloc_ppn()
    gpa = 0x5000_0000
    vpn2 = (gpa >> 30) & 0x7FF
    # Non-leaf with U=1 (invalid for non-leaf)
    tester.ram.write((s2_root << 12) + vpn2 * 8,
                     PteFactory.build(v=1, r=0, w=0, x=0, u=1, ppn=l1))

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T34: expected ERROR, got {result}"
    assert int(dut.ptw_error_2S_o.value) == 1
    assert int(dut.cause_code_o.value)   == LOAD_GUEST_PF

    dut._log.info("T34 PASS: S2 non-leaf U=1 → GUEST_PAGE_FAULT")


# ---------------------------------------------------------------------------
# T35: S2 LVL3 non-leaf
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t35_s2_lvl3_nonleaf(dut):
    """T35: S2 LVL3 with R=X=0 (non-leaf at max depth). Covers: BR24, BR29(True)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR24", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    l1 = pmm.alloc_ppn()
    l0 = pmm.alloc_ppn()
    l0_target = pmm.alloc_ppn()
    gpa = 0x6000_0000
    vpn2 = (gpa >> 30) & 0x7FF
    vpn1 = (gpa >> 21) & 0x1FF
    vpn0 = (gpa >> 12) & 0x1FF
    tester.ram.write((s2_root << 12) + vpn2 * 8, PteFactory.non_leaf(ppn=l1))
    tester.ram.write((l1 << 12) + vpn1 * 8, PteFactory.non_leaf(ppn=l0))
    tester.ram.write((l0 << 12) + vpn0 * 8, PteFactory.non_leaf(ppn=l0_target))

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T35: expected ERROR, got {result}"
    assert int(dut.ptw_error_2S_o.value) == 1
    assert int(dut.cause_code_o.value)   == LOAD_GUEST_PF

    dut._log.info("T35 PASS: S2 LVL3 non-leaf → GUEST_PAGE_FAULT")


# ---------------------------------------------------------------------------
# T36: S2 superpage misalignment
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t36_s2_superpage_misalign(dut):
    """T36: S2 1G/2M leaf with misaligned PPN. Covers: BR16, BR17, BR29(True)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    # 1G misaligned
    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    gpa = 0x4000_0000
    vpn2 = (gpa >> 30) & 0x7FF
    tester.ram.write((s2_root << 12) + vpn2 * 8,
                     PteFactory.build(v=1, r=1, w=1, u=1, a=1, d=1, ppn=0x8001))

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T36/1G: expected ERROR, got {result}"
    assert int(dut.ptw_error_2S_o.value) == 1

    dut._log.info("T36 PASS: S2 superpage misalignment → GUEST_PAGE_FAULT")


# ---------------------------------------------------------------------------
# T37: S2 leaf U=0
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t37_s2_leaf_u_cleared(dut):
    """T37: S2 leaf PTE U=0 → GUEST_PAGE_FAULT. Covers: BR18, BR29(True)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR18", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    gpa = 0x7000_0000
    vpn2 = (gpa >> 30) & 0x7FF
    vpn1 = (gpa >> 21) & 0x1FF
    vpn0 = (gpa >> 12) & 0x1FF
    l1 = pmm.alloc_ppn()
    l0 = pmm.alloc_ppn()
    leaf = pmm.alloc_ppn()
    tester.ram.write((s2_root << 12) + vpn2 * 8, PteFactory.non_leaf(ppn=l1))
    tester.ram.write((l1 << 12) + vpn1 * 8, PteFactory.non_leaf(ppn=l0))
    # U=0 on S2 leaf (should be U=1 for valid S2 leaf)
    tester.ram.write((l0 << 12) + vpn0 * 8,
                     PteFactory.build(v=1, r=1, w=1, u=0, a=1, d=1, ppn=leaf))

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa, is_store=True)
    result = await tester.wait_completion()
    assert result == "ERROR", f"T37: expected ERROR for U=0 S2 leaf, got {result}"
    assert int(dut.ptw_error_2S_o.value) == 1
    assert int(dut.cause_code_o.value)   == STORE_GUEST_PF

    dut._log.info("T37 PASS: S2 leaf U=0 → GUEST_PAGE_FAULT")


# ---------------------------------------------------------------------------
# T38-T40: S2 PTW scope-out tests
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t38_s2_leaf_a_cleared(dut):
    """T38: S2 leaf A=0 – PTW succeeds (update_o=1). Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    gpa = 0x8000_0000
    build_s2_walk(tester.ram, pmm, s2_root, gpa, leaf_flags={"a": 0})

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa)
    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T38: PTW should succeed for A=0 (scope外), got {result}"
    assert int(dut.update_o.value) == 1
    dut._log.info("T38 PASS: S2 leaf A=0 → PTW update_o=1")


@cocotb.test()
async def test_t39_s2_leaf_r_cleared(dut):
    """T39: S2 leaf R=0, X=1 – PTW succeeds. Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    gpa = 0x9000_0000
    build_s2_walk(tester.ram, pmm, s2_root, gpa, leaf_flags={"r": 0, "x": 1, "w": 0})

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa)
    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T39: R=0,X=1 should succeed (scope外), got {result}"
    assert int(dut.update_o.value) == 1
    dut._log.info("T39 PASS: S2 leaf R=0,X=1 → PTW update_o=1")


@cocotb.test()
async def test_t40_s2_store_d_cleared(dut):
    """T40: S2 STORE with D=0 – PTW succeeds. Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    gpa = 0xA000_0000
    build_s2_walk(tester.ram, pmm, s2_root, gpa,
                  leaf_flags={"r": 1, "w": 1, "d": 0, "a": 1})

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa, is_store=True)
    result = await tester.wait_completion()
    assert result == "SUCCESS", f"T40: D=0 STORE should succeed (scope外), got {result}"
    assert int(dut.update_o.value) == 1
    dut._log.info("T40 PASS: S2 STORE D=0 → PTW update_o=1")


# ---------------------------------------------------------------------------
# T41: S2 fault priority
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t41_s2_fault_priority(dut):
    """T41: AXI SLVERR + invalid PTE simultaneously → cause=274. Covers: BR27, BR28."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    gpa = 0xB000_0000
    vpn2 = (gpa >> 30) & 0x7FF
    pte_addr = (s2_root << 12) + vpn2 * 8
    tester.ram.write(pte_addr, PteFactory.build(v=0))
    tester.ram.inject_axi_error(pte_addr, resp_code=2)

    await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root)
    await tester.trigger(iova=gpa)
    result = await tester.wait_completion()
    assert result == "ERROR"
    assert int(dut.cause_code_o.value) == PT_DATA_CORRUPT, \
        f"T41: AXI wins, expected {PT_DATA_CORRUPT}"

    dut._log.info("T41 PASS: S2 AXI error priority")


# ===========================================================================
# Two-stage fault tests
# ===========================================================================

def _build_nested_s1_fault(tester, iova, s2_root_ppn, s1_root_gppn, fault_level,
                            fault_type="invalid"):
    """Build nested walk structure with an injected S1 fault at the given level.

    fault_level: 1=LVL1, 2=LVL2, 3=LVL3
    fault_type: "invalid"=v=0, "reserved"=reserved bits set, "nonleaf_adu"=A/D/U on non-leaf,
                "lvl3_nonleaf"=non-leaf at LVL3
    """
    pmm_local = PhysicalMemoryManager(start_ppn=s2_root_ppn + 100)

    vpn2 = (iova >> 30) & 0x1FF
    vpn1 = (iova >> 21) & 0x1FF
    vpn0 = (iova >> 12) & 0x1FF

    # S2 mapping for S1 root
    s1_root_spa = build_s2_walk(tester.ram, pmm_local, s2_root_ppn, s1_root_gppn << 12)

    if fault_level == 1:
        # Fault at S1 root PTE (LVL1)
        if fault_type == "invalid":
            tester.ram.write(s1_root_spa + vpn2 * 8, PteFactory.build(v=0))
        elif fault_type == "reserved":
            tester.ram.write(s1_root_spa + vpn2 * 8,
                             PteFactory.build(v=1, r=0, w=0, ppn=0x2000, reserved=0x1))
        elif fault_type == "nonleaf_adu":
            tester.ram.write(s1_root_spa + vpn2 * 8,
                             PteFactory.build(v=1, r=0, w=0, x=0, a=1,
                                              ppn=pmm_local.alloc_ppn()))
        return

    # LVL1 is a valid non-leaf
    s1_l1_gppn = pmm_local.alloc_ppn()
    s1_l1_spa = build_s2_walk(tester.ram, pmm_local, s2_root_ppn, s1_l1_gppn << 12)
    tester.ram.write(s1_root_spa + vpn2 * 8, PteFactory.non_leaf(ppn=s1_l1_gppn))

    if fault_level == 2:
        if fault_type == "invalid":
            tester.ram.write(s1_l1_spa + vpn1 * 8, PteFactory.build(v=0))
        elif fault_type == "reserved":
            tester.ram.write(s1_l1_spa + vpn1 * 8,
                             PteFactory.build(v=1, r=0, w=0, ppn=0x3000, reserved=0x1))
        elif fault_type == "nonleaf_adu":
            tester.ram.write(s1_l1_spa + vpn1 * 8,
                             PteFactory.build(v=1, r=0, w=0, x=0, d=1,
                                              ppn=pmm_local.alloc_ppn()))
        return

    # LVL2 is a valid non-leaf
    s1_l0_gppn = pmm_local.alloc_ppn()
    s1_l0_spa = build_s2_walk(tester.ram, pmm_local, s2_root_ppn, s1_l0_gppn << 12)
    tester.ram.write(s1_l1_spa + vpn1 * 8, PteFactory.non_leaf(ppn=s1_l0_gppn))

    if fault_level == 3:
        if fault_type == "invalid":
            tester.ram.write(s1_l0_spa + vpn0 * 8, PteFactory.build(v=0))
        elif fault_type == "reserved":
            tester.ram.write(s1_l0_spa + vpn0 * 8,
                             PteFactory.build(v=1, r=1, ppn=0x4000, reserved=0x1))
        elif fault_type == "lvl3_nonleaf":
            tester.ram.write(s1_l0_spa + vpn0 * 8,
                             PteFactory.non_leaf(ppn=pmm_local.alloc_ppn()))


# ---------------------------------------------------------------------------
# T52: Two-stage S1/S2 invalid PTE
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t52_twostage_invalid_pte(dut):
    """T52: S1 LVL1 invalid PTE in nested walk → S1 fault (ptw_error_2S_o=0). Covers: BR09, BR29, BR30."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR09", dut)
    log_br_hit("BR30", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()    # 0x1000 (aligned)
    s1_root_gppn = 0x1001
    iova = sign_extend_sv39(0x0100_0000)

    # Build S2 mapping for S1 root, then inject S1 LVL1 fault
    _build_nested_s1_fault(tester, iova, s2_root, s1_root_gppn,
                           fault_level=1, fault_type="invalid")

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "ERROR", f"T52: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value)    == 1
    assert int(dut.ptw_error_2S_o.value) == 0, "S1 fault → ptw_error_2S_o must be 0"
    assert int(dut.cause_code_o.value)   == LOAD_PAGE_FAULT

    dut._log.info("T52 PASS: Two-stage S1 LVL1 invalid PTE → S1 fault")


# ---------------------------------------------------------------------------
# T53: Two-stage reserved bits
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t53_twostage_reserved_bits(dut):
    """T53: S1 LVL3 reserved bits in nested walk. Covers: BR25, BR29."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = 0x1001
    iova = sign_extend_sv39(0x0200_0000)

    _build_nested_s1_fault(tester, iova, s2_root, s1_root_gppn,
                           fault_level=3, fault_type="reserved")

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "ERROR", f"T53: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value)    == 1
    assert int(dut.ptw_error_2S_o.value) == 0  # S1 fault
    assert int(dut.cause_code_o.value)   == LOAD_PAGE_FAULT

    dut._log.info("T53 PASS: Two-stage S1 LVL3 reserved bits → PAGE_FAULT")


# ---------------------------------------------------------------------------
# T54: Two-stage AXI error
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t54_twostage_axi_error(dut):
    """T54: AXI SLVERR during S2-INTERMED walk → cause=274. Covers: BR27, BR28."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = 0x1001
    iova = sign_extend_sv39(0x0300_0000)

    # Compute the first S2-INTERMED fetch address for s1_root_gppn
    gpa_for_s1_root = s1_root_gppn << 12   # GPA of the S1 root page
    vpn2_s2 = (gpa_for_s1_root >> 30) & 0x7FF
    s2_intermed_pte_addr = (s2_root << 12) + vpn2_s2 * 8
    tester.ram.inject_axi_error(s2_intermed_pte_addr, resp_code=2)

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "ERROR", f"T54: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value)  == 1
    assert int(dut.cause_code_o.value) == PT_DATA_CORRUPT

    dut._log.info("T54 PASS: Two-stage AXI error → PT_DATA_CORRUPTION=274")


# ---------------------------------------------------------------------------
# T55: Two-stage non-leaf A/D/U in S1 walk
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t55_twostage_nonleaf_adu(dut):
    """T55: S1 LVL1 non-leaf with A=1 in nested walk → PAGE_FAULT. Covers: BR23, BR29, BR30."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = 0x1001
    iova = sign_extend_sv39(0x0400_0000)

    _build_nested_s1_fault(tester, iova, s2_root, s1_root_gppn,
                           fault_level=1, fault_type="nonleaf_adu")

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "ERROR", f"T55: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value)    == 1
    assert int(dut.ptw_error_2S_o.value) == 0  # S1 fault
    assert int(dut.cause_code_o.value)   == LOAD_PAGE_FAULT

    dut._log.info("T55 PASS: Two-stage S1 non-leaf ADU → PAGE_FAULT")


# ---------------------------------------------------------------------------
# T56: Two-stage LVL3 non-leaf
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t56_twostage_lvl3_nonleaf(dut):
    """T56: S1 LVL3 non-leaf in nested walk → PAGE_FAULT. Covers: BR24, BR29, BR30."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = 0x1001
    iova = sign_extend_sv39(0x0500_0000)

    _build_nested_s1_fault(tester, iova, s2_root, s1_root_gppn,
                           fault_level=3, fault_type="lvl3_nonleaf")

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "ERROR", f"T56: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value)    == 1
    assert int(dut.ptw_error_2S_o.value) == 0
    assert int(dut.cause_code_o.value)   == LOAD_PAGE_FAULT

    dut._log.info("T56 PASS: Two-stage S1 LVL3 non-leaf → PAGE_FAULT")


# ---------------------------------------------------------------------------
# T57: S1 leaf GPPN upper bits non-zero (BR26)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t57_s1_leaf_gppn_upper(dut):
    """T57: S1 leaf PPN[44:29] non-zero (GPPN upper bits) → GUEST_PAGE_FAULT. Covers: BR26, BR29, BR30."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR26", dut)
    log_br_hit("BR30", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = 0x1001
    iova = sign_extend_sv39(0x0600_0000)

    vpn2 = (iova >> 30) & 0x1FF
    vpn1 = (iova >> 21) & 0x1FF
    vpn0 = (iova >> 12) & 0x1FF

    # Build S2 mappings for the S1 walk structure
    s1_root_spa = build_s2_walk(tester.ram, pmm, s2_root, s1_root_gppn << 12)
    s1_l1_gppn = pmm.alloc_ppn()
    s1_l1_spa = build_s2_walk(tester.ram, pmm, s2_root, s1_l1_gppn << 12)
    s1_l0_gppn = pmm.alloc_ppn()
    s1_l0_spa = build_s2_walk(tester.ram, pmm, s2_root, s1_l0_gppn << 12)

    tester.ram.write(s1_root_spa + vpn2 * 8, PteFactory.non_leaf(ppn=s1_l1_gppn))
    tester.ram.write(s1_l1_spa + vpn1 * 8, PteFactory.non_leaf(ppn=s1_l0_gppn))
    # S1 leaf with PPN[44:29] != 0 (set bit 29 of PPN → bit 39 of PTE)
    bad_ppn = (1 << 29)   # PPN bit 29 set (beyond GPPNW=29)
    tester.ram.write(s1_l0_spa + vpn0 * 8,
                     PteFactory.build(v=1, r=1, w=1, a=1, d=1, ppn=bad_ppn))

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "ERROR", f"T57: expected ERROR for GPPN upper bits, got {result}"
    assert int(dut.ptw_error_o.value)        == 1
    assert int(dut.ptw_error_2S_o.value)     == 1, "ptw_error_2S_o must be 1 for GPPN fault"
    assert int(dut.ptw_error_2S_int_o.value) == 1, "ptw_error_2S_int_o must be 1 (INTERMED)"

    dut._log.info("T57 PASS: S1 leaf GPPN upper bits → GUEST_PAGE_FAULT with 2S_int")


# ---------------------------------------------------------------------------
# T58: Two-stage superpage misalignment
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t58_twostage_superpage_misalign(dut):
    """T58: S1 LVL1 1G superpage misalignment in nested walk. Covers: BR16, BR17, BR29."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = 0x1001
    iova = sign_extend_sv39(0x4000_0000)  # 1G-aligned

    vpn2 = (iova >> 30) & 0x1FF
    s1_root_spa = build_s2_walk(tester.ram, pmm, s2_root, s1_root_gppn << 12)
    # S1 LVL1 leaf with misaligned PPN
    tester.ram.write(s1_root_spa + vpn2 * 8,
                     PteFactory.build(v=1, r=1, w=1, a=1, d=1, ppn=0x8001))

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "ERROR", f"T58: expected ERROR, got {result}"
    assert int(dut.ptw_error_o.value) == 1

    dut._log.info("T58 PASS: Two-stage superpage misalign → fault")


# ---------------------------------------------------------------------------
# T59: Two-stage S2-FINAL leaf U=0
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t59_twostage_s2_leaf_u_cleared(dut):
    """T59: S2-FINAL leaf U=0 in nested walk → GUEST_PAGE_FAULT. Covers: BR18, BR29(True)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0700_0000)

    vpn2 = (iova >> 30) & 0x1FF
    vpn1 = (iova >> 21) & 0x1FF
    vpn0 = (iova >> 12) & 0x1FF

    s1_root_spa = build_s2_walk(tester.ram, pmm, s2_root, s1_root_gppn << 12)
    s1_l1_gppn = pmm.alloc_ppn()
    s1_l1_spa = build_s2_walk(tester.ram, pmm, s2_root, s1_l1_gppn << 12)
    s1_l0_gppn = pmm.alloc_ppn()
    s1_l0_spa = build_s2_walk(tester.ram, pmm, s2_root, s1_l0_gppn << 12)

    tester.ram.write(s1_root_spa + vpn2 * 8, PteFactory.non_leaf(ppn=s1_l1_gppn))
    tester.ram.write(s1_l1_spa + vpn1 * 8, PteFactory.non_leaf(ppn=s1_l0_gppn))

    # S1 leaf points to final_gppn in GPA space.
    # Use VPN[2]=1 range (>=0x40000) so S2-FINAL root slot != S2-INTERMED slot (VPN[2]=0).
    final_gppn = 0x40010
    tester.ram.write(s1_l0_spa + vpn0 * 8,
                     PteFactory.build(v=1, r=1, w=1, a=1, d=1, ppn=final_gppn))

    # S2-FINAL for final_gppn with U=0 (invalid for S2 leaf)
    final_gpa = final_gppn << 12
    vpn2f = (final_gpa >> 30) & 0x7FF
    vpn1f = (final_gpa >> 21) & 0x1FF
    vpn0f = (final_gpa >> 12) & 0x1FF
    l1f = pmm.alloc_ppn()
    l0f = pmm.alloc_ppn()
    leaff = pmm.alloc_ppn()
    tester.ram.write((s2_root << 12) + vpn2f * 8, PteFactory.non_leaf(ppn=l1f))
    tester.ram.write((l1f << 12) + vpn1f * 8, PteFactory.non_leaf(ppn=l0f))
    tester.ram.write((l0f << 12) + vpn0f * 8,
                     PteFactory.build(v=1, r=1, w=1, u=0, a=1, d=1, ppn=leaff))  # U=0!

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "ERROR", f"T59: expected ERROR for S2-FINAL U=0, got {result}"
    assert int(dut.ptw_error_o.value)        == 1
    assert int(dut.ptw_error_2S_o.value)     == 1
    assert int(dut.ptw_error_2S_int_o.value) == 0  # FINAL, not INTERMED

    dut._log.info("T59 PASS: Two-stage S2-FINAL U=0 → GUEST_PAGE_FAULT")


# ---------------------------------------------------------------------------
# T60-T62: Two-stage PTW scope-out tests
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t60_twostage_leaf_a_cleared(dut):
    """T60: Two-stage with S1 leaf A=0 – PTW succeeds. Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0800_0000)
    build_nested_walk(tester.ram, pmm, s1_root_gppn, s2_root, iova,
                      s1_leaf_flags={"a": 0, "d": 1})

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "SUCCESS", f"T60: PTW should succeed (A=0 scope外), got {result}"
    assert int(dut.update_o.value) == 1
    dut._log.info("T60 PASS: Two-stage S1 leaf A=0 → PTW update_o=1")


@cocotb.test()
async def test_t61_twostage_leaf_r_cleared(dut):
    """T61: Two-stage with S1 leaf R=0, X=1 – PTW succeeds. Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0900_0000)
    build_nested_walk(tester.ram, pmm, s1_root_gppn, s2_root, iova,
                      s1_leaf_flags={"r": 0, "x": 1, "w": 0})

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "SUCCESS", f"T61: R=0,X=1 should succeed (scope外), got {result}"
    assert int(dut.update_o.value) == 1
    dut._log.info("T61 PASS: Two-stage S1 leaf R=0,X=1 → PTW update_o=1")


@cocotb.test()
async def test_t62_twostage_store_d_cleared(dut):
    """T62: Two-stage with S1 leaf D=0, is_store=1 – PTW succeeds. Covers: (scope外)."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = pmm.alloc_ppn()
    iova = sign_extend_sv39(0x0A00_0000)
    build_nested_walk(tester.ram, pmm, s1_root_gppn, s2_root, iova,
                      s1_leaf_flags={"r": 1, "w": 1, "d": 0, "a": 1})

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova, is_store=True)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "SUCCESS", f"T62: STORE D=0 should succeed (scope外), got {result}"
    assert int(dut.update_o.value) == 1
    dut._log.info("T62 PASS: Two-stage STORE D=0 → PTW update_o=1")


# ---------------------------------------------------------------------------
# T63: Two-stage fault priority
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t63_twostage_fault_priority(dut):
    """T63: AXI SLVERR during S2-INTERMED → cause=274. Covers: BR27, BR28."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    s1_root_gppn = 0x1001
    iova = sign_extend_sv39(0x0B00_0000)

    gpa_for_s1_root = s1_root_gppn << 12
    vpn2_s2 = (gpa_for_s1_root >> 30) & 0x7FF
    s2_pte_addr = (s2_root << 12) + vpn2_s2 * 8
    # Both invalid and AXI error → AXI error wins
    tester.ram.write(s2_pte_addr, PteFactory.build(v=0))
    tester.ram.inject_axi_error(s2_pte_addr, resp_code=2)

    await tester.configure(en_1S=1, en_2S=1,
                           iosatp_ppn=s1_root_gppn,
                           iohgatp_ppn=s2_root)
    await tester.trigger(iova=iova)
    result = await tester.wait_completion(timeout_cycles=400)
    assert result == "ERROR", f"T63: expected ERROR, got {result}"
    assert int(dut.cause_code_o.value) == PT_DATA_CORRUPT

    dut._log.info("T63 PASS: Two-stage AXI error priority → PT_DATA_CORRUPTION")


# ---------------------------------------------------------------------------
# T72: CDW implicit error
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_t72_cdw_implicit_error(dut):
    """T72: CDW implicit access with S2 invalid PTE → ptw_error_o=1, flush_cdw_o=1. Covers: BR03, BR31."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    log_br_hit("BR31", dut)

    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s2_root = pmm.alloc_ppn()
    pdt_gppn = 0xC    # GPA = 0xC000

    # Place invalid PTE at the S2 root entry for pdt_gppn
    gpa = pdt_gppn << 12
    vpn2 = (gpa >> 30) & 0x7FF
    tester.ram.write((s2_root << 12) + vpn2 * 8, PteFactory.build(v=0))

    dut.en_1S_i.value               = 0
    dut.en_2S_i.value               = 1
    dut.iohgatp_ppn_i.value         = s2_root
    dut.pdt_gppn_i.value            = pdt_gppn
    dut.cdw_implicit_access_i.value = 0
    await RisingEdge(dut.clk_i)

    dut.cdw_implicit_access_i.value = 1
    await RisingEdge(dut.clk_i)

    for _ in range(150):
        await RisingEdge(dut.clk_i)
        await ReadOnly()
        if int(dut.ptw_error_o.value) == 1:
            assert int(dut.flush_cdw_o.value) == 1, \
                f"T72: flush_cdw_o must be 1 on CDW error, got {int(dut.flush_cdw_o.value)}"
            dut._log.info("T72 PASS: CDW implicit error → flush_cdw_o=1")
            return
        if int(dut.cdw_done_o.value) == 1:
            assert False, "T72: CDW unexpectedly succeeded with invalid S2 PTE"
    assert False, "T72: Timeout waiting for CDW error"
