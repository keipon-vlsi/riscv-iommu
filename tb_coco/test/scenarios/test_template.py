"""test_template.py — 新規テスト追加時の雛形

このファイルをコピー → リネーム → 中身を書き換えて使ってください。
コメントで "EDIT HERE" と書いてある部分が編集ポイントです。

# テスト追加の流れ:
1. このファイルをコピー (例: test_xxx.py)
2. Makefile の MODULE にカンマ区切りで追加 (またはグループターゲット使用)
3. 関数名は test_NN_xxx で命名 (NN は任意の番号)
4. make sim MODULE=test_xxx で確認
"""

import logging
import cocotb

# === helpers パッケージから必要なものを import ===
# IommuEnv が中心 API。定数は名前付きで import する。
from helpers import (
    IommuEnv,
    # PTE フラグ
    PTE_LEAF_RWX_AD, PTE_LEAF_R_AD, PTE_LEAF_RW_AD,
    PTE_V, PTE_R, PTE_W, PTE_X, PTE_U, PTE_A, PTE_D,
    # フォルト原因
    CAUSE_LOAD_PAGE_FAULT, CAUSE_STORE_PAGE_FAULT,
    CAUSE_LOAD_ACCESS_FAULT,
    # transaction type
    TTYP_UNTRANSLATED_RD, TTYP_UNTRANSLATED_WR,
)


# =============================================================================
# === 正常系の最小テンプレ ===
# =============================================================================
@cocotb.test(timeout_time=50, timeout_unit="us")
async def test_template_normal(dut):
    """シナリオを 1 行で説明 (EDIT HERE)。"""
    log = logging.getLogger("cocotb.tb")
    log.setLevel(logging.INFO)

    # ---- 1. 環境構築 ----
    env = IommuEnv(dut)
    await env.setup()                              # clock + reset + AXI + FQ

    # ---- 2. DC を配置 (Sv39 1-stage) ----
    await env.install_dc_sv39_s1(did=0)

    # ---- 3. ページテーブルを作る ----
    iova   = 0x002_345                              # ← EDIT HERE
    sp_ppn = 0x100                                   # ← EDIT HERE (= SPA >> 12)
    env.map_sv39_4k(iova, sp_ppn=sp_ppn,
                    perms=PTE_LEAF_RWX_AD)           # ← EDIT HERE: 権限

    # ---- 4. 物理メモリに期待データ ----
    spa = (sp_ppn << 12) | (iova & 0xFFF)
    test_data = 0xC0FFEE_BABE0123                    # ← EDIT HERE
    env.comp_ram.write(spa, test_data.to_bytes(8, "little"))

    # ---- 5. 翻訳実行 ----
    op = await env.dev_tr_read(iova, 8)
    got = int.from_bytes(op.data, "little")

    # ---- 6. 検証 ----
    assert got == test_data, \
        f"translation failed: expected 0x{test_data:016x}, got 0x{got:016x}"

    # フォルトが出ていないことも確認 (任意だが推奨)
    await env.fq.expect_no_record(settle_cycles=20)


# =============================================================================
# === フォルト系の最小テンプレ ===
# =============================================================================
@cocotb.test(timeout_time=50, timeout_unit="us")
async def test_template_fault(dut):
    """シナリオを 1 行で説明 (EDIT HERE)。"""
    log = logging.getLogger("cocotb.tb")
    log.setLevel(logging.INFO)

    env = IommuEnv(dut)
    await env.setup()

    await env.install_dc_sv39_s1(did=0)

    # ---- フォルトを引くページ設定 ----
    iova = 0x002_345
    env.map_sv39_4k(iova, sp_ppn=0x100, perms=0)    # ★ V=0 → page fault

    # ---- read を発行して FQ にフォルトレコードが来るのを待つ ----
    rec = await env.expect_fault_on_read(
        iova,
        cause=CAUSE_LOAD_PAGE_FAULT,                # ← EDIT HERE
        ttyp=TTYP_UNTRANSLATED_RD,                  # 任意 (None で省略可)
        did=0,                                       # 任意
    )
    log.info(f"  ✓ fault as expected: {rec}")
