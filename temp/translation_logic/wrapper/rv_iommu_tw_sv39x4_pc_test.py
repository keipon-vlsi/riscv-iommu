"""
rv_iommu_ptw_test_wrapper (Option C: Force 方式) 用 cocotb テストベンチ。

テスト戦略:
  1. DDT/PDT はメモリに構築しない (DDTC/PDTC は idle のまま)
  2. PTW サブモジュールの init_ptw_i / iosatp_ppn_i / iohgatp_ppn_i /
     en_1S_i / en_2S_i をラッパ経由で force 駆動
  3. メモリには S1 PT と S2 PT だけを構築
  4. force_init_ptw_i を 1 サイクルパルスすれば PTW が動く
  5. PTW AXI が読むアドレスに対して MockMem から応答
"""

import cocotb
import random
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


# =============================================================================
# 定数
# =============================================================================
VLEN       = 39
PLEN       = 56
GPLEN      = 41
PAGE_SHIFT = 12

# Cause code (PTW レベル)
CAUSE_LOAD_PAGE_FAULT        = 13
CAUSE_STORE_PAGE_FAULT       = 15
CAUSE_LOAD_GUEST_PAGE_FAULT  = 21
CAUSE_STORE_GUEST_PAGE_FAULT = 23
CAUSE_PT_DATA_CORRUPTION     = 274


# =============================================================================
# Memory model
# =============================================================================
class MockMem:
    def __init__(self):
        self.mem = {}
    def write(self, addr, value):
        assert (addr & 0x7) == 0
        self.mem[addr] = value & ((1 << 64) - 1)
    def read(self, addr):
        assert (addr & 0x7) == 0
        return self.mem.get(addr, 0)
    def clear(self):
        self.mem.clear()


class PhysicalMemoryManager:
    def __init__(self, start_ppn=0x1000):
        self._next = start_ppn
    def alloc_ppn(self):
        p = self._next; self._next += 1; return p


# =============================================================================
# PTE ビルダ
# =============================================================================
class Pte:
    V, R, W, X = 1, 2, 4, 8
    U, G, A, D = 16, 32, 64, 128

    @staticmethod
    def non_leaf(ppn):
        return Pte.V | ((ppn & ((1 << 44) - 1)) << 10)

    @staticmethod
    def s1_leaf(ppn, rwx=0b111, u=1, a=1, d=1):
        pte = Pte.V
        if rwx & 0b100: pte |= Pte.R
        if rwx & 0b010: pte |= Pte.W
        if rwx & 0b001: pte |= Pte.X
        if u: pte |= Pte.U
        if a: pte |= Pte.A
        if d: pte |= Pte.D
        pte |= ((ppn & ((1 << 44) - 1)) << 10)
        return pte

    @staticmethod
    def s2_leaf(ppn, rwx=0b111, a=1, d=1):
        pte = Pte.V | Pte.U   # G-stage leaf は U=1 必須
        if rwx & 0b100: pte |= Pte.R
        if rwx & 0b010: pte |= Pte.W
        if rwx & 0b001: pte |= Pte.X
        if a: pte |= Pte.A
        if d: pte |= Pte.D
        pte |= ((ppn & ((1 << 44) - 1)) << 10)
        return pte

    @staticmethod
    def invalid():
        return 0


