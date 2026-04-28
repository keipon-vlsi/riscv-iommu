"""
PTW testbench helpers.

Contents:
  - PTE bit-level utilities (decode, IOVA sign-extension)
  - PteFactory: build Sv39/Sv39x4 PTE values
  - PhysicalMemoryManager: sequential PPN allocator
  - Page table builders for S1-only / S2-only / nested (S1+S2) walks
  - MockMemory: AXI-lite read responder
  - PTWTester: drives the DUT inputs and polls completion
"""

import logging
import random as _rnd_mod

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


# =============================================================================
# Logging
# =============================================================================
def setup_file_logger(filename: str = "ptw_test.log") -> None:
    """Mirror cocotb logger output to a file."""
    log = logging.getLogger("cocotb")
    for h in log.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename.endswith(filename):
            return
    fh = logging.FileHandler(filename, mode="w")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(fh)


# =============================================================================
# PTE bit-level utilities
# =============================================================================
def decode_pte(dut, pte_val: int, name: str = "PTE") -> None:
    """Log a human-readable dump of a PTE."""
    v   =  pte_val        & 0x1
    r   = (pte_val >> 1)  & 0x1
    w   = (pte_val >> 2)  & 0x1
    x   = (pte_val >> 3)  & 0x1
    u   = (pte_val >> 4)  & 0x1
    g   = (pte_val >> 5)  & 0x1
    a   = (pte_val >> 6)  & 0x1
    d   = (pte_val >> 7)  & 0x1
    ppn = (pte_val >> 10) & 0xFFFFFFFFFFF
    dut._log.info(
        f"  [{name}] raw={hex(pte_val)} ppn={hex(ppn)} "
        f"V:{v} R:{r} W:{w} X:{x} U:{u} G:{g} A:{a} D:{d}"
    )


def sign_extend_sv39(iova_39: int) -> int:
    """Sign-extend a 39-bit IOVA to 64 bits (Sv39 canonical form)."""
    iova_39 &= 0x7FFFFFFFFF
    if (iova_39 >> 38) & 1:
        return iova_39 | 0xFFFFFF8000000000
    return iova_39


# =============================================================================
# PTE factory
# =============================================================================
class PteFactory:
    """Build Sv39 / Sv39x4 page table entries."""

    @staticmethod
    def build(v=1, r=0, w=0, x=0, u=0, g=0, a=0, d=0,
              rsw=0, ppn=0, reserved=0) -> int:
        return (
             (v & 1)
            | ((r & 1) << 1)
            | ((w & 1) << 2)
            | ((x & 1) << 3)
            | ((u & 1) << 4)
            | ((g & 1) << 5)
            | ((a & 1) << 6)
            | ((d & 1) << 7)
            | ((rsw & 0x3) << 8)
            | ((ppn & 0xFFFFFFFFFFF) << 10)
            | ((reserved & 0x3FF) << 54)
        )

    @classmethod
    def non_leaf(cls, ppn: int) -> int:
        """Non-leaf PTE (V=1, R=W=X=0). Same format for S1 and S2."""
        return cls.build(v=1, ppn=ppn)

    @classmethod
    def s1_leaf(cls, ppn: int, r=1, w=1, x=0, u=0, a=1, d=1) -> int:
        """Stage-1 leaf PTE. Default: kernel R/W data page."""
        return cls.build(v=1, r=r, w=w, x=x, u=u, a=a, d=d, ppn=ppn)

    @classmethod
    def s2_leaf(cls, ppn: int, r=1, w=1, x=0, a=1, d=1) -> int:
        """Stage-2 (G-stage) leaf PTE. U-bit is always 1."""
        return cls.build(v=1, r=r, w=w, x=x, u=1, a=a, d=d, ppn=ppn)

    @staticmethod
    def invalid() -> int:
        """Invalid PTE (V=0)."""
        return 0


# =============================================================================
# PPN allocator
# =============================================================================
class PhysicalMemoryManager:
    """Sequential PPN allocator for laying out page tables in memory."""

    def __init__(self, start_ppn: int = 0x1000):
        self._next = start_ppn

    def alloc_ppn(self) -> int:
        ppn = self._next
        self._next += 1
        return ppn


