"""
test_simple_axil_ram.py — cocotbext-axi 入門サンプル

このテストは AxiLiteMaster と simple_axil_ram (DUT) の疎通を確認する。
学習ポイント:
  - Clock / Reset の駆動
  - AxiLiteBus.from_prefix() で信号束を作成
  - AxiLiteMaster による read/write
  - データ検証
"""

import logging

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from cocotbext.axi import AxiLiteBus, AxiLiteMaster


# =============================================================================
# 共通セットアップヘルパ
# =============================================================================
async def reset_dut(dut, cycles=5):
    """指定サイクル数だけリセットをアサート (active-high)。"""
    dut.rst.value = 1
    for _ in range(cycles):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


def make_master(dut):
    """AxiLiteMaster を生成して返す共通処理。"""
    # AxiLiteBus.from_prefix(dut, "s_axil") は dut.s_axil_awvalid 等を
    # 自動で 1 つの bus オブジェクトに束ねる
    bus = AxiLiteBus.from_prefix(dut, "s_axil")
    return AxiLiteMaster(bus, dut.clk, dut.rst)


# =============================================================================
# テスト 1: 1 番地の write → read で疎通確認
# =============================================================================
@cocotb.test()
async def test_01_single_write_read(dut):
    """write 1 回 → read 1 回でデータが読み戻せること。"""
    log = logging.getLogger("cocotb.tb")
    log.setLevel(logging.INFO)

    # 100 MHz クロック (10 ns 周期) を start_soon で並列に走らせる
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())

    # Master 接続 + リセット
    master = make_master(dut)
    await reset_dut(dut)

    # write: 0xDEADBEEF を address 0x100 に
    addr = 0x100
    write_val = 0xDEADBEEF
    log.info(f"Writing 0x{write_val:08x} to 0x{addr:03x}")
    await master.write(addr, write_val.to_bytes(4, "little"))

    # read back
    log.info(f"Reading from 0x{addr:03x}")
    op = await master.read(addr, 4)
    read_val = int.from_bytes(op.data, "little")
    log.info(f"  Got: 0x{read_val:08x}")

    assert read_val == write_val, \
        f"Mismatch: wrote 0x{write_val:08x}, read 0x{read_val:08x}"
    log.info("✓ Test 1 PASS")


# =============================================================================
# テスト 2: 複数番地に書いて、すべて正しく読み戻せること
# =============================================================================
@cocotb.test()
async def test_02_multiple_addresses(dut):
    """16 番地に異なる値を書き込み、全部読み戻して検証。"""
    log = logging.getLogger("cocotb.tb")

    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    master = make_master(dut)
    await reset_dut(dut)

    # (addr, value) のリストを生成
    test_pairs = [
        (0x000, 0x11111111), (0x004, 0x22222222),
        (0x008, 0x33333333), (0x00C, 0x44444444),
        (0x010, 0x55555555), (0x014, 0x66666666),
        (0x018, 0x77777777), (0x01C, 0x88888888),
        (0x020, 0x99999999), (0x024, 0xAAAAAAAA),
        (0x028, 0xBBBBBBBB), (0x02C, 0xCCCCCCCC),
        (0x030, 0xDDDDDDDD), (0x034, 0xEEEEEEEE),
        (0x038, 0xFFFFFFFF), (0x03C, 0x12345678),
    ]

    # まず全部 write
    for addr, val in test_pairs:
        await master.write(addr, val.to_bytes(4, "little"))

    # その後すべて read で検証
    for addr, expected in test_pairs:
        op = await master.read(addr, 4)
        actual = int.from_bytes(op.data, "little")
        assert actual == expected, \
            f"@0x{addr:03x}: expected 0x{expected:08x}, got 0x{actual:08x}"

    log.info(f"✓ Test 2 PASS — {len(test_pairs)} addresses verified")


# =============================================================================
# テスト 3: WSTRB (バイトストローブ) の挙動確認
# =============================================================================
@cocotb.test()
async def test_03_byte_strobe(dut):
    """部分書き込みで他バイトが上書きされないこと。"""
    log = logging.getLogger("cocotb.tb")

    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    master = make_master(dut)
    await reset_dut(dut)

    addr = 0x200

    # まず全 1 を書き込み
    await master.write(addr, b"\xFF\xFF\xFF\xFF")
    op = await master.read(addr, 4)
    assert op.data == b"\xFF\xFF\xFF\xFF"

    # 次に下位 1 byte だけ書き込み (cocotbext-axi は length=1 で勝手に
    # WSTRB を生成してくれる)
    await master.write(addr, b"\x00")  # 下位 1 byte だけ書く

    op = await master.read(addr, 4)
    # 期待: 下位 1 byte が 0x00、上位 3 byte は 0xFF のまま
    expected = b"\x00\xFF\xFF\xFF"
    assert op.data == expected, \
        f"WSTRB test fail: expected {expected.hex()}, got {op.data.hex()}"

    log.info("✓ Test 3 PASS — WSTRB respected")


# =============================================================================
# テスト 4: ランダムテスト (簡易)
# =============================================================================
@cocotb.test()
async def test_04_random(dut):
    """ランダムな addr / value で 50 回 write → read"""
    import random
    log = logging.getLogger("cocotb.tb")

    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    master = make_master(dut)
    await reset_dut(dut)

    random.seed(42)

    expected = {}
    for i in range(50):
        addr = random.randint(0, 0xFFC) & ~0x3   # 4-byte aligned, 4KB 内
        val  = random.randint(0, 0xFFFFFFFF)
        await master.write(addr, val.to_bytes(4, "little"))
        expected[addr] = val   # 後の write で上書きされる場合は最新が残る

    # 全 addr を検証
    for addr, exp_val in expected.items():
        op = await master.read(addr, 4)
        actual = int.from_bytes(op.data, "little")
        assert actual == exp_val, \
            f"@0x{addr:03x}: expected 0x{exp_val:08x}, got 0x{actual:08x}"

    log.info(f"✓ Test 4 PASS — {len(expected)} random writes verified")