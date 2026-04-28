"""
Nested (S1 + S2) 2段階変換 フォルト注入テスト  — フォルト種別 (2)〜(8) を網羅。

対象フォルト:
  (2) PTE.reserved != 0
  (3) AXI RRESP != OKAY
  (4) Non-Leaf PTE に A/D/U ビットが立つ (全7パターン)
  (5) 最終階層 (L0) に Non-Leaf PTE
  (6) Leaf PTE の A=0
  (7) Leaf PTE の R=0
  (8) Store 時に Leaf PTE の D=0

各フォルトを、ネスト変換中の以下いずれかの PTE 位置に注入する:
  - S1_L2 / S1_L1 / S1_L0                      (S1 ウォーク 各階層)
  - S2_L2_FOR_S1ROOT / S2_L1_FOR_S1ROOT / S2_L0_FOR_S1ROOT
      ( S1 Root を読むための S2 ウォーク 各階層 )
  - S2_L2_FOR_S1L1 / S2_L1_FOR_S1L1 / S2_L0_FOR_S1L1
  - S2_L2_FOR_S1L0 / S2_L1_FOR_S1L0 / S2_L0_FOR_S1L0
  - S2_L2_FINAL / S2_L1_FINAL / S2_L0_FINAL
      ( 最終 GPA→SPA 変換の S2 ウォーク )
"""

import cocotb
import random
from cocotb.triggers import Timer
from ptw_helpers import *


# =============================================================================
# Sv39 PTE ビット定義
# =============================================================================
#   [63:54] reserved(10) / [53:10] PPN(44) / [9:8] RSW / [7:0] D A G U X W R V
# =============================================================================
V_BIT, R_BIT, W_BIT, X_BIT = 0, 1, 2, 3
U_BIT, G_BIT, A_BIT, D_BIT = 4, 5, 6, 7
RESERVED_HIGH_BIT = 63


def _bit(n):
    return 1 << n


# =============================================================================
# 不正 PTE ビルダ群
# =============================================================================
def _leaf_base(ppn, stage):
    return PteFactory.s1_leaf(ppn=ppn) if stage == 1 else PteFactory.s2_leaf(ppn=ppn)


def pte_reserved(ppn, *, leaf, stage):
    """Reserved ビット (bit63) を立てた PTE。"""
    base = _leaf_base(ppn, stage) if leaf else PteFactory.non_leaf(ppn=ppn)
    return base | _bit(RESERVED_HIGH_BIT)


def pte_rw_illegal(ppn, *, stage):
    """R=0, W=1 の違法エンコーディング (RISC-V Reserved)。"""
    p = _leaf_base(ppn, stage)
    p &= ~_bit(R_BIT)
    p |=  _bit(W_BIT)
    return p


def pte_nonleaf_adu(ppn, *, a, d, u):
    """Non-Leaf PTE に A/D/U を立てたもの。"""
    p = PteFactory.non_leaf(ppn=ppn)
    if a: p |= _bit(A_BIT)
    if d: p |= _bit(D_BIT)
    if u: p |= _bit(U_BIT)
    return p


def pte_l0_nonleaf(ppn):
    """L0 階層に Non-Leaf PTE を置く (V=1, R=W=X=0)。"""
    return PteFactory.non_leaf(ppn=ppn)


def pte_leaf_clear(ppn, *, bit, stage):
    """Leaf PTE の特定ビットだけクリアしたもの。"""
    return _leaf_base(ppn, stage) & ~_bit(bit)


# =============================================================================
# フォルト指定
# =============================================================================
class FaultSpec:
    """
    site: 注入位置 ("S1_L2", "S2_L0_FOR_S1ROOT", "S2_L0_FINAL" 等)
    kind: フォルト種別 ("RESERVED" / "RW_ILLEGAL" / "RRESP" /
                       "NONLEAF_ADU" / "L0_NONLEAF" /
                       "LEAF_A0" / "LEAF_R0" / "LEAF_D0")
    params: kind 固有パラメータ (例: NONLEAF_ADU の (a,d,u) )
    """
    def __init__(self, site, kind, **params):
        self.site = site
        self.kind = kind
        self.params = params

    def matches(self, site):
        return self.site == site

    def __repr__(self):
        extra = f" {self.params}" if self.params else ""
        return f"<Fault {self.kind}@{self.site}{extra}>"


