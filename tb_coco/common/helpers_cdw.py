"""
DDTW / PDTW 単体検証用 helper (= PTW の helpers.py の DDTW/PDTW 版)

- DcFactory:    DC (= Device Context) 4 entries × 8 byte を組み立てる
- PcFactory:    PC (= Process Context) 2 entries × 8 byte を組み立てる
- NlEntryFactory: PDT/DDT の non-leaf entry を組み立てる
- MockMemoryBurst: multi-beat AXI burst read に対応した memory model
- PhysicalMemoryManager: 既存 helpers.py と同じ PPN allocator

注意: DC/PC の bit layout は RISC-V IOMMU spec 1.0 に従っているが、
      実際の pkg の struct と差異がある場合は調整が必要。
"""

import logging
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge


# =============================================================================
# PhysicalMemoryManager (= PTW 版と同じ)
# =============================================================================
class PhysicalMemoryManager:
    def __init__(self, start_ppn: int = 0x1000):
        self._next = start_ppn

    def alloc_ppn(self) -> int:
        ppn = self._next
        self._next += 1
        return ppn

    def alloc_aligned_ppn(self, alignment_ppn: int = 4) -> int:
        """指定 PPN 単位でアラインされた PPN を割り当てる。

        例: alignment_ppn=4 (= 16K aligned、 iohgatp.PPN 用) で、
            内部カウンタを 4 の倍数に切り上げてから 1 つ消費する。
        """
        self._next = (self._next + alignment_ppn - 1) & ~(alignment_ppn - 1)
        ppn = self._next
        self._next += 1
        return ppn


# =============================================================================
# DC (= Device Context) builder
# =============================================================================
class DcFactory:
    """DC を 4 entries × 8 bytes (= MSI_DISABLED 想定) で組み立てる。

    Layout per spec 1.0 (= 主要 field のみ):
        Entry 0: dc.tc
            bit 0:    V (valid)
            bit 1:    en_ats
            bit 2:    en_pri
            bit 3:    t2gpa
            bit 4:    dtf
            bit 5:    pdtv  (= PC 経由翻訳を有効化)
            bit 6:    prpr
            bit 7:    gade
            bit 8:    sade
            bit 9:    dpe
            bit 10:   sbe
            bit 11:   sxl
        Entry 1: dc.iohgatp
            bits 0-43:  PPN
            bits 44-59: GSCID
            bits 60-63: MODE (0=BARE, 8=Sv39x4)
        Entry 2: dc.ta
            bits 12-31: PSCID
        Entry 3: dc.fsc
            bits 0-43:  PPN  (= iosatp.PPN if !pdtv, else pdtp.PPN)
            bits 60-63: MODE (0=BARE, 8=Sv39, or 1/2/3 for PD8/17/20)
    """

    @staticmethod
    def build(v=1, pdtv=0, sbe=0,
              iohgatp_mode=0, iohgatp_ppn=0, gscid=0,
              pscid=0,
              fsc_mode=0, fsc_ppn=0):
        """Return list of 4 × 8-byte (= 64-bit) words."""
        tc = (
            (v    & 1) |
            ((pdtv & 1) << 5) |
            ((sbe  & 1) << 10)
        )
        iohgatp = (
            (iohgatp_ppn & ((1 << 44) - 1)) |
            ((gscid & 0xFFFF) << 44) |
            ((iohgatp_mode & 0xF) << 60)
        )
        ta = (pscid & 0xFFFFF) << 12
        fsc = (
            (fsc_ppn & ((1 << 44) - 1)) |
            ((fsc_mode & 0xF) << 60)
        )
        return [tc, iohgatp, ta, fsc]


# =============================================================================
# PC (= Process Context) builder
# =============================================================================
class PcFactory:
    """PC を 2 entries × 8 bytes で組み立てる。

    Entry 0: pc.ta
        bit 0:     V
        bit 1:     ENS  (= enable supervisor; = ssrv)
        bit 2:     SUM
        bits 12-31: PSCID
    Entry 1: pc.fsc
        bits 0-43:  PPN
        bits 60-63: MODE (8 = Sv39, 0 = BARE)
    """

    @staticmethod
    def build(v=1, ens=0, sum_bit=0, pscid=0, fsc_mode=8, fsc_ppn=0):
        """Return list of 2 × 8-byte words."""
        ta = (
            (v       & 1) |
            ((ens    & 1) << 1) |
            ((sum_bit & 1) << 2) |
            ((pscid & 0xFFFFF) << 12)
        )
        fsc = (
            (fsc_ppn & ((1 << 44) - 1)) |
            ((fsc_mode & 0xF) << 60)
        )
        return [ta, fsc]


