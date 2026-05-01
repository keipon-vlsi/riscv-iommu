"""iommu_tb.regs — レジスタ R/W ヘルパ (prog AXI 経由)

`AxiMaster.write/read` を 8 byte / 4 byte でラップする。
busy bit や enable bit のポーリング待ちもここに集約。
"""

import logging

from cocotb.triggers import RisingEdge

from .const import (
    REG_DDTP_L, DDTP_MODE_MASK, DDTP_BUSY_BIT, DDTP_PPN_SHIFT,
    REG_FQCSR, REG_CQCSR,
    QCSR_EN, QCSR_ON, QCSR_BUSY,
)


# =============================================================================
# プリミティブ R/W
# =============================================================================
async def write_reg64(prog_master, addr: int, value: int):
    """8 byte register への write。"""
    await prog_master.write(addr, (value & 0xFFFF_FFFF_FFFF_FFFF).to_bytes(8, "little"))


async def read_reg64(prog_master, addr: int) -> int:
    op = await prog_master.read(addr, 8)
    return int.from_bytes(op.data, "little")


async def write_reg32(prog_master, addr: int, value: int):
    """4 byte register への write。"""
    await prog_master.write(addr, (value & 0xFFFF_FFFF).to_bytes(4, "little"))


async def read_reg32(prog_master, addr: int) -> int:
    op = await prog_master.read(addr, 4)
    return int.from_bytes(op.data, "little")


# =============================================================================
# ポーリング系
# =============================================================================
async def poll_reg(prog_master, dut, addr: int, *, mask: int, expected: int,
                   width: int = 4, max_cycles: int = 500):
    """`(read_reg(addr) & mask) == expected` になるまで待つ。

    Args:
        addr: register address
        mask / expected: 比較条件
        width: 4 or 8 byte
        max_cycles: タイムアウト
    """
    reader = read_reg32 if width == 4 else read_reg64
    for _ in range(max_cycles):
        v = await reader(prog_master, addr)
        if (v & mask) == expected:
            return v
        await RisingEdge(dut.clk_i)
    raise TimeoutError(
        f"poll_reg(addr=0x{addr:x}, mask=0x{mask:x}, expected=0x{expected:x}) "
        f"timed out after {max_cycles} cycles. last value=0x{v:x}"
    )


# =============================================================================
# 高レベル: ddtp 設定
# =============================================================================
async def configure_ddt_mode(prog_master, dut, *, mode: int, ddt_base_ppn: int):
    """ddtp に mode + PPN を書いて busy が落ちるまで待つ。

    Args:
        mode: DDTP_MODE_OFF / BARE / 1LVL / 2LVL / 3LVL
        ddt_base_ppn: DDT root の PPN (mode=BARE/OFF なら無視される)
    """
    log = logging.getLogger("cocotb.tb.regs")

    ddtp_val = ((ddt_base_ppn & 0x0FFF_FFFF_FFFF) << DDTP_PPN_SHIFT) | (mode & DDTP_MODE_MASK)
    log.info(f"  ddtp <= 0x{ddtp_val:016x} (mode={mode}, ppn=0x{ddt_base_ppn:x})")

    await write_reg64(prog_master, REG_DDTP_L, ddtp_val)

    # busy bit が落ちるまで poll
    final = await poll_reg(prog_master, dut, REG_DDTP_L,
                           mask=DDTP_BUSY_BIT, expected=0,
                           width=8, max_cycles=500)

    actual_mode = final & DDTP_MODE_MASK
    if actual_mode != mode:
        raise AssertionError(
            f"ddtp mode mismatch: wrote {mode}, read back {actual_mode}. "
            f"ddtp = 0x{final:016x}"
        )
    log.info(f"  ddtp confirmed: 0x{final:016x}")
    return final


# =============================================================================
# 高レベル: queue 制御 (CQ / FQ 共通)
# =============================================================================
async def enable_queue(prog_master, dut, *, csr_addr: int, max_cycles: int = 500):
    """queue CSR の EN を立てて ON が立つのを待つ汎用ヘルパ。"""
    log = logging.getLogger("cocotb.tb.regs")

    cur = await read_reg32(prog_master, csr_addr)
    new = cur | QCSR_EN
    await write_reg32(prog_master, csr_addr, new)

    final = await poll_reg(prog_master, dut, csr_addr,
                           mask=(QCSR_BUSY | QCSR_ON),
                           expected=QCSR_ON,
                           width=4, max_cycles=max_cycles)
    log.info(f"  queue CSR @0x{csr_addr:x} enabled: 0x{final:08x}")
    return final


async def enable_cq(prog_master, dut):
    return await enable_queue(prog_master, dut, csr_addr=REG_CQCSR)


async def enable_fq(prog_master, dut):
    return await enable_queue(prog_master, dut, csr_addr=REG_FQCSR)