def make_fault_pte(fault, *, is_leaf, stage, ppn):
    """FaultSpec から、その位置に書くべき不正 PTE 値を作る。
       RRESP の場合は None を返し、呼び出し側は正常 PTE + バスエラー注入を行う。"""
    k = fault.kind
    if k == "RESERVED":
        return pte_reserved(ppn, leaf=is_leaf, stage=stage)
    if k == "RW_ILLEGAL":
        assert is_leaf, "RW_ILLEGAL は Leaf 位置のみ"
        return pte_rw_illegal(ppn, stage=stage)
    if k == "NONLEAF_ADU":
        assert not is_leaf, "NONLEAF_ADU は Non-Leaf 位置のみ"
        return pte_nonleaf_adu(ppn, **fault.params)
    if k == "L0_NONLEAF":
        assert is_leaf, "L0_NONLEAF は L0 位置のみ"
        return pte_l0_nonleaf(ppn)
    if k == "LEAF_A0":
        assert is_leaf
        return pte_leaf_clear(ppn, bit=A_BIT, stage=stage)
    if k == "LEAF_R0":
        assert is_leaf
        return pte_leaf_clear(ppn, bit=R_BIT, stage=stage)
    if k == "LEAF_D0":
        assert is_leaf
        return pte_leaf_clear(ppn, bit=D_BIT, stage=stage)
    if k == "RRESP":
        return None   # 正常値を書いて、バス側に RRESP エラーを仕込む
    raise ValueError(f"未知の fault kind: {k}")


def _has_bus_error_api(tb):
    """テストベンチに RRESP エラー注入 API があるか。"""
    return any(hasattr(tb.ram, n)
               for n in ("inject_rresp_error", "set_bus_error", "inject_bus_error"))


def inject_bus_error(tb, addr):
    """AXI RRESP != OKAY を該当アドレスのリードに注入する。
       実装はテストベンチ依存。典型名を順に試す。呼び出し前に必ず
       _has_bus_error_api(tb) で有無を確認すること。"""
    for method_name in ("inject_rresp_error", "set_bus_error", "inject_bus_error"):
        fn = getattr(tb.ram, method_name, None)
        if fn is not None:
            fn(addr)
            return
    raise RuntimeError(
        "tb.ram に RRESP エラー注入メソッドが見つかりません。"
        "テストベンチ側に inject_rresp_error(addr) 等を実装してください。"
    )


# =============================================================================
# RAM 読み出し & PTE 解析 (S2 ウォーク再利用用)
# =============================================================================
def _read_pte(tb, addr):
    """RAM の指定アドレスから PTE (64bit) を読む。無ければ 0。"""
    mem = getattr(tb.ram, "mem", None)
    if mem is not None:
        try:
            return mem.get(addr, 0)
        except AttributeError:
            pass
    read_fn = getattr(tb.ram, "read", None)
    if read_fn is not None:
        return read_fn(addr)
    return 0


def _pte_is_valid_nonleaf(pte):
    """V=1 かつ R=W=X=0 なら Non-Leaf として使える。"""
    if (pte & 0x1) == 0:
        return False
    return (pte & 0b1110) == 0   # R/W/X 全て 0


def _pte_get_ppn(pte):
    """PTE の PPN フィールド [53:10] を取り出す。"""
    return (pte >> 10) & 0xFFFFFFFFFFF