# =============================================================================
# Non-Leaf entry builder (= DDT / PDT 中間レベル用)
# =============================================================================
class NlEntryFactory:
    """DDT / PDT の non-leaf entry (= 次レベルの PT page を指すポインタ)。

    Layout (= rv_iommu::nl_entry_t、 推定):
        bit 0:     V
        bits 10-53: PPN
        その他は reserved
    """

    @staticmethod
    def build(v=1, ppn=0):
        return (v & 1) | ((ppn & ((1 << 44) - 1)) << 10)


# =============================================================================
# Multi-beat MockMemory (= DDTW / PDTW 用 AXI burst 対応)
# =============================================================================
class MockMemoryBurst:
    """AXI burst (= len > 0) read に対応した memory model。

    DDTW (= 4 beat for DC) and PDTW (= 2 beat for PC) で使う。
    NL entry の 1-beat read にも対応。

    使い方:
        ram = MockMemoryBurst(dut)
        ram.write(addr_bytes, data_64bit)
        # → dut.mem_ar_valid_o が立ったら自動的に beat ごとに応答
    """

    def __init__(self, dut):
        self.dut = dut
        self.mem = {}   # byte addr → 64-bit data
        cocotb.start_soon(self._serve())

    def write(self, addr, data):
        self.mem[addr] = data
        self.dut._log.info(f"  [MockMem] write {hex(addr)} = {hex(data)}")

    def write_words(self, base_addr, words):
        """連続する 64-bit word の list を書き込む (= DC/PC 配置用)。"""
        for i, w in enumerate(words):
            self.write(base_addr + i * 8, w)

    async def _serve(self):
        # 初期値
        self.dut.mem_ar_ready_i.value = 1
        self.dut.mem_r_valid_i.value  = 0
        self.dut.mem_r_data_i.value   = 0
        self.dut.mem_r_last_i.value   = 0
        self.dut.mem_r_resp_i.value   = 0

        next_r_valid = 0
        next_r_data  = 0
        next_r_last  = 0
        next_r_resp  = 0

        burst_active = False
        base_addr    = 0
        num_beats    = 0
        beats_sent   = 0

        while True:
            await RisingEdge(self.dut.clk_i)
            # この cycle で driver する値
            self.dut.mem_r_valid_i.value = next_r_valid
            self.dut.mem_r_data_i.value  = next_r_data
            self.dut.mem_r_last_i.value  = next_r_last
            self.dut.mem_r_resp_i.value  = next_r_resp

            await ReadOnly()

            # R handshake (= valid & ready の両方が立った)
            if (int(self.dut.mem_r_valid_i.value) == 1
                    and int(self.dut.mem_r_ready_o.value) == 1):
                beats_sent += 1
                if beats_sent < num_beats:
                    # 次の beat 準備
                    addr = base_addr + beats_sent * 8
                    next_r_data  = self.mem.get(addr, 0)
                    next_r_last  = 1 if beats_sent == num_beats - 1 else 0
                    next_r_valid = 1
                    self.dut._log.info(
                        f"  [AXI] read beat {beats_sent} addr={hex(addr)} -> {hex(next_r_data)}"
                    )
                else:
                    # burst 完了
                    burst_active = False
                    next_r_valid = 0
                    next_r_last  = 0
                    next_r_data  = 0

            # 新規 AR を accept (= burst 中じゃない時のみ)
            if (not burst_active
                    and int(self.dut.mem_ar_valid_o.value) == 1
                    and int(self.dut.mem_ar_ready_i.value) == 1):
                base_addr  = int(self.dut.mem_ar_addr_o.value)
                num_beats  = int(self.dut.mem_ar_len_o.value) + 1
                beats_sent = 0
                burst_active = True
                next_r_data  = self.mem.get(base_addr, 0)
                next_r_last  = 1 if num_beats == 1 else 0
                next_r_valid = 1
                self.dut._log.info(
                    f"  [AXI] burst start addr={hex(base_addr)} len={num_beats-1} "
                    f"-> beat 0: {hex(next_r_data)}"
                )


# =============================================================================
# Helper: PTW done 信号を simulate (= nested S2 walk の代わりに直接結果を返す)
# =============================================================================
async def simulate_ptw_done(dut, spa_ppn, cycles_delay=5):
    """DDTW / PDTW から cdw_implicit_access_o が立ったら、 指定 cycle 後に
    ptw_done_i + pdt_ppn_i を立てて S2 walk 結果を simulate する。
    """
    log = logging.getLogger("cocotb.tb.ptw_sim")
    # Wait until cdw_implicit_access_o asserts
    while True:
        await RisingEdge(dut.clk_i)
        if int(dut.cdw_implicit_access_o.value) == 1:
            log.info(f"  [PTW sim] cdw_implicit_access detected, returning ppn=0x{spa_ppn:x}")
            break

    # 数 cycle 待ってから ptw_done をパルス
    for _ in range(cycles_delay):
        await RisingEdge(dut.clk_i)
    dut.pdt_ppn_i.value  = spa_ppn
    dut.ptw_done_i.value = 1
    await RisingEdge(dut.clk_i)
    dut.ptw_done_i.value = 0