import cocotb
import random
from cocotb.triggers import Timer
from ptw_helpers import PTWTester, PteFactory, format_sv39_iova

# -------------------------------------------------------------------------
# 共通のテスト本体 (tb を引数として受け取るように変更)
# -------------------------------------------------------------------------
async def run_fault_injection_test(tb, dut, fault_type, level, adu_combo=0):
    await tb.reset()
    tb.ram.mem.clear()
    tb.ram.error_addresses.clear() # ★ 前のテストのAXIエラー設定を掃除する

    # IOVAとPPNの準備
    iova = 0x1_d6ab_c019 
    iova_64 = format_sv39_iova(iova)
    vpn = [(iova >> 30) & 0x1FF, (iova >> 21) & 0x1FF, (iova >> 12) & 0x1FF]
    
    ppns = [0x1140, 0x11, 0x12, 0x123]
    tb.dut.iosatp_ppn_i.value = ppns[0]
    tb.dut.en_1S_i.value = 1

    # アドレス計算
    addrs = [
        (ppns[0] << 12) + (vpn[0] * 8),
        (ppns[1] << 12) + (vpn[1] * 8),
        (ppns[2] << 12) + (vpn[2] * 8) 
    ]

    # PTE生成
    ptes = [
        PteFactory.s1_non_leaf(ppn=ppns[1]),
        PteFactory.s1_non_leaf(ppn=ppns[2]),
        PteFactory.s1_leaf(ppn=ppns[3])
    ]

    is_store_req = False
    # フォルト注入
    if fault_type == "V=0":
        ptes[2 - level] &= ~0x1

    elif fault_type == "R=0_W=1":
        ptes[2 - level] &= ~(1 << 1)
        ptes[2 - level] |= (1 << 2)

    elif fault_type == "RESERVED":
        garbage = random.randint(1, 0x3FF)
        dut._log.info(f"  -> [エラー注入] Level {level} の予約ビットにゴミ {hex(garbage)} を混入")
        ptes[2 - level] |= (garbage << 54)

    elif fault_type == "AXI_ERR":
        tb.ram.inject_axi_error(addrs[2 - level], 2)

    elif fault_type == "NON_LEAF_ADU":
        # adu_combo (1〜7) を使って、A, D, U を個別にセットする
        u_bit = (adu_combo >> 0) & 1
        a_bit = (adu_combo >> 1) & 1
        d_bit = (adu_combo >> 2) & 1
        dut._log.info(f"  -> [エラー注入] S2 Level {level}(Non-Leaf) を U={u_bit}, A={a_bit}, D={d_bit} に改ざん")
        if u_bit: ptes[2 - level] |= (1 << 4)
        if a_bit: ptes[2 - level] |= (1 << 6)
        if d_bit: ptes[2 - level] |= (1 << 7)
        
    elif fault_type == "LEVEL0_NON_LEAF":
        # 最終階層(Level 0)なのに Non-Leaf (R=0, W=0, X=0) になっている
        tb.dut._log.info(f"  -> [エラー注入] 最終階層 Level 0 に Non-Leaf を配置する")
        ptes[2] = PteFactory.s1_non_leaf(ppn=ppns[3])
        
    elif fault_type == "LEAF_A_0":
        # Leaf PTE なのに Accessed(A) ビットが 0 になっている
        # (ハードウェアによるA/D更新をサポートしていない場合、OSに任せるためFaultを出すのが仕様)
        tb.dut._log.info(f"  -> [エラー注入] 最終階層 Level 0 の Aビットを 0 にする")
        ptes[2] &= ~(1 << 6)
        
    elif fault_type == "LEAF_R_0":
        # Leaf PTE なのに Read(R) ビットが 0 になっている
        # (データ読み出し要求なのに、R=0, X=1 の「実行専用(Execute-Only)ページ」を引いた場合のアクセス権限エラー)
        tb.dut._log.info(f"  -> [エラー注入] 最終階層 Level 0 を R=0, W=0, X=1 (実行専用) にする")
        ptes[2] &= ~(1 << 1) # R=0
        ptes[2] &= ~(1 << 2) # W=0
        ptes[2] |= (1 << 3)  # X=1
    
    elif fault_type == "LEAF_D_0_STORE":
        # Store命令なのに Dirty(D) ビットが 0
        # (OSによる明示的なDirty追跡が必要な場合、書き込み時にPage Faultを出す仕様)
        tb.dut._log.info(f"  -> [エラー注入] Store命令なのに最終階層 Level 0 の Dビットを 0 にする")
        ptes[2] &= ~(1 << 7) # D=0
        is_store_req = True  # ★ PTWへのリクエストをStoreにする
        
    elif fault_type == "LEAF_W_0_STORE":
        # Store命令なのに Write(W) ビットが 0 (読み取り専用ページへの書き込み)
        tb.dut._log.info(f"  -> [エラー注入] Store命令なのに最終階層 Level 0 の Wビットを 0 にする")
        ptes[2] &= ~(1 << 2) # W=0
        is_store_req = True  # ★ PTWへのリクエストをStoreにする


    for a, p in zip(addrs, ptes):
        tb.ram.write(a, p)

    await tb.trigger(iova=iova_64, is_store=is_store_req)
    result = await tb.wait_completion()

    assert result == "ERROR", f"Fault {fault_type} at Level {level} failed to trigger ptw_error_o"
    dut._log.info(f"PASS: {fault_type} at Level {level} detected correctly.")