# =============================================================================
# S2 サブウォーク (フォルト注入対応)
# =============================================================================
def build_s2_subwalk(tb, pmm, s2_root_ppn, gpa, *, walk_label,
                     fault=None, target_spa=None):
    """
    gpa (GPA) → SPA の S2 3段ウォークを RAM に構築する。

    walk_label: "S1ROOT" / "S1L1" / "S1L0" / "FINAL"
    fault: FaultSpec (任意)。site が "S2_L{0,1,2}_FOR_{walk_label}" または
           walk_label="FINAL" なら "S2_L{0,1,2}_FINAL" に一致すれば注入。
    target_spa: 最終リーフが指すべき SPA (None なら新規 alloc)

    戻り値: (spa, fault_consumed)
      fault_consumed=True なら、この呼び出しでフォルトを仕込んだ (以降不要)
    """
    vpn2 = (gpa >> 30) & 0x1FF
    vpn1 = (gpa >> 21) & 0x1FF
    vpn0 = (gpa >> 12) & 0x1FF
    levels = [(2, vpn2), (1, vpn1), (0, vpn0)]

    cur_ppn = s2_root_ppn
    for lvl, vpn_bits in levels:
        entry_addr = (cur_ppn << 12) + vpn_bits * 8
        if walk_label == "FINAL":
            site_here = f"S2_L{lvl}_FINAL"
        else:
            site_here = f"S2_L{lvl}_FOR_{walk_label}"
        is_leaf = (lvl == 0)

        if fault is not None and fault.matches(site_here):
            # --- フォルト注入 (既存 PTE を上書き) ---
            nxt_ppn = pmm.alloc_ppn()
            fault_pte = make_fault_pte(fault, is_leaf=is_leaf, stage=2, ppn=nxt_ppn)
            if fault_pte is not None:
                tb.ram.write(entry_addr, fault_pte)
            else:
                # RRESP: 正常 PTE を書きつつ、バス側でエラー応答
                if is_leaf:
                    dummy = (target_spa >> 12 if target_spa is not None
                             else pmm.alloc_ppn())
                    tb.ram.write(entry_addr, PteFactory.s2_leaf(ppn=dummy))
                else:
                    tb.ram.write(entry_addr, PteFactory.non_leaf(ppn=nxt_ppn))
                inject_bus_error(tb, entry_addr)
            return None, True

        # --- 正常ケース: 既存エントリがあれば再利用 ---
        if is_leaf:
            # L0 は GPA 毎に一意なので常に新規 (※ 同じ GPA で 2 回呼ばない前提)
            if target_spa is None:
                target_spa = pmm.alloc_ppn() << 12
            tb.ram.write(entry_addr, PteFactory.s2_leaf(ppn=target_spa >> 12))
            return target_spa, False
        else:
            existing = _read_pte(tb, entry_addr)
            if _pte_is_valid_nonleaf(existing):
                # 既に有効な Non-Leaf PTE が書いてある → 再利用
                cur_ppn = _pte_get_ppn(existing)
            else:
                nxt_ppn = pmm.alloc_ppn()
                tb.ram.write(entry_addr, PteFactory.non_leaf(ppn=nxt_ppn))
                cur_ppn = nxt_ppn

    raise RuntimeError("unreachable")