# =============================================================================
# Page table layout builders
# =============================================================================
def _pte_is_valid_non_leaf(pte: int) -> bool:
    """V=1 and R=W=X=0."""
    return (pte & 0x1) == 1 and (pte & 0b1110) == 0


def _get_or_alloc_next(ram, pmm: PhysicalMemoryManager, pte_addr: int) -> int:
    """Return the PPN pointed to by the non-leaf PTE at pte_addr.
    Create one if the slot is empty or not a valid non-leaf."""
    existing = ram.mem.get(pte_addr, 0)
    if _pte_is_valid_non_leaf(existing):
        return (existing >> 10) & 0xFFFFFFFFFFF
    ppn = pmm.alloc_ppn()
    ram.write(pte_addr, PteFactory.non_leaf(ppn=ppn))
    return ppn


def build_s1_walk(ram, pmm: PhysicalMemoryManager, root_ppn: int,
                  iova: int, target_pa: int = None,
                  leaf_flags: dict = None) -> int:
    """Lay out a 3-level Sv39 S1 page table so that `iova` resolves to `target_pa`.

    Args:
        ram:        MockMemory instance.
        pmm:        PhysicalMemoryManager.
        root_ppn:   S1 root page table PPN (iosatp.ppn).
                    Interpreted as SPA when S2 is disabled.
        iova:       39-bit input virtual address.
        target_pa:  Desired output PA. A new page is allocated if None.
        leaf_flags: Optional dict with r/w/x/u/a/d overrides for the leaf PTE.

    Returns:
        The PA that the leaf PTE points to.
    """
    vpn2 = (iova >> 30) & 0x1FF
    vpn1 = (iova >> 21) & 0x1FF
    vpn0 = (iova >> 12) & 0x1FF

    l2_addr = (root_ppn << 12) + vpn2 * 8
    l1_ppn  = _get_or_alloc_next(ram, pmm, l2_addr)

    l1_addr = (l1_ppn << 12) + vpn1 * 8
    l0_ppn  = _get_or_alloc_next(ram, pmm, l1_addr)

    l0_addr = (l0_ppn << 12) + vpn0 * 8
    if target_pa is None:
        target_pa = pmm.alloc_ppn() << 12

    flags = {"r": 1, "w": 1, "x": 0, "u": 0, "a": 1, "d": 1}
    if leaf_flags:
        flags.update(leaf_flags)
    ram.write(l0_addr, PteFactory.s1_leaf(ppn=target_pa >> 12, **flags))

    return target_pa


def build_s2_walk(ram, pmm: PhysicalMemoryManager, root_ppn: int,
                  gpa: int, target_spa: int = None,
                  leaf_flags: dict = None) -> int:
    """Lay out a 3-level Sv39x4 S2 page table so that `gpa` resolves to `target_spa`.

    Note: Sv39x4 has an 11-bit VPN[2] (gpa[40:30]), wider than Sv39's 9 bits.
    """
    vpn2 = (gpa >> 30) & 0x7FF          # 11 bits for Sv39x4
    vpn1 = (gpa >> 21) & 0x1FF
    vpn0 = (gpa >> 12) & 0x1FF

    l2_addr = (root_ppn << 12) + vpn2 * 8
    l1_ppn  = _get_or_alloc_next(ram, pmm, l2_addr)

    l1_addr = (l1_ppn << 12) + vpn1 * 8
    l0_ppn  = _get_or_alloc_next(ram, pmm, l1_addr)

    l0_addr = (l0_ppn << 12) + vpn0 * 8
    if target_spa is None:
        target_spa = pmm.alloc_ppn() << 12

    flags = {"r": 1, "w": 1, "x": 0, "a": 1, "d": 1}
    if leaf_flags:
        flags.update(leaf_flags)
    ram.write(l0_addr, PteFactory.s2_leaf(ppn=target_spa >> 12, **flags))

    return target_spa


# Backward-compatible alias.
map_s2_page = build_s2_walk