# -------------------------------------------------------------------------
# 各テストケース (テストごとに1回だけ PTWTester を作る)
# -------------------------------------------------------------------------
@cocotb.test()
async def test_s1_fault_invalid_pte(dut):
    """PTE.V=0 または R=0,W=1 のテスト"""
    tb = PTWTester(dut) # ★ ここで1回だけ作る
    for lv in [2, 1, 0]:
        await run_fault_injection_test(tb, dut, "V=0", lv)
        await run_fault_injection_test(tb, dut, "R=0_W=1", lv)

@cocotb.test()
async def test_s1_fault_reserved_bits(dut):
    """PTE.reserved != 0 のテスト"""
    tb = PTWTester(dut) # ★ ここで1回だけ作る
    for lv in [2, 1, 0]:
        await run_fault_injection_test(tb, dut, "RESERVED", lv)

@cocotb.test()
async def test_s1_fault_axi_resp(dut):
    """AXI RRESP != OKAY のテスト"""
    tb = PTWTester(dut) # ★ ここで1回だけ作る
    for lv in [2, 1, 0]:
        await run_fault_injection_test(tb, dut, "AXI_ERR", lv)

@cocotb.test()
async def test_s1_fault_non_leaf_adu(dut):
    """Non-Leaf PTE に A, D, U ビットの組み合わせ(全7パターン)が立っているテスト"""
    tb = PTWTester(dut)
    for lv in [2, 1]: # Non-Leafは Level 2 と 1 のみ
        for combo in range(1, 8): # 1(001) 〜 7(111) までループ
            await run_fault_injection_test(tb, dut, "NON_LEAF_ADU", lv, adu_combo=combo)

@cocotb.test()
async def test_s1_fault_level0_non_leaf(dut):
    """最終階層 (Level 0) が Non-Leaf だった場合のテスト"""
    tb = PTWTester(dut)
    # 最終階層でのみテスト
    await run_fault_injection_test(tb, dut, "LEVEL0_NON_LEAF", 0)

@cocotb.test()
async def test_s1_fault_leaf_a_0(dut):
    """Leaf PTE の A ビットが 0 だった場合のテスト"""
    tb = PTWTester(dut)
    # 最終階層でのみテスト
    await run_fault_injection_test(tb, dut, "LEAF_A_0", 0)

@cocotb.test()
async def test_s1_fault_leaf_r_0(dut):
    """Leaf PTE の R ビットが 0 (読み取り権限なし) だった場合のテスト"""
    tb = PTWTester(dut)
    # 最終階層でのみテスト
    await run_fault_injection_test(tb, dut, "LEAF_R_0", 0)

@cocotb.test()
async def test_s1_fault_leaf_d_0_store(dut):
    """Store命令実行時に Leaf PTE の D ビットが 0 だった場合のテスト"""
    tb = PTWTester(dut)
    await run_fault_injection_test(tb, dut, "LEAF_D_0_STORE", 0)

@cocotb.test()
async def test_s1_fault_leaf_w_0_store(dut):
    """Store命令実行時に Leaf PTE の W ビットが 0 (書き込み権限なし) だった場合のテスト"""
    tb = PTWTester(dut)
    await run_fault_injection_test(tb, dut, "LEAF_W_0_STORE", 0)
