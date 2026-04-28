"""Random tests for rv_iommu_ptw_sv39x4_pc.
R01: S1-only random (100 cases, seed=42)
R02: S2-only random (100 cases, seed=43)
R03: Two-stage random (100 cases, seed=44)
"""

import random

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly

from tb_coco.common.helpers import (
    PTWTester, PhysicalMemoryManager, PteFactory,
    build_s1_walk, build_s2_walk, build_nested_walk,
    translate_sv39_golden, sign_extend_sv39,
    gen_random_iova_sv39, gen_random_gpa_sv39x4, gen_random_pte_flags,
)

NUM_CASES = 100


async def _setup(dut):
    dut.mem_ar_ready_i.value         = 1
    dut.cdw_implicit_access_i.value  = 0
    dut.pscid_i.value               = 0
    dut.gscid_i.value               = 0
    dut.msi_en_i.value              = 0
    dut.msi_addr_mask_i.value       = 0
    dut.msi_addr_pattern_i.value    = 0
    dut.pdt_gppn_i.value            = 0


# ---------------------------------------------------------------------------
# R01: S1-only random walk
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_r01_s1_random(dut):
    """R01: 100 random S1-only walks with various IOVAs. Seed=42."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    rng = random.Random(42)
    pmm = PhysicalMemoryManager(start_ppn=0x1000)
    s1_root_ppn = pmm.alloc_ppn()

    passes = 0
    for i in range(NUM_CASES):
        iova_raw = rng.randrange(0, 1 << 39)
        iova = sign_extend_sv39(iova_raw)
        is_store = rng.randint(0, 1) == 1

        # Build a valid S1 page table entry for this IOVA
        build_s1_walk(tester.ram, pmm, s1_root_ppn, iova)

        golden = translate_sv39_golden(
            iova=iova, ram_mem=tester.ram.mem,
            s1_root_ppn=s1_root_ppn, en_1S=1, en_2S=0,
            is_store=is_store
        )

        await tester.configure(en_1S=1, en_2S=0, iosatp_ppn=s1_root_ppn)
        await tester.trigger(iova=iova, is_store=is_store)
        result = await tester.wait_completion()

        if golden["result"] == "SUCCESS":
            assert result == "SUCCESS", \
                f"R01[{i}]: golden=SUCCESS but DUT={result} (iova={hex(iova)})"
            assert int(dut.update_o.value) == 1, f"R01[{i}]: update_o=0"
            passes += 1
        else:
            assert result == "ERROR", \
                f"R01[{i}]: golden=FAULT but DUT={result} (iova={hex(iova)})"
            await ReadOnly()
            assert int(dut.ptw_error_o.value) == 1, f"R01[{i}]: ptw_error_o=0"

        # Clock edge between iterations (cocotb v2 ReadOnly phase requirement)
        await RisingEdge(dut.clk_i)

    dut._log.info(f"R01 PASS: {passes}/{NUM_CASES} cases resulted in SUCCESS")


# ---------------------------------------------------------------------------
# R02: S2-only random walk
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_r02_s2_random(dut):
    """R02: 100 random S2-only walks with various GPAs. Seed=43."""
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    rng = random.Random(43)
    pmm = PhysicalMemoryManager(start_ppn=0x5000)
    s2_root_ppn = pmm.alloc_ppn()

    passes = 0
    for i in range(NUM_CASES):
        gpa = rng.randrange(0, 1 << 41) & ~0xFFF   # page-aligned GPA
        is_store = rng.randint(0, 1) == 1

        build_s2_walk(tester.ram, pmm, s2_root_ppn, gpa)

        golden = translate_sv39_golden(
            iova=gpa, ram_mem=tester.ram.mem,
            s1_root_ppn=0, en_1S=0, en_2S=1,
            iohgatp_ppn=s2_root_ppn,
            is_store=is_store
        )

        await tester.configure(en_1S=0, en_2S=1, iohgatp_ppn=s2_root_ppn)
        await tester.trigger(iova=gpa, is_store=is_store)
        result = await tester.wait_completion()

        if golden["result"] == "SUCCESS":
            assert result == "SUCCESS", \
                f"R02[{i}]: golden=SUCCESS but DUT={result} (gpa={hex(gpa)})"
            assert int(dut.update_o.value) == 1, f"R02[{i}]: update_o=0"
            passes += 1
        elif golden["result"] == "GUEST_PAGE_FAULT":
            assert result == "ERROR", \
                f"R02[{i}]: golden=FAULT but DUT={result} (gpa={hex(gpa)})"

        await RisingEdge(dut.clk_i)

    dut._log.info(f"R02 PASS: {passes}/{NUM_CASES} cases resulted in SUCCESS")


# ---------------------------------------------------------------------------
# R03: Two-stage random walk
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_r03_twostage_random(dut):
    """R03: 100 random two-stage nested walks. Seed=44.
    Note: translate_sv39_golden returns UNSUPPORTED for en_1S=1+en_2S=1.
    Expectation: DUT completes with update_o=1 for all valid nested walks.
    """
    tester = PTWTester(dut)
    await _setup(dut)
    await tester.reset()

    rng = random.Random(44)

    for i in range(NUM_CASES):
        iova_raw = rng.randrange(0, 1 << 39)
        iova = sign_extend_sv39(iova_raw)

        pmm = PhysicalMemoryManager(start_ppn=0x8000 + i * 0x200)
        s2_root = pmm.alloc_ppn()    # first alloc has bits[1:0]=0 ✓
        s1_root_gppn = pmm.alloc_ppn()

        build_nested_walk(tester.ram, pmm, s1_root_gppn, s2_root, iova)

        await tester.configure(en_1S=1, en_2S=1,
                               iosatp_ppn=s1_root_gppn,
                               iohgatp_ppn=s2_root)
        await tester.trigger(iova=iova)
        result = await tester.wait_completion(timeout_cycles=400)
        assert result == "SUCCESS", \
            f"R03[{i}]: nested walk failed with {result} (iova={hex(iova)})"
        assert int(dut.update_o.value) == 1, f"R03[{i}]: update_o=0"

        await RisingEdge(dut.clk_i)

    dut._log.info(f"R03 PASS: all {NUM_CASES} two-stage random walks succeeded")