def build_nested_walk(ram, pmm: PhysicalMemoryManager,
                      s1_root_gppn: int, s2_root_ppn: int, iova: int,
                      final_spa: int = None,
                      s1_leaf_flags: dict = None) -> int:
    """Lay out a full nested (S1+S2) translation for `iova`.

    With both stages enabled, every S1 PTE fetch must be S2-translated first.
    This builder:
      1. Places the S1 root page in GPA space and adds an S2 mapping for it.
      2. Allocates S1 L1 / L0 pages in GPA space and maps each via S2.
      3. Writes the S1 root / L1 / leaf PTEs.
      4. Allocates the final data page and maps its GPA to `final_spa` via S2.

    Args:
        s1_root_gppn: GPA PPN of the S1 root. Assigned to iosatp.ppn by the DUT.
        s2_root_ppn:  SPA PPN of the S2 root. Assigned to iohgatp.ppn.
        iova:         39-bit input virtual address.
        final_spa:    Desired host PA of the translated page. Alloc new if None.

    Returns:
        The final SPA the translation should resolve to.
    """
    vpn2 = (iova >> 30) & 0x1FF
    vpn1 = (iova >> 21) & 0x1FF
    vpn0 = (iova >> 12) & 0x1FF

    # 1. S2 mapping for the S1 root page
    s1_root_spa = build_s2_walk(ram, pmm, s2_root_ppn, s1_root_gppn << 12)

    # 2. S1 L1 page (in GPA), its S2 mapping, and S1 root -> L1 non-leaf PTE
    s1_l1_gppn = pmm.alloc_ppn()
    s1_l1_spa  = build_s2_walk(ram, pmm, s2_root_ppn, s1_l1_gppn << 12)
    ram.write(s1_root_spa + vpn2 * 8, PteFactory.non_leaf(ppn=s1_l1_gppn))

    # 3. S1 L0 page
    s1_l0_gppn = pmm.alloc_ppn()
    s1_l0_spa  = build_s2_walk(ram, pmm, s2_root_ppn, s1_l0_gppn << 12)
    ram.write(s1_l1_spa + vpn1 * 8, PteFactory.non_leaf(ppn=s1_l0_gppn))

    # 4. Final data page in GPA + S2 mapping + S1 leaf PTE
    final_gppn = pmm.alloc_ppn()
    if final_spa is None:
        final_spa = pmm.alloc_ppn() << 12
    build_s2_walk(ram, pmm, s2_root_ppn, final_gppn << 12, target_spa=final_spa)

    flags = {"r": 1, "w": 1, "x": 0, "u": 0, "a": 1, "d": 1}
    if s1_leaf_flags:
        flags.update(s1_leaf_flags)
    ram.write(s1_l0_spa + vpn0 * 8, PteFactory.s1_leaf(ppn=final_gppn, **flags))

    return final_spa


# =============================================================================
# Mock memory (AXI-lite read responder)
# =============================================================================
class MockMemory:
    """Single-beat read responder backed by a dict."""

    def __init__(self, dut):
        self.dut = dut
        self.mem = {}                # addr -> 64-bit data
        self.error_addresses = {}    # addr -> RRESP code (0=OKAY)
        cocotb.start_soon(self._serve())

    def write(self, addr: int, data: int) -> None:
        self.mem[addr] = data
        self.dut._log.info(f"  [MockMem] write {hex(addr)} = {hex(data)}")

    def inject_axi_error(self, addr: int, resp_code: int = 2) -> None:
        """Return a non-OKAY RRESP when this address is read (default SLVERR=2)."""
        self.error_addresses[addr] = resp_code

    async def _serve(self):
        # Initial values
        self.dut.mem_rd_resp_valid_i.value = 0
        self.dut.mem_rd_resp_data_i.value  = 0
        has_resp = hasattr(self.dut, "mem_rd_resp_resp_i")
        if has_resp:
            self.dut.mem_rd_resp_resp_i.value = 0

        next_valid = 0
        next_data  = 0
        next_resp  = 0

        while True:
            await RisingEdge(self.dut.clk_i)
            self.dut.mem_rd_resp_valid_i.value = next_valid
            self.dut.mem_rd_resp_data_i.value  = next_data
            if has_resp:
                self.dut.mem_rd_resp_resp_i.value = next_resp

            await ReadOnly()

            # Deassert VALID once the handshake completes
            if (int(self.dut.mem_rd_resp_valid_i.value) == 1
                    and int(self.dut.mem_rd_resp_ready_o.value) == 1):
                next_valid = 0

            # Accept a new request
            if int(self.dut.mem_rd_req_valid_o.value) == 1:
                addr = int(self.dut.mem_rd_req_addr_o.value)
                data = self.mem.get(addr, 0)
                resp = self.error_addresses.get(addr, 0)

                if resp != 0:
                    self.dut._log.warning(
                        f"  [AXI] read {hex(addr)} -> injected error (resp={resp})"
                    )
                else:
                    self.dut._log.info(
                        f"  [AXI] read {hex(addr)} -> {hex(data)}"
                    )
                decode_pte(self.dut, data, name=f"fetched@{hex(addr)}")

                next_valid = 1
                next_data  = data
                next_resp  = resp