# =============================================================================
# Nested ウォーク全体の構築
# =============================================================================
def build_nested_memory(tb, pmm, iova_39, s1_root_gppn, s2_root_ppn, fault):
    """
    S1 3段 + 各段ごとの S2 ウォーク + 最終 GPA→SPA S2 ウォーク
    を全て RAM に構築する。fault.site が指す位置で注入する。

    戻り値: True なら正常構築完了 (PTW は成功するはず), False はここでフォルト済み
    """
    vpn2_s1 = (iova_39 >> 30) & 0x1FF
    vpn1_s1 = (iova_39 >> 21) & 0x1FF
    vpn0_s1 = (iova_39 >> 12) & 0x1FF

    def _maybe_s1_fault(site, is_leaf, cur_ppn_placeholder):
        """S1 PTE 位置での注入判定。命中すれば PTE を書き込んで True を返す。"""
        if fault is None or not fault.matches(site):
            return False
        nxt_ppn = pmm.alloc_ppn()
        fp = make_fault_pte(fault, is_leaf=is_leaf, stage=1, ppn=nxt_ppn)
        if fp is not None:
            tb.ram.write(cur_ppn_placeholder, fp)
        else:
            # RRESP: 正常 PTE + バスエラー
            if is_leaf:
                dummy = pmm.alloc_ppn()
                tb.ram.write(cur_ppn_placeholder, PteFactory.s1_leaf(ppn=dummy))
            else:
                tb.ram.write(cur_ppn_placeholder, PteFactory.non_leaf(ppn=nxt_ppn))
            inject_bus_error(tb, cur_ppn_placeholder)
        return True

    # ---- (1) S1 Root を読むための S2 ウォーク ----
    s1_root_spa, consumed = build_s2_subwalk(
        tb, pmm, s2_root_ppn, s1_root_gppn << 12,
        walk_label="S1ROOT", fault=fault,
    )
    if consumed:
        return False

    # ---- (2) S1 Root PTE (VPN2) ----
    s1_l2_addr = s1_root_spa + vpn2_s1 * 8
    if _maybe_s1_fault("S1_L2", is_leaf=False, cur_ppn_placeholder=s1_l2_addr):
        return False
    s1_l1_gppn = pmm.alloc_ppn()
    tb.ram.write(s1_l2_addr, PteFactory.non_leaf(ppn=s1_l1_gppn))

    # ---- (3) S1 L1 を読むための S2 ウォーク ----
    s1_l1_spa, consumed = build_s2_subwalk(
        tb, pmm, s2_root_ppn, s1_l1_gppn << 12,
        walk_label="S1L1", fault=fault,
    )
    if consumed:
        return False

    # ---- (4) S1 L1 PTE (VPN1) ----
    s1_l1_addr = s1_l1_spa + vpn1_s1 * 8
    if _maybe_s1_fault("S1_L1", is_leaf=False, cur_ppn_placeholder=s1_l1_addr):
        return False
    s1_l0_gppn = pmm.alloc_ppn()
    tb.ram.write(s1_l1_addr, PteFactory.non_leaf(ppn=s1_l0_gppn))

    # ---- (5) S1 L0 を読むための S2 ウォーク ----
    s1_l0_spa, consumed = build_s2_subwalk(
        tb, pmm, s2_root_ppn, s1_l0_gppn << 12,
        walk_label="S1L0", fault=fault,
    )
    if consumed:
        return False

    # ---- (6) S1 L0 PTE (VPN0, リーフ) ----
    s1_l0_addr = s1_l0_spa + vpn0_s1 * 8
    if _maybe_s1_fault("S1_L0", is_leaf=True, cur_ppn_placeholder=s1_l0_addr):
        return False
    final_gppn = pmm.alloc_ppn()
    tb.ram.write(s1_l0_addr, PteFactory.s1_leaf(ppn=final_gppn))

    # ---- (7) 最終 GPA→SPA の S2 ウォーク ----
    final_spa, consumed = build_s2_subwalk(
        tb, pmm, s2_root_ppn, final_gppn << 12,
        walk_label="FINAL", fault=fault,
    )
    if consumed:
        return False

    return True


# =============================================================================
# 1 ケース実行
# =============================================================================
async def _run_one(dut, tb, fault, idx, *, is_store=False):
    dut._log.info(f"  [{fault}] run#{idx}  store={is_store}")

    await tb.reset()
    tb.ram.mem.clear()
    pmm = PhysicalMemoryManager(start_ppn=0x1000)

    iova_39 = random.getrandbits(39)
    iova_64 = format_sv39_iova(iova_39)

    s2_root_ppn  = pmm.alloc_ppn() & ~0x3          # Sv39x4 アライメント
    s1_root_gppn = pmm.alloc_ppn()

    tb.dut.iosatp_ppn_i.value  = s1_root_gppn
    tb.dut.iohgatp_ppn_i.value = s2_root_ppn
    tb.dut.en_1S_i.value = 1
    tb.dut.en_2S_i.value = 1

    ok = build_nested_memory(tb, pmm, iova_39, s1_root_gppn, s2_root_ppn, fault)

    # trigger - store/load 指定に対応
    try:
        await tb.trigger(iova=iova_64, is_store=is_store)
    except TypeError:
        # 旧シグネチャ (is_store なし) 用フォールバック
        if is_store and hasattr(tb, "trigger_store"):
            await tb.trigger_store(iova=iova_64)
        else:
            await tb.trigger(iova=iova_64)

    result = await tb.wait_completion()

    if not ok:
        assert result != "SUCCESS", \
            f"[{fault}] フォルトを仕込んだのに SUCCESS が返った (result={result})"
        dut._log.info(f"    -> 期待どおりフォルト検出 (result={result})")
    else:
        # 構築段階でフォルトが入らなかった場合は SUCCESS 期待
        assert result == "SUCCESS", \
            f"[{fault}] フォルト未注入のはずが result={result}"
        dut._log.info(f"    -> 正常完了 (result={result})")