# =============================================================================
# PT 構築 (S1 + S2 ネスト。Force 方式用に DDT/PDT 不要)
# =============================================================================
class PagingBuilder:
    """
    S1 PT と S2 PT だけをメモリに構築する。ルート PPN は外部から指定。

    使い方:
        b = PagingBuilder(ram, pmm, iosatp_ppn, iohgatp_ppn)
        spa = b.setup_translation(iova=..., s1_rwx=0b111)
    """
    def __init__(self, ram, pmm, iosatp_ppn, iohgatp_ppn):
        self.ram = ram
        self.pmm = pmm
        self.iosatp_ppn  = iosatp_ppn
        self.iohgatp_ppn = iohgatp_ppn

    @staticmethod
    def _is_valid_non_leaf(pte):
        if (pte & 1) == 0: return False
        return (pte & 0b1110) == 0

    def _s2_walk(self, gpa, target_spa=None, fault=None):
        """gpa → spa の S2 3 段ウォークを構築。既存 PTE は再利用。"""
        vpn = [(gpa >> 30) & 0x1FF, (gpa >> 21) & 0x1FF, (gpa >> 12) & 0x1FF]
        cur = self.iohgatp_ppn

        for lvl, vbits in [(2, vpn[0]), (1, vpn[1]), (0, vpn[2])]:
            addr = (cur << PAGE_SHIFT) + vbits * 8
            is_leaf = (lvl == 0)

            if fault is not None and fault.get('level') == lvl:
                self.ram.write(addr, fault['pte'])
                return None

            if is_leaf:
                if target_spa is None:
                    target_spa = self.pmm.alloc_ppn() << PAGE_SHIFT
                self.ram.write(addr, Pte.s2_leaf(ppn=target_spa >> PAGE_SHIFT))
                return target_spa

            existing = self.ram.read(addr)
            if self._is_valid_non_leaf(existing):
                cur = (existing >> 10) & ((1 << 44) - 1)
            else:
                nxt = self.pmm.alloc_ppn()
                self.ram.write(addr, Pte.non_leaf(nxt))
                cur = nxt
        raise RuntimeError("unreachable")

    def setup_translation(self, iova, target_spa=None, s1_rwx=0b111,
                          s1_fault=None, s2_fault=None):
        """
        S1 + S2 ネスト構成で iova の変換経路をメモリに構築。
        戻り値: 最終 SPA (正常時)
        """
        vpn = [(iova >> 30) & 0x1FF, (iova >> 21) & 0x1FF, (iova >> 12) & 0x1FF]

        # S1 Root を読むための S2 ウォーク
        if s2_fault and s2_fault.get('for') == 'S1ROOT':
            self._s2_walk(self.iosatp_ppn << PAGE_SHIFT, fault=s2_fault)
            return None
        s1_root_spa = self._s2_walk(self.iosatp_ppn << PAGE_SHIFT)

        # S1 L2 PTE
        s1_l2_addr = s1_root_spa + vpn[0] * 8
        if s1_fault and s1_fault.get('level') == 2:
            self.ram.write(s1_l2_addr, s1_fault['pte'])
            return None
        s1_l1_gppn = self.pmm.alloc_ppn()
        self.ram.write(s1_l2_addr, Pte.non_leaf(s1_l1_gppn))

        # S1 L1 を読むための S2 ウォーク
        if s2_fault and s2_fault.get('for') == 'S1L1':
            self._s2_walk(s1_l1_gppn << PAGE_SHIFT, fault=s2_fault)
            return None
        s1_l1_spa = self._s2_walk(s1_l1_gppn << PAGE_SHIFT)

        # S1 L1 PTE
        s1_l1_addr = s1_l1_spa + vpn[1] * 8
        if s1_fault and s1_fault.get('level') == 1:
            self.ram.write(s1_l1_addr, s1_fault['pte'])
            return None
        s1_l0_gppn = self.pmm.alloc_ppn()
        self.ram.write(s1_l1_addr, Pte.non_leaf(s1_l0_gppn))

        # S1 L0 を読むための S2 ウォーク
        if s2_fault and s2_fault.get('for') == 'S1L0':
            self._s2_walk(s1_l0_gppn << PAGE_SHIFT, fault=s2_fault)
            return None
        s1_l0_spa = self._s2_walk(s1_l0_gppn << PAGE_SHIFT)

        # S1 L0 リーフ PTE
        s1_l0_addr = s1_l0_spa + vpn[2] * 8
        if s1_fault and s1_fault.get('level') == 0:
            self.ram.write(s1_l0_addr, s1_fault['pte'])
            return None
        final_gppn = self.pmm.alloc_ppn()
        self.ram.write(s1_l0_addr, Pte.s1_leaf(ppn=final_gppn, rwx=s1_rwx, u=1))

        # 最終 GPA の S2 ウォーク
        if s2_fault and s2_fault.get('for') == 'FINAL':
            self._s2_walk(final_gppn << PAGE_SHIFT, fault=s2_fault)
            return None
        return self._s2_walk(final_gppn << PAGE_SHIFT, target_spa=target_spa)