# =============================================================================
# DUT driver
# =============================================================================
class PTWTester:
    """Reset, configure, trigger and observe the PTW DUT."""

    def __init__(self, dut):
        self.dut = dut
        self.ram = MockMemory(dut)
        cocotb.start_soon(Clock(dut.clk_i, 10, unit="ns").start())

    async def reset(self, cycles: int = 5):
        """Hold reset for a few cycles and set inputs to safe defaults."""
        self.dut.rst_ni.value        = 0
        self.dut.init_ptw_i.value    = 0
        self.dut.iosatp_ppn_i.value  = 0
        self.dut.iohgatp_ppn_i.value = 0
        self.dut.req_iova_i.value    = 0
        self.dut.en_1S_i.value       = 0
        self.dut.en_2S_i.value       = 0
        if hasattr(self.dut, "is_store_i"):
            self.dut.is_store_i.value = 0

        for _ in range(cycles):
            await RisingEdge(self.dut.clk_i)
        self.dut.rst_ni.value = 1
        for _ in range(cycles):
            await RisingEdge(self.dut.clk_i)

    async def configure(self, en_1S: int = 0, en_2S: int = 0,
                        iosatp_ppn: int = 0, iohgatp_ppn: int = 0):
        """Set stage enables and root PPNs. Call before trigger()."""
        self.dut.en_1S_i.value       = en_1S
        self.dut.en_2S_i.value       = en_2S
        self.dut.iosatp_ppn_i.value  = iosatp_ppn
        self.dut.iohgatp_ppn_i.value = iohgatp_ppn
        await RisingEdge(self.dut.clk_i)

    async def trigger(self, iova: int, is_store: bool = False):
        """Pulse init_ptw_i for one cycle to start a walk."""
        self.dut.req_iova_i.value = iova
        if hasattr(self.dut, "is_store_i"):
            self.dut.is_store_i.value = 1 if is_store else 0
        await RisingEdge(self.dut.clk_i)
        self.dut.init_ptw_i.value = 1
        await RisingEdge(self.dut.clk_i)
        self.dut.init_ptw_i.value = 0

    async def wait_completion(self, timeout_cycles: int = 200) -> str:
        """Wait for update_o or ptw_error_o.

        Returns:
            "SUCCESS" | "ERROR" | "TIMEOUT"
        """
        for _ in range(timeout_cycles):
            await RisingEdge(self.dut.clk_i)
            await ReadOnly()
            if int(self.dut.ptw_error_o.value) == 1:
                return "ERROR"
            if int(self.dut.update_o.value) == 1:
                return "SUCCESS"
        return "TIMEOUT"


# =============================================================================
# Random generators
# =============================================================================

def gen_random_iova_sv39(seed=None) -> int:
    """Return a canonical (sign-extended) 39-bit IOVA."""
    rng = _rnd_mod.Random(seed)
    raw = rng.randrange(0, 1 << 39)
    return sign_extend_sv39(raw)


def gen_random_gpa_sv39x4(seed=None) -> int:
    """Return a 41-bit Guest Physical Address (Sv39x4 range)."""
    rng = _rnd_mod.Random(seed)
    return rng.randrange(0, 1 << 41)