# =============================================================================
# 各フォルト種別のテストケース列挙
# =============================================================================
ALL_S1_SITES  = ["S1_L2", "S1_L1", "S1_L0"]
ALL_S2_SITES  = [
    "S2_L2_FOR_S1ROOT", "S2_L1_FOR_S1ROOT", "S2_L0_FOR_S1ROOT",
    "S2_L2_FOR_S1L1",   "S2_L1_FOR_S1L1",   "S2_L0_FOR_S1L1",
    "S2_L2_FOR_S1L0",   "S2_L1_FOR_S1L0",   "S2_L0_FOR_S1L0",
    "S2_L2_FINAL",      "S2_L1_FINAL",      "S2_L0_FINAL",
]
ALL_SITES = ALL_S1_SITES + ALL_S2_SITES

LEAF_SITES    = ["S1_L0", "S2_L0_FOR_S1ROOT", "S2_L0_FOR_S1L1",
                 "S2_L0_FOR_S1L0", "S2_L0_FINAL"]
NONLEAF_SITES = [s for s in ALL_SITES if s not in LEAF_SITES]

# 7 パターンの A/D/U (全 0 以外の組み合わせ)
ADU_PATTERNS = [(a, d, u)
                for a in (0, 1) for d in (0, 1) for u in (0, 1)
                if (a, d, u) != (0, 0, 0)]


# =============================================================================
# テスト (1) : reserved != 0
# =============================================================================
@cocotb.test()
async def test_fault_reserved_nonzero(dut):
    """PTE.reserved != 0 を各 PTE 位置に注入。"""
    dut._log.info("=== (2) PTE.reserved != 0 ===")
    tb = PTWTester(dut)
    RUNS = 3
    for site in ALL_SITES:
        is_leaf_site = site in LEAF_SITES
        for i in range(RUNS):
            fault = FaultSpec(site, "RESERVED")
            await _run_one(dut, tb, fault, i + 1)
    dut._log.info("🎉 RESERVED フォルト網羅完了")
    await Timer(100, unit="ns")


# =============================================================================
# テスト (2) : V=0 または R=0,W=1  (R=0,W=1 をここで補完)
# =============================================================================
@cocotb.test()
async def test_fault_rw_illegal(dut):
    """Leaf PTE に R=0, W=1 の違法エンコードを注入。"""
    dut._log.info("=== (1b) PTE.R=0, W=1 (Reserved エンコード) ===")
    tb = PTWTester(dut)
    RUNS = 5
    for site in LEAF_SITES:
        for i in range(RUNS):
            fault = FaultSpec(site, "RW_ILLEGAL")
            await _run_one(dut, tb, fault, i + 1)
    dut._log.info("🎉 R=0/W=1 フォルト網羅完了")
    await Timer(100, unit="ns")


# =============================================================================
# テスト (3) : AXI RRESP != OKAY
# =============================================================================
@cocotb.test()
async def test_fault_axi_rresp(dut):
    """あらゆる PTE リードに対して RRESP != OKAY を返す。
       テストベンチ側に RRESP 注入 API が無い場合はスキップ。"""
    dut._log.info("=== (3) AXI RRESP != OKAY ===")
    tb = PTWTester(dut)
    if not _has_bus_error_api(tb):
        dut._log.warning(
            "tb.ram に RRESP エラー注入メソッド (inject_rresp_error 等) が無いため、"
            "このテストはスキップします。テストベンチ側に API を実装してから有効化してください。"
        )
        return
    RUNS = 3
    for site in ALL_SITES:
        for i in range(RUNS):
            fault = FaultSpec(site, "RRESP")
            await _run_one(dut, tb, fault, i + 1)
    dut._log.info("🎉 RRESP フォルト網羅完了")
    await Timer(100, unit="ns")


