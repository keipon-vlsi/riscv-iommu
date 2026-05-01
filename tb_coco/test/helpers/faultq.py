"""iommu_tb.faultq — Fault Queue (FQ) のセットアップとフォルトレコード読出し

FQ は ds_ram 上に配置される 32 byte/entry の循環バッファ。
IOMMU が翻訳でフォルトしたら fqt にエントリを書き込んで進める。
TB 側は fqh を進めながら ds_ram からレコードを読み出して内容を検証する。
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from cocotb.triggers import RisingEdge

from .const import (
    REG_FQB_L, REG_FQH, REG_FQT, REG_FQCSR,
    FQ_RECORD_SIZE,
    QCSR_EN, QCSR_ON, QCSR_BUSY, QCSR_MF,
)
from .regs import (
    write_reg32, read_reg32, write_reg64,
    enable_fq,
)


# =============================================================================
# Fault record データクラス
# =============================================================================
@dataclass
class FaultRecord:
    """FQ から読み出した 1 entry を decode した結果。

    spec section 3.7 Figure 4 (32 byte / entry):
      DW0[11:0]   cause
      DW0[31:12]  PID (process_id)
      DW0[32]     PV  (process valid)
      DW0[33]     PRIV
      DW0[39:34]  TTYP (transaction type)
      DW0[63:40]  DID (device_id, lower 24 bit)
      DW1         iotval     (= original VA / IOVA)
      DW2         iotval2    (= GPA in case of guest fault)
      DW3         reserved
    """
    cause: int = 0
    pid:   int = 0
    pv:    int = 0
    priv:  int = 0
    ttyp:  int = 0
    did:   int = 0
    iotval:  int = 0
    iotval2: int = 0
    raw: bytes = field(default=b"", repr=False)

    def __str__(self):
        return (f"FaultRecord(cause={self.cause}, ttyp={self.ttyp}, "
                f"did=0x{self.did:x}, iotval=0x{self.iotval:x}, "
                f"iotval2=0x{self.iotval2:x})")


def decode_fault_record(raw: bytes) -> FaultRecord:
    """32 byte の raw bytes を FaultRecord にパース。

    spec (riscv-iommu 1.0 §4.2 Figure 32) のレイアウト:
        DW0 [ 63:  0] = CAUSE/PID/PV/PRIV/TTYP/DID
        DW1 [127: 64] = "for custom use" + reserved
        DW2 [191:128] = iotval     (= 元の VA / IOVA)
        DW3 [255:192] = iotval2    (= guest 2-stage 時の GPA)
    """
    assert len(raw) == FQ_RECORD_SIZE
    dw0 = int.from_bytes(raw[0:8],   "little")
    # raw[8:16] は custom + reserved なのでスキップ
    dw2 = int.from_bytes(raw[16:24], "little")    # iotval
    dw3 = int.from_bytes(raw[24:32], "little")    # iotval2
    return FaultRecord(
        cause   = (dw0 >>  0) & 0xFFF,
        pid     = (dw0 >> 12) & 0xFFFFF,
        pv      = (dw0 >> 32) & 0x1,
        priv    = (dw0 >> 33) & 0x1,
        ttyp    = (dw0 >> 34) & 0x3F,
        did     = (dw0 >> 40) & 0xFFFFFF,
        iotval  = dw2,
        iotval2 = dw3,
        raw     = raw,
    )


# =============================================================================
# FQ コントローラ (TB 側)
# =============================================================================
class FaultQueue:
    """Fault Queue を ds_ram 上に置いて IOMMU から書かせるための TB 側 wrapper。

    使い方:
        fq = FaultQueue(dut, prog_master, ds_ram,
                        base_ppn=DEFAULT_FQ_BASE_PPN, log2sz=7)
        await fq.enable()                  # IOMMU を fqcsr.fqen=1
        ...
        rec = await fq.wait_for_record()  # 1 件積まれるまで poll
        assert rec.cause == ...
    """

    def __init__(self, dut, prog_master, ds_ram, *, base_ppn: int, log2sz: int = 7):
        self.dut = dut
        self.prog = prog_master
        self.ds_ram = ds_ram
        self.base_ppn  = base_ppn
        self.base_addr = base_ppn << 12
        self.log2sz = log2sz
        self.num_entries = 1 << log2sz
        self.byte_size = self.num_entries * FQ_RECORD_SIZE
        self.head_local = 0           # TB 側で進める consumer pointer
        self.log = logging.getLogger("cocotb.tb.fq")

    # ------------------------------------------------------------------
    async def configure(self):
        """fqb を書く。fqcsr.fqen はまだ立てない。"""
        # FQ をゼロクリア
        self.ds_ram.write(self.base_addr, bytes(self.byte_size))
        # fqb: bits[4:0]=log2sz-1, bits[53:10]=PPN
        fqb_val = ((self.base_ppn & 0x0FFF_FFFF_FFFF) << 10) | ((self.log2sz - 1) & 0x1F)
        await write_reg64(self.prog, REG_FQB_L, fqb_val)
        self.log.info(f"  fqb <= 0x{fqb_val:016x} "
                      f"(base_ppn=0x{self.base_ppn:x}, log2sz={self.log2sz})")

    async def enable(self):
        """fqcsr.fqen=1 にして fqon が立つのを待つ。"""
        await enable_fq(self.prog, self.dut)

    async def setup(self):
        """configure + enable を一括で。"""
        await self.configure()
        await self.enable()

    # ------------------------------------------------------------------
    async def read_tail(self) -> int:
        return await read_reg32(self.prog, REG_FQT)

    async def read_head(self) -> int:
        return await read_reg32(self.prog, REG_FQH)

    async def write_head(self, head: int):
        await write_reg32(self.prog, REG_FQH, head & (self.num_entries - 1))

    # ------------------------------------------------------------------
    async def wait_for_record(self, *, max_cycles: int = 1000) -> FaultRecord:
        """新しい fault record が 1 件以上積まれるまで待ち、その 1 件を返す。

        消費後は fqh を進める (= ack)。
        """
        for _ in range(max_cycles):
            tail = await self.read_tail()
            if tail != self.head_local:
                rec = self._read_record(self.head_local)
                self.log.info(f"  FQ rec @{self.head_local}: {rec}")
                self.head_local = (self.head_local + 1) & (self.num_entries - 1)
                await self.write_head(self.head_local)
                return rec
            await RisingEdge(self.dut.clk_i)
        raise TimeoutError(f"No fault record arrived within {max_cycles} cycles")

    async def expect_no_record(self, *, settle_cycles: int = 50):
        """`settle_cycles` 待ってもレコードが積まれないことを確認。

        正常系テストで「フォルトしていない」ことを assert したい時に使う。
        """
        for _ in range(settle_cycles):
            await RisingEdge(self.dut.clk_i)
        tail = await self.read_tail()
        if tail != self.head_local:
            rec = self._read_record(self.head_local)
            raise AssertionError(f"Unexpected fault record: {rec}")

    async def drain(self) -> list:
        """積まれているレコードを全部吸い出す。"""
        out = []
        while True:
            tail = await self.read_tail()
            if tail == self.head_local:
                break
            out.append(self._read_record(self.head_local))
            self.head_local = (self.head_local + 1) & (self.num_entries - 1)
        await self.write_head(self.head_local)
        return out

    # ------------------------------------------------------------------
    def _read_record(self, idx: int) -> FaultRecord:
        addr = self.base_addr + idx * FQ_RECORD_SIZE
        raw = bytes(self.ds_ram.read(addr, FQ_RECORD_SIZE))
        return decode_fault_record(raw)


# =============================================================================
# 期待値マッチ helper
# =============================================================================
async def expect_fault(fq: FaultQueue, *, cause: int,
                        iotval: Optional[int] = None,
                        iotval2: Optional[int] = None,
                        ttyp: Optional[int] = None,
                        did: Optional[int] = None,
                        max_cycles: int = 1000) -> FaultRecord:
    """1 件の fault record を待って、フィールドを assert する便利関数。"""
    rec = await fq.wait_for_record(max_cycles=max_cycles)

    msg = []
    if rec.cause != cause:
        msg.append(f"cause: expected {cause}, got {rec.cause}")
    if iotval is not None and rec.iotval != iotval:
        msg.append(f"iotval: expected 0x{iotval:x}, got 0x{rec.iotval:x}")
    if iotval2 is not None and rec.iotval2 != iotval2:
        msg.append(f"iotval2: expected 0x{iotval2:x}, got 0x{rec.iotval2:x}")
    if ttyp is not None and rec.ttyp != ttyp:
        msg.append(f"ttyp: expected {ttyp}, got {rec.ttyp}")
    if did is not None and rec.did != did:
        msg.append(f"did: expected 0x{did:x}, got 0x{rec.did:x}")

    if msg:
        raise AssertionError(f"Fault mismatch: {' / '.join(msg)}\n  full: {rec}")
    return rec