def gen_random_pte_flags(kind: str = "s1_leaf",
                          allow_invalid: bool = False,
                          seed=None) -> dict:
    """Return a dict of PTE flag bits suitable for PteFactory.build().

    kind:
        "s1_leaf"  – V=1, at least R=1 or X=1, W requires R
        "s2_leaf"  – V=1, U=1, at least R=1
        "non_leaf" – V=1, R=W=X=0 (pointer)
    allow_invalid:
        When True, may return V=0 (invalid PTE) ~10 % of the time.
    """
    rng = _rnd_mod.Random(seed)

    if allow_invalid and rng.random() < 0.1:
        return {"v": 0, "r": 0, "w": 0, "x": 0, "u": 0, "a": 1, "d": 1}

    if kind == "non_leaf":
        return {"v": 1, "r": 0, "w": 0, "x": 0, "u": 0, "a": 0, "d": 0}

    if kind == "s2_leaf":
        r = rng.randint(0, 1)
        x = rng.randint(0, 1)
        if r == 0 and x == 0:
            r = 1
        w = rng.randint(0, 1) if r else 0
        return {"v": 1, "r": r, "w": w, "x": x, "u": 1, "a": 1, "d": 1}

    # s1_leaf (default)
    r = rng.randint(0, 1)
    x = rng.randint(0, 1)
    if r == 0 and x == 0:
        r = 1
    w = rng.randint(0, 1) if r else 0
    u = rng.randint(0, 1)
    return {"v": 1, "r": r, "w": w, "x": x, "u": u, "a": 1, "d": 1}


# =============================================================================
# Python golden model
# =============================================================================

_PTE_V = 1 << 0
_PTE_R = 1 << 1
_PTE_W = 1 << 2
_PTE_X = 1 << 3


def _pte_ppn(pte: int) -> int:
    return (pte >> 10) & 0xFFFFFFFFFFF   # 44-bit PPN field


def _walk_sv39(iova: int, ram: dict, root_ppn: int, vpn2_bits: int = 9) -> dict:
    """One-stage Sv39 / Sv39x4 walk on a Python dict-backed RAM.

    vpn2_bits=9  → Sv39   (S1 stage, VPN2 = iova[38:30])
    vpn2_bits=11 → Sv39x4 (S2/G-stage, VPN2 = gpa[40:30], 2048-entry root)

    Returns:
        fault        : bool
        pte          : raw 64-bit PTE of the leaf (0 if fault before first PTE)
        pa           : physical address (0 on fault)
        superpage_2M : bool
        superpage_1G : bool
    """
    vpn2_mask = (1 << vpn2_bits) - 1
    vpn = [(iova >> 12) & 0x1FF,
           (iova >> 21) & 0x1FF,
           (iova >> 30) & vpn2_mask]
    pptr = (root_ppn << 12) + vpn[2] * 8

    for level in range(2, -1, -1):
        pte = ram.get(pptr, 0)
        if not (pte & _PTE_V):
            return {"fault": True, "pte": pte, "pa": 0,
                    "superpage_2M": False, "superpage_1G": False}
        if (pte & _PTE_W) and not (pte & _PTE_R):
            return {"fault": True, "pte": pte, "pa": 0,
                    "superpage_2M": False, "superpage_1G": False}
        if pte & (_PTE_R | _PTE_X):
            ppn = _pte_ppn(pte)
            if level == 2:
                pa = (ppn << 12) | (iova & 0x3FFFFFFF)
                return {"fault": False, "pte": pte, "pa": pa,
                        "superpage_2M": False, "superpage_1G": True}
            if level == 1:
                pa = (ppn << 12) | (iova & 0x1FFFFF)
                return {"fault": False, "pte": pte, "pa": pa,
                        "superpage_2M": True, "superpage_1G": False}
            pa = (ppn << 12) | (iova & 0xFFF)
            return {"fault": False, "pte": pte, "pa": pa,
                    "superpage_2M": False, "superpage_1G": False}
        next_ppn = _pte_ppn(pte)
        pptr = (next_ppn << 12) + vpn[level - 1] * 8

    return {"fault": True, "pte": 0, "pa": 0,
            "superpage_2M": False, "superpage_1G": False}


