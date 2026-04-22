import cocotb
import random
from cocotb.triggers import Timer
from ptw_helpers import PTWTester, PteFactory, format_sv39x4_gpa

# -------------------------------------------------------------------------
# Stage-2 専用: エラー注入テスト本体
# -------------------------------------------------------------------------
async def run_s2_fault_injection_test(tb, dut, fault_type, level, adu_combo=0):
    await tb.reset()
    tb.ram.mem.clear()
    tb.ram.error_addresses.clear()

    # 1. アドレス生成 (Stage-2仕様: 41ビットGPA)
    gpa_41 = random.getrandbits(41)
    iova_64 = format_sv39x4_gpa(gpa_41)
    
    # VPN抽出 (Stage-2のVPN2は11ビット!)
    vpn = [(gpa_41 >> 30) & 0x7FF, (gpa_41 >> 21) & 0x1FF, (gpa_41 >> 12) & 0x1FF]
    
    # 2. PPN生成と設定
    ppns = random.sample(range(1, 1 << 44), 4)
    ppns[0] &= ~0x3  # S2 Rootは16KBアライメント(下位2ビット0)必須
    
    tb.dut.iosatp_ppn_i.value = 0
    tb.dut.iohgatp_ppn_i.value = ppns[0]
    tb.dut.en_1S_i.value = 0
    tb.dut.en_2S_i.value = 1

    # 3. アドレス計算
    addrs = [
        (ppns[0] << 12) + (vpn[0] * 8),
        (ppns[1] << 12) + (vpn[1] * 8),
        (ppns[2] << 12) + (vpn[2] * 8) 
    ]

    # 4. PTE生成 (Stage-2用のPTEを使用)
    ptes = [
        PteFactory.s2_non_leaf(ppn=ppns[1]),
        PteFactory.s2_non_leaf(ppn=ppns[2]),
        PteFactory.s2_leaf(ppn=ppns[3])
    ]

    # ----------------------------------------
    # ★ フォルト注入ロジック
    # ----------------------------------------
    is_store_req = False

    if fault_type == "V=0":
        ptes[2 - level] &= ~0x1
        
    elif fault_type == "R=0_W=1":
        ptes[2 - level] &= ~(1 << 1)
        ptes[2 - level] |= (1 << 2)
        
    elif fault_type == "RESERVED":
        garbage = random.randint(1, 0x3FF)
        dut._log.info(f"  -> [エラー注入] S2 Level {level} 予約ビットにゴミ {hex(garbage)} を混入")
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
        dut._log.info(f"  -> [エラー注入] S2 最終階層 Level 0 に Non-Leaf を配置")
        ptes[2] = PteFactory.s2_non_leaf(ppn=ppns[3])
        
    elif fault_type == "LEAF_A_0":
        dut._log.info(f"  -> [エラー注入] S2 最終階層 Level 0 の Aビットを 0 にする")
        ptes[2] &= ~(1 << 6)
        
    elif fault_type == "LEAF_R_0":
        # S2における実行専用(R=0, W=0, X=1)にしてRead要求を通す
        dut._log.info(f"  -> [エラー注入] S2 最終階層 Level 0 を R=0, W=0, X=1 (実行専用) にする")
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

    # 5. メモリ配置と実行
    for a, p in zip(addrs, ptes):
        tb.ram.write(a, p)

    await tb.trigger(iova=iova_64, is_store=is_store_req)
    result = await tb.wait_completion()

    # エラー(ptw_error_o=1)にならなければアサートで落とす
    assert result == "ERROR", f"S2 Fault {fault_type} at Level {level} failed to trigger ptw_error_o"
    dut._log.info(f"PASS: S2 {fault_type} at Level {level} detected correctly.\n")

# -------------------------------------------------------------------------
# S2 各テストケース (シナリオ)
# -------------------------------------------------------------------------
@cocotb.test()
async def test_s2_fault_invalid_pte(dut):
    """PTE.V=0 または R=0,W=1 のテスト"""
    tb = PTWTester(dut)
    for lv in [2, 1, 0]:
        await run_s2_fault_injection_test(tb, dut, "V=0", lv)
        await run_s2_fault_injection_test(tb, dut, "R=0_W=1", lv)

@cocotb.test()
async def test_s2_fault_reserved_bits(dut):
    """PTE.reserved != 0 のテスト"""
    tb = PTWTester(dut)
    for lv in [2, 1, 0]:
        await run_s2_fault_injection_test(tb, dut, "RESERVED", lv)

@cocotb.test()
async def test_s2_fault_axi_resp(dut):
    """AXI RRESP != OKAY のテスト"""
    tb = PTWTester(dut)
    for lv in [2, 1, 0]:
        await run_s2_fault_injection_test(tb, dut, "AXI_ERR", lv)

@cocotb.test()
async def test_s2_fault_non_leaf_adu(dut):
    """Non-Leaf PTE に A, D, U ビットの組み合わせ(全7パターン)が立っているテスト"""
    tb = PTWTester(dut)
    for lv in [2, 1]: # Non-Leafは Level 2 と 1 のみ
        for combo in range(1, 8): # 1(001) 〜 7(111) までループ
            await run_s2_fault_injection_test(tb, dut, "NON_LEAF_ADU", lv, adu_combo=combo)

@cocotb.test()
async def test_s2_fault_level0_non_leaf(dut):
    """最終階層 (Level 0) が Non-Leaf だった場合のテスト"""
    tb = PTWTester(dut)
    await run_s2_fault_injection_test(tb, dut, "LEVEL0_NON_LEAF", 0)

@cocotb.test()
async def test_s2_fault_leaf_a_0(dut):
    """Leaf PTE の A ビットが 0 だった場合のテスト"""
    tb = PTWTester(dut)
    await run_s2_fault_injection_test(tb, dut, "LEAF_A_0", 0)

@cocotb.test()
async def test_s2_fault_leaf_r_0(dut):
    """Leaf PTE の R ビットが 0 (実行専用) だった場合のアクセス権限テスト"""
    tb = PTWTester(dut)
    await run_s2_fault_injection_test(tb, dut, "LEAF_R_0", 0)

@cocotb.test()
async def test_s2_fault_leaf_d_0_store(dut):
    """Store命令実行時に Leaf PTE の D ビットが 0 だった場合のテスト"""
    tb = PTWTester(dut)
    await run_s2_fault_injection_test(tb, dut, "LEAF_D_0_STORE", 0)

@cocotb.test()
async def test_s2_fault_leaf_w_0_store(dut):
    """Store命令実行時に Leaf PTE の W ビットが 0 (書き込み権限なし) だった場合のテスト"""
    tb = PTWTester(dut)
    await run_s2_fault_injection_test(tb, dut, "LEAF_W_0_STORE", 0)