# =============================================================================
# テスト (4) : Non-Leaf PTE に A/D/U が立つ (全 7 パターン)
# =============================================================================
@cocotb.test()
async def test_fault_nonleaf_adu(dut):
    """Non-Leaf 位置の PTE に A/D/U の 7 パターンを注入。"""
    dut._log.info("=== (4) Non-Leaf に A/D/U (7 パターン) ===")
    tb = PTWTester(dut)
    for (a, d, u) in ADU_PATTERNS:
        dut._log.info(f"  --- パターン (A,D,U)=({a},{d},{u}) ---")
        for site in NONLEAF_SITES:
            fault = FaultSpec(site, "NONLEAF_ADU", a=a, d=d, u=u)
            await _run_one(dut, tb, fault, 1)
    dut._log.info(
        f"🎉 Non-Leaf A/D/U フォルト網羅完了 "
        f"({len(ADU_PATTERNS)}×{len(NONLEAF_SITES)}箇所)"
    )
    await Timer(100, unit="ns")


# =============================================================================
# テスト (5) : 最終階層 (L0) が Non-Leaf
# =============================================================================
@cocotb.test()
async def test_fault_l0_nonleaf(dut):
    """L0 位置に Non-Leaf PTE を置く。"""
    dut._log.info("=== (5) L0 に Non-Leaf PTE ===")
    tb = PTWTester(dut)
    RUNS = 5
    for site in LEAF_SITES:
        for i in range(RUNS):
            fault = FaultSpec(site, "L0_NONLEAF")
            await _run_one(dut, tb, fault, i + 1)
    dut._log.info("🎉 L0 Non-Leaf フォルト網羅完了")
    await Timer(100, unit="ns")


# =============================================================================
# テスト (6) : Leaf PTE の A=0
# =============================================================================
@cocotb.test()
async def test_fault_leaf_a0(dut):
    """Leaf PTE で A=0。"""
    dut._log.info("=== (6) Leaf A=0 ===")
    tb = PTWTester(dut)
    RUNS = 5
    for site in LEAF_SITES:
        for i in range(RUNS):
            fault = FaultSpec(site, "LEAF_A0")
            await _run_one(dut, tb, fault, i + 1)
    dut._log.info("🎉 Leaf A=0 フォルト網羅完了")
    await Timer(100, unit="ns")


# =============================================================================
# テスト (7) : Leaf PTE の R=0
# =============================================================================
@cocotb.test()
async def test_fault_leaf_r0(dut):
    """Leaf PTE で R=0 (読み取り権限なし) — ロードアクセスで検出されるはず。"""
    dut._log.info("=== (7) Leaf R=0 ===")
    tb = PTWTester(dut)
    RUNS = 5
    # R=0 は S1/S2 どちらでも成立するが、特に S1 leaf (S1_L0) が典型
    for site in LEAF_SITES:
        for i in range(RUNS):
            fault = FaultSpec(site, "LEAF_R0")
            await _run_one(dut, tb, fault, i + 1, is_store=False)
    dut._log.info("🎉 Leaf R=0 フォルト網羅完了")
    await Timer(100, unit="ns")


# =============================================================================
# テスト (8) : Store 時に Leaf PTE の D=0
# =============================================================================
@cocotb.test()
async def test_fault_store_leaf_d0(dut):
    """Store アクセス時に Leaf PTE の D=0 → Store/AMO Page Fault になるはず。"""
    dut._log.info("=== (8) Store 時 Leaf D=0 ===")
    tb = PTWTester(dut)
    RUNS = 5
    for site in LEAF_SITES:
        for i in range(RUNS):
            fault = FaultSpec(site, "LEAF_D0")
            await _run_one(dut, tb, fault, i + 1, is_store=True)
    dut._log.info("🎉 Store + D=0 フォルト網羅完了")
    await Timer(100, unit="ns")


# =============================================================================
# 参考: 正常系 (フォルト無し) のサニティテスト
# =============================================================================
@cocotb.test()
async def test_nested_sanity_no_fault(dut):
    """フォルト未注入時に SUCCESS を返すことを確認するサニティ。"""
    dut._log.info("=== サニティ: Nested 変換 正常系 ===")
    tb = PTWTester(dut)
    for i in range(10):
        await _run_one(dut, tb, fault=None, idx=i + 1)
    dut._log.info("🎉 正常系サニティ OK")
    await Timer(100, unit="ns")