def translate_sv39_golden(iova: int, ram_mem: dict,
                           s1_root_ppn: int = 0,
                           en_1S: int = 1, en_2S: int = 0,
                           iohgatp_ppn: int = 0,
                           is_store: bool = False) -> dict:
    """Software golden model for PTW translate.

    Supports S1-only (en_1S=1, en_2S=0) and S2-only (en_1S=0, en_2S=1).
    Nested (en_1S=1, en_2S=1) returns result="UNSUPPORTED".

    Returns:
        result      : "SUCCESS" | "PAGE_FAULT" | "GUEST_PAGE_FAULT" | "UNSUPPORTED"
        pa          : int – final physical address (0 on fault)
        leaf_1s_pte : int – raw S1 leaf PTE (0 if not walked)
        leaf_2s_pte : int – raw S2 leaf PTE (0 if not walked)
        cause       : int – RISC-V cause code (0 on success)
    """
    LOAD_PAGE_FAULT    = 13
    STORE_PAGE_FAULT   = 15
    LOAD_GUEST_PF      = 21
    STORE_GUEST_PF     = 23

    pf_cause  = STORE_PAGE_FAULT   if is_store else LOAD_PAGE_FAULT
    gpf_cause = STORE_GUEST_PF     if is_store else LOAD_GUEST_PF

    if en_1S and en_2S:
        return {"result": "UNSUPPORTED", "pa": 0,
                "leaf_1s_pte": 0, "leaf_2s_pte": 0, "cause": 0}

    if en_1S and not en_2S:
        r = _walk_sv39(iova, ram_mem, s1_root_ppn)
        if r["fault"]:
            return {"result": "PAGE_FAULT", "pa": 0,
                    "leaf_1s_pte": r["pte"], "leaf_2s_pte": 0,
                    "cause": pf_cause}
        return {"result": "SUCCESS", "pa": r["pa"],
                "leaf_1s_pte": r["pte"], "leaf_2s_pte": 0, "cause": 0}

    if not en_1S and en_2S:
        # S2-only: IOVA treated as GPA (41-bit Sv39x4); use 4-aligned root.
        # Use vpn2_bits=11 to match the hardware's 2048-entry root (gpa[40:30]).
        gpa       = iova & 0x1FFFFFFFFFF
        s2_root   = iohgatp_ppn & ~0x3
        r = _walk_sv39(gpa, ram_mem, s2_root, vpn2_bits=11)
        if r["fault"]:
            return {"result": "GUEST_PAGE_FAULT", "pa": 0,
                    "leaf_1s_pte": 0, "leaf_2s_pte": r["pte"],
                    "cause": gpf_cause}
        return {"result": "SUCCESS", "pa": r["pa"],
                "leaf_1s_pte": 0, "leaf_2s_pte": r["pte"], "cause": 0}

    # Both disabled — pass-through
    return {"result": "SUCCESS", "pa": iova & 0xFFFFFFFFFFFF,
            "leaf_1s_pte": 0, "leaf_2s_pte": 0, "cause": 0}


# =============================================================================
# BR coverage tracking
# =============================================================================

_br_hits: dict = {}


def log_br_hit(br_id: str, dut) -> None:
    """Record that a branch condition was exercised in this simulation."""
    _br_hits[br_id] = _br_hits.get(br_id, 0) + 1
    dut._log.info(f"  [BR HIT] {br_id}")


def report_br_coverage(dut, expected_brs: list) -> None:
    """Log which expected BRs were hit and which were missed."""
    hit  = sorted(br for br in expected_brs if br in _br_hits)
    miss = sorted(br for br in expected_brs if br not in _br_hits)
    dut._log.info(f"BR Coverage: {len(hit)}/{len(expected_brs)} hit")
    if hit:
        dut._log.info(f"  Hit  : {', '.join(hit)}")
    if miss:
        dut._log.warning(f"  Missed: {', '.join(miss)}")


# =============================================================================
# Assertion helpers
# =============================================================================

def check_iotlb_update(dut, expected_leaf_ppn: int,
                        stage: str = "s1", ctx: str = "") -> None:
    """Assert that the DUT signals a valid IOTLB update with the correct leaf PPN.

    stage: "s1" checks up_1S_content_o; "s2" checks up_2S_content_o.
    """
    prefix = f"[{ctx}] " if ctx else ""
    assert int(dut.update_o.value) == 1, \
        f"{prefix}update_o should be 1, got {int(dut.update_o.value)}"
    assert int(dut.ptw_error_o.value) == 0, \
        f"{prefix}ptw_error_o should be 0, got {int(dut.ptw_error_o.value)}"

    if stage == "s1":
        pte_val = int(dut.up_1S_content_o.value)
    else:
        pte_val = int(dut.up_2S_content_o.value)

    actual_ppn = (pte_val >> 10) & 0xFFFFFFFFFFF
    assert actual_ppn == expected_leaf_ppn, (
        f"{prefix}leaf PPN mismatch: expected {hex(expected_leaf_ppn)}, "
        f"got {hex(actual_ppn)} (raw PTE={hex(pte_val)})"
    )