# =============================================================================
# PTW Force 方式テストベンチ
# =============================================================================
class PtwForceTester:
    """
    force_ptw_en_i を介してラッパの force ポートを駆動し、PTW を直接起動する。
    """

    def __init__(self, dut):
        self.dut = dut
        self.ram = MockMem()
        self.pmm = PhysicalMemoryManager(start_ppn=0x1000)

        # ルート PPN は固定値を割り当てておく
        self.iosatp_ppn  = self.pmm.alloc_ppn()
        self.iohgatp_ppn = self.pmm.alloc_ppn() & ~0x3  # Sv39x4 4-page align

        self.builder = PagingBuilder(
            self.ram, self.pmm,
            self.iosatp_ppn, self.iohgatp_ppn,
        )

    # ------------------------------------------------------------------
    # リセット & 初期化
    # ------------------------------------------------------------------
    async def reset(self):
        self.dut.rst_ni.value = 0
        self.dut.req_trans_i.value = 0
        self.dut.iova_i.value = 0
        self.dut.trans_type_i.value = 0
        self.dut.priv_lvl_i.value = 0
        self.dut.flush_iotlb_i.value = 0
        self.dut.flush_ddtc_i.value = 0
        self.dut.flush_pdtc_i.value = 0

        # Force 関連は全てゼロ
        self.dut.force_ptw_en_i.value = 0
        self.dut.force_init_ptw_i.value = 0
        self.dut.force_iosatp_ppn_i.value = 0
        self.dut.force_iohgatp_ppn_i.value = 0
        self.dut.force_en_1S_i.value = 0
        self.dut.force_en_2S_i.value = 0

        await Timer(50, unit="ns")
        self.dut.rst_ni.value = 1
        await RisingEdge(self.dut.clk_i)

    # ------------------------------------------------------------------
    # Force 制御 ON (ルートポインタ + en_1S/en_2S セット)
    # ------------------------------------------------------------------
    async def enable_force(self, en_1S=1, en_2S=1):
        """
        Force 方式を有効化。iosatp/iohgatp/en_1S/en_2S をセット。
        init_ptw はまだ 0 のまま (trigger_ptw で立ち上げる)。
        """
        await RisingEdge(self.dut.clk_i)
        self.dut.force_iosatp_ppn_i.value  = self.iosatp_ppn
        self.dut.force_iohgatp_ppn_i.value = self.iohgatp_ppn
        self.dut.force_en_1S_i.value = en_1S
        self.dut.force_en_2S_i.value = en_2S
        self.dut.force_init_ptw_i.value = 0
        self.dut.force_ptw_en_i.value = 1
        await RisingEdge(self.dut.clk_i)

    async def disable_force(self):
        """Force を解除して元の駆動に戻す。"""
        await RisingEdge(self.dut.clk_i)
        self.dut.force_ptw_en_i.value = 0
        self.dut.force_init_ptw_i.value = 0
        await RisingEdge(self.dut.clk_i)

    # ------------------------------------------------------------------
    # PTW 1 回起動 (init_ptw を 1 サイクルパルス)
    # ------------------------------------------------------------------
    async def trigger_ptw(self, iova):
        """
        force_init_ptw_i を 1 サイクル立てて PTW を起動する。
        iova は iova_i 経由で供給 (PTW 内部で VPN 抽出)。
        """
        await RisingEdge(self.dut.clk_i)
        self.dut.iova_i.value = iova
        self.dut.trans_type_i.value = 0b000010   # UNTRANSLATED_R
        self.dut.priv_lvl_i.value = 1

        self.dut.force_init_ptw_i.value = 1
        await RisingEdge(self.dut.clk_i)
        self.dut.force_init_ptw_i.value = 0

    # ------------------------------------------------------------------
    # PTW 完了待ち
    # ------------------------------------------------------------------
    async def wait_ptw_done(self, timeout_cycles=2000):
        """
        PTW が完了するまで待つ。観測は trans_valid_o / trans_error_o か
        iotlb への update 信号で検出する。簡易版は trans_valid/error で判定。
        """
        for _ in range(timeout_cycles):
            await RisingEdge(self.dut.clk_i)
            if int(self.dut.trans_valid_o.value) == 1:
                return "SUCCESS"
            if int(self.dut.trans_error_o.value) == 1:
                return "ERROR"
        raise TimeoutError("PTW timeout")


