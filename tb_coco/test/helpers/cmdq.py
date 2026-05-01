"""iommu_tb.cmdq — Command Queue (CQ) のセットアップとコマンド発行

CQ は ds_ram 上に配置される 16 byte/entry の循環バッファ。
TB 側が cqt に進めながら command を書き込み、IOMMU が cqh を進めて消費する。

使い方:
    cq = CommandQueue(dut, prog_master, ds_ram,
                      base_ppn=DEFAULT_CQ_BASE_PPN, log2sz=7)
    await cq.setup()
    await cq.iotinval_vma(addr=iova, pscid=0, av=True)
    await cq.iofence_c()                        # ← barrier として使う
"""

import logging

from cocotb.triggers import RisingEdge

from .const import (
    REG_CQB_L, REG_CQH, REG_CQT, REG_CQCSR,
    QCSR_BUSY, QCSR_ON,
    CMD_OPCODE_IOTINVAL, CMD_OPCODE_IOFENCE,
    IOTINVAL_FUNC3_VMA, IOTINVAL_FUNC3_GVMA,
    IOFENCE_FUNC3_C,
)
from .regs import (
    write_reg32, read_reg32, write_reg64,
    enable_cq,
)


CQ_ENTRY_SIZE = 16


def _build_cmd_dw0(*, opcode: int, func3: int = 0,
                    pv: bool = False, dv: bool = False,
                    pid: int = 0, did: int = 0,
                    extra: int = 0) -> int:
    """共通ビットを組み立て: [6:0]=opcode, [9:7]=func3, [11:10]=rsvd, [31:12]=pid, [32]=pv, [33]=dv,
    [39:34]=rsvd, [63:40]=did。

    コマンド種ごとに extra (上位ビット) を OR して使い分ける。
    """
    return ((opcode & 0x7F)
          | ((func3 & 0x7) << 7)
          | ((pid & 0xFFFFF) << 12)
          | ((1 << 32) if pv else 0)
          | ((1 << 33) if dv else 0)
          | ((did & 0xFFFFFF) << 40)
          | extra)


# =============================================================================
# CommandQueue クラス
# =============================================================================
class CommandQueue:
    def __init__(self, dut, prog_master, ds_ram, *, base_ppn: int, log2sz: int = 7):
        self.dut = dut
        self.prog = prog_master
        self.ds_ram = ds_ram
        self.base_ppn  = base_ppn
        self.base_addr = base_ppn << 12
        self.log2sz = log2sz
        self.num_entries = 1 << log2sz
        self.byte_size = self.num_entries * CQ_ENTRY_SIZE
        self.tail_local = 0
        self.log = logging.getLogger("cocotb.tb.cq")

    # ------------------------------------------------------------------
    async def configure(self):
        """cqb を書く。cqcsr.cqen はまだ立てない。"""
        self.ds_ram.write(self.base_addr, bytes(self.byte_size))
        cqb_val = ((self.base_ppn & 0x0FFF_FFFF_FFFF) << 10) | ((self.log2sz - 1) & 0x1F)
        await write_reg64(self.prog, REG_CQB_L, cqb_val)
        self.log.info(f"  cqb <= 0x{cqb_val:016x}")

    async def enable(self):
        await enable_cq(self.prog, self.dut)

    async def setup(self):
        await self.configure()
        await self.enable()

    # ------------------------------------------------------------------
    async def _push(self, dw0: int, dw1: int = 0):
        """1 コマンドを CQ に書き込んで cqt を進める。"""
        addr = self.base_addr + self.tail_local * CQ_ENTRY_SIZE
        self.ds_ram.write(addr, dw0.to_bytes(8, "little") + dw1.to_bytes(8, "little"))
        self.tail_local = (self.tail_local + 1) & (self.num_entries - 1)
        await write_reg32(self.prog, REG_CQT, self.tail_local)

    async def _wait_consumed(self, *, max_cycles: int = 500):
        """cqh が tail_local に追いつくまで待つ。"""
        for _ in range(max_cycles):
            head = await read_reg32(self.prog, REG_CQH)
            if head == self.tail_local:
                return
            await RisingEdge(self.dut.clk_i)
        raise TimeoutError(f"CQ did not drain. cqh != cqt={self.tail_local}")

    # ------------------------------------------------------------------
    # 高レベル: 各コマンド
    # ------------------------------------------------------------------
    async def iotinval_vma(self, *, addr: int = 0, pscid: int = 0, gscid: int = 0,
                            av: bool = False, pscv: bool = False, gv: bool = False,
                            wait: bool = True):
        """IOTINVAL.VMA: S-stage IOTLB 無効化。

        Args:
            addr: 無効化する IOVA (av=True の時のみ有効)
            pscid: PSCID (pscv=True なら使う)
            gscid: GSCID (gv=True なら使う)
            av/pscv/gv: 各 valid bit
            wait: 発行後に IOFENCE.C で barrier してから帰る (推奨)
        """
        # DW0 fields
        dw0 = _build_cmd_dw0(
            opcode = CMD_OPCODE_IOTINVAL,
            func3  = IOTINVAL_FUNC3_VMA,
            extra  = (((1 << 32) if av  else 0)
                   | ((1 << 33) if pscv else 0)
                   | ((1 << 34) if gv  else 0)
                   | ((pscid & 0xFFFFF) << 12)
                   | ((gscid & 0xFFFF)  << 40)),
        )
        # DW1: address
        dw1 = (addr >> 2) & 0xFFFF_FFFF_FFFF_FFFF if av else 0
        await self._push(dw0, dw1)
        if wait:
            await self.iofence_c()

    async def iotinval_gvma(self, *, gpa: int = 0, gscid: int = 0,
                             av: bool = False, gv: bool = False,
                             wait: bool = True):
        """IOTINVAL.GVMA: G-stage IOTLB 無効化。"""
        dw0 = _build_cmd_dw0(
            opcode = CMD_OPCODE_IOTINVAL,
            func3  = IOTINVAL_FUNC3_GVMA,
            extra  = (((1 << 32) if av else 0)
                   | ((1 << 34) if gv else 0)
                   | ((gscid & 0xFFFF) << 40)),
        )
        dw1 = (gpa >> 2) & 0xFFFF_FFFF_FFFF_FFFF if av else 0
        await self._push(dw0, dw1)
        if wait:
            await self.iofence_c()

    async def iofence_c(self, *, av: bool = False, addr: int = 0, data: int = 0,
                          wsi: bool = False):
        """IOFENCE.C: 先行コマンド完了を保証する barrier。

        通常は av=False で十分 (CQ 完全 drain を待つだけ)。
        """
        dw0 = _build_cmd_dw0(
            opcode = CMD_OPCODE_IOFENCE,
            func3  = IOFENCE_FUNC3_C,
            extra  = (((1 << 32) if av  else 0)
                   | ((1 << 33) if wsi else 0)
                   | ((data & 0xFFFFFFFF) << 32)),
        )
        dw1 = (addr >> 2) & 0xFFFF_FFFF_FFFF_FFFF if av else 0
        await self._push(dw0, dw1)
        await self._wait_consumed()