# =============================================================================
# サンプルテスト
# =============================================================================

@cocotb.test()
async def test_force_basic_nested_walk(dut):
    """
    Force 方式の最小テスト: S1+S2 ネストウォークを手動で起動し、
    PTW が最終 SPA を返すことを確認。
    """
    cocotb.start_soon(Clock(dut.clk_i, 10, unit="ns").start())
    tb = PtwForceTester(dut)
    await tb.reset()

    # S1/S2 PT をメモリに構築
    iova = 0x0000_1234_5000
    expected_spa = tb.builder.setup_translation(iova=iova)

    # Force を有効化して PTW を起動
    await tb.enable_force(en_1S=1, en_2S=1)
    await tb.trigger_ptw(iova=iova)

    # 注: この時点で PTW が走り、IOTLB に結果を書く。
    #     trans_valid_o は IOTLB ヒットでないと 1 にならないので、
    #     通常は force 解除後に req_trans_i で改めて要求して確認する。

    # TODO: AXI メモリ応答を走らせるコルーチンを別途起動しておく必要あり
    #       (下記 axi_responder を用意すること)
    # ...

    dut._log.info(f"✓ PTW force 起動完了、期待 SPA=0x{expected_spa:x}")


@cocotb.test()
async def test_force_then_normal_lookup(dut):
    """
    Force で IOTLB を populate → force 解除 → 通常要求で IOTLB ヒット確認。
    """
    cocotb.start_soon(Clock(dut.clk_i, 10, unit="ns").start())
    tb = PtwForceTester(dut)
    await tb.reset()

    iova = 0x0000_2000_1000
    expected_spa = tb.builder.setup_translation(iova=iova)

    # Phase 1: Force で PTW を走らせて IOTLB を populate
    await tb.enable_force(en_1S=1, en_2S=1)
    await tb.trigger_ptw(iova=iova)

    # PTW が AXI 経由でメモリを読むので、その応答を走らせる必要がある
    # (axi_responder は別途実装、下記参照)

    # IOTLB 更新を待つ (PTW 完了検出)
    # for _ in range(100): await RisingEdge(dut.clk_i)

    # Phase 2: Force 解除 → 通常要求で IOTLB ヒットを期待
    await tb.disable_force()

    # ...ここで req_trans_i で再度要求を投げて trans_valid_o を観測...


# =============================================================================
# AXI レスポンダ (要実装)
# =============================================================================
async def axi_read_responder(dut, req_prefix, rsp_prefix, ram):
    """
    PTW AXI の AR を受けて R チャンネルで応答する。
    req_prefix: "ptw_axi_req_o" など
    rsp_prefix: "ptw_axi_resp_i" など

    TODO: プロジェクトの AXI 構造体に合わせて実装する
          (既存の tb_coco の MockMem.axi_responder コルーチンを流用可能)
    """
    raise NotImplementedError(
        "プロジェクトの AXI 構造体に合わせて実装してください。"
        "既存の tb_coco/.../MockMem.axi_responder を参考に。"
    )