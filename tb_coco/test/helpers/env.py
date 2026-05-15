"""iommu_tb.env — IommuEnv: テストの 1 行目に来る bundle クラス

典型的な使い方:
    @cocotb.test(timeout_time=50, timeout_unit="us")
    async def test_xxx(dut):
        env = IommuEnv(dut)
        await env.setup()                          # クロック+リセット+masters+FQ

        await env.install_dc_sv39_s1(did=0)        # DC 配置 + DDT mode 切替
        env.map_sv39_4k(iova=0x2345, sp_ppn=0x100) # PT 配置

        env.comp_ram.write(spa, data)              # 期待データ
        op = await env.dev_tr_read(0x2345, 8)      # ★ 翻訳実行
        assert int.from_bytes(op.data, "little") == data
"""

import logging

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from cocotbext.axi import AxiBus, AxiMaster, AxiRam

from .const import (
    DDTP_MODE_BARE, DDTP_MODE_1LVL,
    DEFAULT_DDT_BASE_PPN,
    DEFAULT_S1_ROOT_PPN, DEFAULT_S1_MID_PPN, DEFAULT_S1_LEAF_PPN,
    DEFAULT_G_ROOT_PPN,  DEFAULT_G_MID_PPN,  DEFAULT_G_LEAF_PPN,
    DEFAULT_PDT_ROOT_PPN, DEFAULT_PDT_L1_PPN, DEFAULT_PDT_LEAF_PPN,
    DEFAULT_CQ_BASE_PPN, DEFAULT_FQ_BASE_PPN,
    DEFAULT_CQ_LOG2SZ,   DEFAULT_FQ_LOG2SZ,
    PC_PROCESS_ID_FIXED, PC_PSCID_FIXED,
)
from .memory import (
    install_dc_1lvl,
    build_dc_identity, build_dc_sv39_s1, build_dc_sv39x4_s2, build_dc_sv39_2stage,
    build_dc_sv39_s1_pc, build_dc_sv39x4_s2_pc, build_dc_sv39_2stage_pc,
    build_dc_msi,
    install_pdt_pd20, pack_pc_ta, pack_pc_fsc,
    ATGP_MODE_BARE, ATGP_MODE_SV39,
    setup_sv39_4k, setup_sv39_2m, setup_sv39_1g, setup_sv39_custom_leaf,
)
from .regs import configure_ddt_mode
from .faultq import FaultQueue, expect_fault
from .cmdq import CommandQueue


# =============================================================================
# 共通: reset / master factory
# =============================================================================
async def reset_dut(dut, *, cycles: int = 10):
    """active-low reset を cycles サイクル assert → release。

    AXI 入力は reset 前に 0 駆動しておかないと X 値が IOMMU 内部に伝搬する。
    """
    log = logging.getLogger("cocotb.tb.reset")

    # 全 AXI 入力を 0 に倒す (存在しない信号は AttributeError → skip)
    sigs = (_PROG_INPUT_SIGS + _TR_INPUT_SIGS
            + _COMP_RESPONSE_SIGS + _DS_RESPONSE_SIGS)
    for sig in sigs:
        try:
            getattr(dut, sig).value = 0
        except AttributeError:
            pass

    dut.rst_ni.value = 0
    log.info("Reset asserted")
    for _ in range(cycles):
        await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 1
    log.info("Reset de-asserted")
    for _ in range(5):
        await RisingEdge(dut.clk_i)


# tr の DVM 拡張も含む (cocotbext-axi の AxiBus からは見えないので手駆動)
_PROG_INPUT_SIGS = [
    "prog_awid", "prog_awaddr", "prog_awlen", "prog_awsize", "prog_awburst",
    "prog_awlock", "prog_awcache", "prog_awprot", "prog_awqos", "prog_awregion",
    "prog_awatop", "prog_awuser", "prog_awvalid",
    "prog_wdata", "prog_wstrb", "prog_wlast", "prog_wuser", "prog_wvalid",
    "prog_bready",
    "prog_arid", "prog_araddr", "prog_arlen", "prog_arsize", "prog_arburst",
    "prog_arlock", "prog_arcache", "prog_arprot", "prog_arqos", "prog_arregion",
    "prog_aruser", "prog_arvalid",
    "prog_rready",
]
_TR_INPUT_SIGS = [
    "tr_awid", "tr_awaddr", "tr_awlen", "tr_awsize", "tr_awburst",
    "tr_awlock", "tr_awcache", "tr_awprot", "tr_awqos", "tr_awregion",
    "tr_awatop", "tr_awuser", "tr_awvalid",
    "tr_aw_stream_id", "tr_aw_ss_id_valid", "tr_aw_substream_id",
    "tr_wdata", "tr_wstrb", "tr_wlast", "tr_wuser", "tr_wvalid",
    "tr_bready",
    "tr_arid", "tr_araddr", "tr_arlen", "tr_arsize", "tr_arburst",
    "tr_arlock", "tr_arcache", "tr_arprot", "tr_arqos", "tr_arregion",
    "tr_aruser", "tr_arvalid",
    "tr_ar_stream_id", "tr_ar_ss_id_valid", "tr_ar_substream_id",
    "tr_rready",
]
_COMP_RESPONSE_SIGS = [
    "comp_awready", "comp_wready",
    "comp_bid", "comp_bresp", "comp_buser", "comp_bvalid",
    "comp_arready",
    "comp_rid", "comp_rdata", "comp_rresp", "comp_rlast", "comp_ruser", "comp_rvalid",
]
_DS_RESPONSE_SIGS = [
    "ds_awready", "ds_wready",
    "ds_bid", "ds_bresp", "ds_buser", "ds_bvalid",
    "ds_arready",
    "ds_rid", "ds_rdata", "ds_rresp", "ds_rlast", "ds_ruser", "ds_rvalid",
]


# =============================================================================
# IommuEnv 本体
# =============================================================================
class IommuEnv:
    """4 つの AXI ポート / レジスタ / 各 queue を一括して扱う bundle。

    属性:
        dut:           cocotb の DUT handle
        prog_master:   prog AXI master (regmap I/O)
        tr_master:     dev_tr AXI master (デバイス側からの翻訳要求)
        comp_ram:      dev_comp AXI slave (= 物理メモリ模擬)
        ds_ram:        ds AXI slave (= データ構造領域: DDT/PT/CQ/FQ)
        fq:            FaultQueue (env.setup() で setup 済み)
        cq:            CommandQueue (env.enable_cq() を呼ぶと使えるように)

    レイアウト定数:
        ddt_base_ppn / s1_root/mid/leaf_ppn etc.
        テストで上書きしたければ env.ddt_base_ppn = 0x42 のように代入可。
    """

    def __init__(self, dut, *,
                  clock_period_ns: int = 10,
                  ds_ram_size: int = 0x1000000,        # 16 MiB
                  comp_ram_size: int = 0x100_000_000, # 4 GiB sparse
                  ddt_base_ppn: int = DEFAULT_DDT_BASE_PPN,
                  s1_root_ppn: int = DEFAULT_S1_ROOT_PPN,
                  s1_mid_ppn:  int = DEFAULT_S1_MID_PPN,
                  s1_leaf_ppn: int = DEFAULT_S1_LEAF_PPN,
                  g_root_ppn:  int = DEFAULT_G_ROOT_PPN,
                  g_mid_ppn:   int = DEFAULT_G_MID_PPN,
                  g_leaf_ppn:  int = DEFAULT_G_LEAF_PPN,
                  pdt_root_ppn: int = DEFAULT_PDT_ROOT_PPN,
                  pdt_l1_ppn:   int = DEFAULT_PDT_L1_PPN,
                  pdt_leaf_ppn: int = DEFAULT_PDT_LEAF_PPN,
                  cq_base_ppn: int = DEFAULT_CQ_BASE_PPN,
                  fq_base_ppn: int = DEFAULT_FQ_BASE_PPN,
                  cq_log2sz:   int = DEFAULT_CQ_LOG2SZ,
                  fq_log2sz:   int = DEFAULT_FQ_LOG2SZ):
        self.dut = dut
        self.log = logging.getLogger("cocotb.tb.env")
        self.clock_period_ns = clock_period_ns

        # AXI モデル (setup() で生成)
        self.prog_master = None
        self.tr_master = None
        self.comp_ram = None
        self.ds_ram = None
        self._ds_ram_size = ds_ram_size
        self._comp_ram_size = comp_ram_size

        # PPN レイアウト
        self.ddt_base_ppn = ddt_base_ppn
        self.s1_root_ppn  = s1_root_ppn
        self.s1_mid_ppn   = s1_mid_ppn
        self.s1_leaf_ppn  = s1_leaf_ppn
        self.g_root_ppn   = g_root_ppn
        self.g_mid_ppn    = g_mid_ppn
        self.g_leaf_ppn   = g_leaf_ppn
        self.pdt_root_ppn = pdt_root_ppn
        self.pdt_l1_ppn   = pdt_l1_ppn
        self.pdt_leaf_ppn = pdt_leaf_ppn
        self.msi_pt_root_ppn = 0x180   # MSI PT base (Flat). 他 PPN と衝突しない値。

        # Queue の設定 (setup() で実体化)
        self._cq_base_ppn = cq_base_ppn
        self._fq_base_ppn = fq_base_ppn
        self._cq_log2sz   = cq_log2sz
        self._fq_log2sz   = fq_log2sz
        self.fq = None
        self.cq = None

        # 既定の DVM 値 (各 dev_tr アクセスでこれを使う)
        self.default_stream_id   = 0
        self.default_ss_id_valid = 0
        self.default_substream_id = 0

    # ------------------------------------------------------------------
    # セットアップ
    # ------------------------------------------------------------------
    async def setup(self, *, enable_fq: bool = True, enable_cq: bool = False):
        """clock 起動 → reset → masters/rams 生成 → FQ enable まで一括。

        テストの最初に 1 度だけ呼ぶ。`enable_cq=True` を渡せば CQ も初期化される
        (IOTINVAL を使うテストで必要)。
        """
        # ---- clock ----
        cocotb.start_soon(Clock(self.dut.clk_i, self.clock_period_ns, unit="ns").start())

        # ---- AXI モデル生成 (reset 前に作っておくと reset 中の信号駆動も任せられる) ----
        self.prog_master = AxiMaster(AxiBus.from_prefix(self.dut, "prog"),
                                      self.dut.clk_i, self.dut.rst_ni,
                                      reset_active_level=False)
        self.tr_master   = AxiMaster(AxiBus.from_prefix(self.dut, "tr"),
                                      self.dut.clk_i, self.dut.rst_ni,
                                      reset_active_level=False)
        self.comp_ram    = AxiRam(AxiBus.from_prefix(self.dut, "comp"),
                                   self.dut.clk_i, self.dut.rst_ni,
                                   reset_active_level=False, size=self._comp_ram_size)
        self.ds_ram      = AxiRam(AxiBus.from_prefix(self.dut, "ds"),
                                   self.dut.clk_i, self.dut.rst_ni,
                                   reset_active_level=False, size=self._ds_ram_size)

        # ---- reset ----
        await reset_dut(self.dut)

        # ---- DVM 初期値 ----
        self._set_dvm_signals(self.default_stream_id,
                              self.default_ss_id_valid,
                              self.default_substream_id)

        # ---- Fault Queue ----
        if enable_fq:
            self.fq = FaultQueue(self.dut, self.prog_master, self.ds_ram,
                                  base_ppn=self._fq_base_ppn,
                                  log2sz=self._fq_log2sz)
            await self.fq.setup()

        # ---- Command Queue ----
        if enable_cq:
            self.cq = CommandQueue(self.dut, self.prog_master, self.ds_ram,
                                    base_ppn=self._cq_base_ppn,
                                    log2sz=self._cq_log2sz)
            await self.cq.setup()
        
        # ---- logging ----
        logging.getLogger("cocotb.axi").setLevel(logging.DEBUG)

        self.log.info("✓ env.setup() complete")

    async def enable_cq(self):
        """後から CQ を有効化したい時用 (Phase 4 の IOTLB 系で使う)。"""
        if self.cq is not None:
            return
        self.cq = CommandQueue(self.dut, self.prog_master, self.ds_ram,
                                base_ppn=self._cq_base_ppn,
                                log2sz=self._cq_log2sz)
        await self.cq.setup()

    # ------------------------------------------------------------------
    # DC 配置 + DDTP 切替 (1 セットで使うことが多いので統合)
    # ------------------------------------------------------------------
    async def install_dc_identity(self, *, did: int = 0):
        """両 stage Bare の identity DC を配置 + 1LVL DDT に切替。"""
        addr = install_dc_1lvl(self.ds_ram,
                                ddt_base_ppn=self.ddt_base_ppn,
                                did=did, dc_bytes=build_dc_identity())
        self.log.info(f"  DC[did={did}] identity @ ds_ram[0x{addr:x}]")
        await configure_ddt_mode(self.prog_master, self.dut,
                                  mode=DDTP_MODE_1LVL,
                                  ddt_base_ppn=self.ddt_base_ppn)

    async def install_dc_sv39_s1(self, *, did: int = 0,
                                   s1_root_ppn: int = None):
        """S=Sv39, G=Bare の DC を配置 + 1LVL DDT 化。"""
        if s1_root_ppn is None:
            s1_root_ppn = self.s1_root_ppn
        dc = build_dc_sv39_s1(s1_root_ppn)
        addr = install_dc_1lvl(self.ds_ram,
                                ddt_base_ppn=self.ddt_base_ppn,
                                did=did, dc_bytes=dc)
        self.log.info(f"  DC[did={did}] sv39_s1(root=0x{s1_root_ppn:x}) "
                       f"@ ds_ram[0x{addr:x}]")
        await configure_ddt_mode(self.prog_master, self.dut,
                                  mode=DDTP_MODE_1LVL,
                                  ddt_base_ppn=self.ddt_base_ppn)

    async def install_dc_sv39x4_s2(self, *, did: int = 0,
                                     g_root_ppn: int = None, gscid: int = 0):
        """S=Bare, G=Sv39x4 の DC を配置 + 1LVL DDT 化。"""
        if g_root_ppn is None:
            g_root_ppn = self.g_root_ppn
        dc = build_dc_sv39x4_s2(g_root_ppn, gscid=gscid)
        addr = install_dc_1lvl(self.ds_ram,
                                ddt_base_ppn=self.ddt_base_ppn,
                                did=did, dc_bytes=dc)
        self.log.info(f"  DC[did={did}] sv39x4_s2 @ ds_ram[0x{addr:x}]")
        await configure_ddt_mode(self.prog_master, self.dut,
                                  mode=DDTP_MODE_1LVL,
                                  ddt_base_ppn=self.ddt_base_ppn)

    async def install_dc_2stage(self, *, did: int = 0,
                                  s1_root_ppn: int = None,
                                  g_root_ppn: int = None,
                                  gscid: int = 0):
        """両 stage 有効の DC。"""
        if s1_root_ppn is None: s1_root_ppn = self.s1_root_ppn
        if g_root_ppn  is None: g_root_ppn  = self.g_root_ppn
        dc = build_dc_sv39_2stage(s1_root_ppn, g_root_ppn, gscid=gscid)
        addr = install_dc_1lvl(self.ds_ram,
                                ddt_base_ppn=self.ddt_base_ppn,
                                did=did, dc_bytes=dc)
        self.log.info(f"  DC[did={did}] 2stage @ ds_ram[0x{addr:x}]")
        await configure_ddt_mode(self.prog_master, self.dut,
                                  mode=DDTP_MODE_1LVL,
                                  ddt_base_ppn=self.ddt_base_ppn)

    # ------------------------------------------------------------------
    # DC 配置 (PDTV=1 / Process Context 版)
    # ------------------------------------------------------------------
    async def install_dc_sv39_s1_pc(self, *, did: int = 0,
                                      pdt_root_ppn: int = None,
                                      s1_root_ppn: int = None):
        """PDTV=1, PC.fsc=Sv39, G=Bare の DC を配置し PDT を書く。"""
        if pdt_root_ppn is None: pdt_root_ppn = self.pdt_root_ppn
        if s1_root_ppn  is None: s1_root_ppn  = self.s1_root_ppn
        dc = build_dc_sv39_s1_pc(pdt_root_ppn)
        addr = install_dc_1lvl(self.ds_ram,
                                ddt_base_ppn=self.ddt_base_ppn,
                                did=did, dc_bytes=dc)
        install_pdt_pd20(
            self.ds_ram,
            root_ppn=pdt_root_ppn, l1_ppn=self.pdt_l1_ppn,
            leaf_ppn=self.pdt_leaf_ppn,
            process_id=PC_PROCESS_ID_FIXED,
            pc_ta_bytes=pack_pc_ta(pscid=PC_PSCID_FIXED),
            pc_fsc_bytes=pack_pc_fsc(ATGP_MODE_SV39, s1_root_ppn),
        )
        self.log.info(f"  DC[did={did}] pc_sv39_s1 @ ds_ram[0x{addr:x}]")
        await configure_ddt_mode(self.prog_master, self.dut,
                                  mode=DDTP_MODE_1LVL,
                                  ddt_base_ppn=self.ddt_base_ppn)

    async def install_dc_sv39x4_s2_pc(self, *, did: int = 0,
                                        pdt_root_ppn: int = None,
                                        g_root_ppn: int = None, gscid: int = 0):
        """PDTV=1, PC.fsc=Bare, G=Sv39x4 の DC を配置し PDT を書く。"""
        if pdt_root_ppn is None: pdt_root_ppn = self.pdt_root_ppn
        if g_root_ppn   is None: g_root_ppn   = self.g_root_ppn
        dc = build_dc_sv39x4_s2_pc(pdt_root_ppn, g_root_ppn, gscid=gscid)
        addr = install_dc_1lvl(self.ds_ram,
                                ddt_base_ppn=self.ddt_base_ppn,
                                did=did, dc_bytes=dc)
        install_pdt_pd20(
            self.ds_ram,
            root_ppn=pdt_root_ppn, l1_ppn=self.pdt_l1_ppn,
            leaf_ppn=self.pdt_leaf_ppn,
            process_id=PC_PROCESS_ID_FIXED,
            pc_ta_bytes=pack_pc_ta(pscid=PC_PSCID_FIXED),
            pc_fsc_bytes=pack_pc_fsc(ATGP_MODE_BARE, 0),
        )
        self.log.info(f"  DC[did={did}] pc_sv39x4_s2 @ ds_ram[0x{addr:x}]")
        await configure_ddt_mode(self.prog_master, self.dut,
                                  mode=DDTP_MODE_1LVL,
                                  ddt_base_ppn=self.ddt_base_ppn)

    async def install_dc_2stage_pc(self, *, did: int = 0,
                                     pdt_root_ppn: int = None,
                                     s1_root_ppn: int = None,
                                     g_root_ppn: int = None, gscid: int = 0):
        """PDTV=1, PC.fsc=Sv39, G=Sv39x4 の DC を配置し PDT を書く。"""
        if pdt_root_ppn is None: pdt_root_ppn = self.pdt_root_ppn
        if s1_root_ppn  is None: s1_root_ppn  = self.s1_root_ppn
        if g_root_ppn   is None: g_root_ppn   = self.g_root_ppn
        dc = build_dc_sv39_2stage_pc(pdt_root_ppn, g_root_ppn, gscid=gscid)
        addr = install_dc_1lvl(self.ds_ram,
                                ddt_base_ppn=self.ddt_base_ppn,
                                did=did, dc_bytes=dc)
        install_pdt_pd20(
            self.ds_ram,
            root_ppn=pdt_root_ppn, l1_ppn=self.pdt_l1_ppn,
            leaf_ppn=self.pdt_leaf_ppn,
            process_id=PC_PROCESS_ID_FIXED,
            pc_ta_bytes=pack_pc_ta(pscid=PC_PSCID_FIXED),
            pc_fsc_bytes=pack_pc_fsc(ATGP_MODE_SV39, s1_root_ppn),
        )
        self.log.info(f"  DC[did={did}] pc_2stage @ ds_ram[0x{addr:x}]")
        await configure_ddt_mode(self.prog_master, self.dut,
                                  mode=DDTP_MODE_1LVL,
                                  ddt_base_ppn=self.ddt_base_ppn)

    async def install_dc_msi(self, *, did: int = 0,
                              s1_root_ppn: int = None,
                              g_root_ppn: int = None,
                              msi_pt_root_ppn: int = None,
                              gscid: int = 0):
        """S=Sv39, G=Sv39x4, msiptp=Flat の DC を配置 + 1LVL DDT 化。"""
        if s1_root_ppn      is None: s1_root_ppn      = self.s1_root_ppn
        if g_root_ppn       is None: g_root_ppn       = self.g_root_ppn
        if msi_pt_root_ppn  is None: msi_pt_root_ppn  = self.msi_pt_root_ppn

        dc = build_dc_msi(
            s1_root_ppn=s1_root_ppn,
            g_root_ppn=g_root_ppn,
            msi_pt_root_ppn=msi_pt_root_ppn,
            msi_addr_pattern=(0x0000300000000000 >> 12),
            msi_addr_mask=(0x000000FFFFFF000 >> 12),
            gscid=gscid,
        )
        addr = install_dc_1lvl(self.ds_ram,
                                ddt_base_ppn=self.ddt_base_ppn,
                                did=did, dc_bytes=dc)
        self.log.info(f"  DC[did={did}] msi(s1=0x{s1_root_ppn:x}, "
                       f"g=0x{g_root_ppn:x}, msipt=0x{msi_pt_root_ppn:x}) "
                       f"@ ds_ram[0x{addr:x}]")
        await configure_ddt_mode(self.prog_master, self.dut,
                                  mode=DDTP_MODE_1LVL,
                                  ddt_base_ppn=self.ddt_base_ppn)

    async def configure_bare(self):
        """ddtp.iommu_mode=Bare に切り替え (DC 不要)。"""
        await configure_ddt_mode(self.prog_master, self.dut,
                                  mode=DDTP_MODE_BARE,
                                  ddt_base_ppn=0)

    # ------------------------------------------------------------------
    # PT 配置 (S1 用は env のデフォルト PPN を使う)
    # ------------------------------------------------------------------
    def map_sv39_4k(self, iova: int, sp_ppn: int, *, perms=None):
        """S1 PT に 4K mapping を 1 個追加。"""
        from .const import PTE_LEAF_RWX_AD
        if perms is None:
            perms = PTE_LEAF_RWX_AD
        setup_sv39_4k(self.ds_ram,
                      root_ppn=self.s1_root_ppn,
                      mid_ppn=self.s1_mid_ppn,
                      leaf_ppn=self.s1_leaf_ppn,
                      iova=iova, sp_ppn=sp_ppn, perms=perms)

    def map_sv39_2m(self, iova: int, sp_ppn: int, *, perms=None):
        """S1 PT に 2M superpage mapping を追加。sp_ppn は 2M aligned。"""
        from .const import PTE_LEAF_RWX_AD
        if perms is None:
            perms = PTE_LEAF_RWX_AD
        setup_sv39_2m(self.ds_ram,
                      root_ppn=self.s1_root_ppn,
                      mid_ppn=self.s1_mid_ppn,
                      iova=iova, sp_ppn=sp_ppn, perms=perms)

    def map_sv39_1g(self, iova: int, sp_ppn: int, *, perms=None):
        """S1 PT に 1G superpage mapping を追加。sp_ppn は 1G aligned。"""
        from .const import PTE_LEAF_RWX_AD
        if perms is None:
            perms = PTE_LEAF_RWX_AD
        setup_sv39_1g(self.ds_ram,
                      root_ppn=self.s1_root_ppn,
                      iova=iova, sp_ppn=sp_ppn, perms=perms)

    def map_sv39_custom(self, iova: int, *, leaf_pte_bytes: bytes):
        """leaf PTE を完全にバイト指定したい時 (reserved bit 注入など)。"""
        setup_sv39_custom_leaf(self.ds_ram,
                                root_ppn=self.s1_root_ppn,
                                mid_ppn=self.s1_mid_ppn,
                                leaf_ppn=self.s1_leaf_ppn,
                                iova=iova, leaf_pte_bytes=leaf_pte_bytes)

    # ------------------------------------------------------------------
    # Transaction 発行 (DVM 設定込み)
    # ------------------------------------------------------------------
    def _set_dvm_signals(self, stream_id: int, ss_id_valid: int, substream_id: int):
        try:
            self.dut.tr_ar_stream_id.value   = stream_id
            self.dut.tr_ar_ss_id_valid.value = ss_id_valid
            self.dut.tr_ar_substream_id.value = substream_id
            self.dut.tr_aw_stream_id.value   = stream_id
            self.dut.tr_aw_ss_id_valid.value = ss_id_valid
            self.dut.tr_aw_substream_id.value = substream_id
        except AttributeError:
            pass

    async def dev_tr_read(self, iova: int, length: int = 8, *,
                           stream_id: int = None, substream_id: int = None,
                           ss_id_valid: int = None):
        """dev_tr 経由で read。AxiResp 付きの op を返す。"""
        sid = self.default_stream_id   if stream_id   is None else stream_id
        sub = self.default_substream_id if substream_id is None else substream_id
        ssv = self.default_ss_id_valid  if ss_id_valid  is None else ss_id_valid
        self._set_dvm_signals(sid, ssv, sub)
        return await self.tr_master.read(iova, length)

    async def dev_tr_write(self, iova: int, data: bytes, *,
                            stream_id: int = None, substream_id: int = None,
                            ss_id_valid: int = None):
        """dev_tr 経由で write。"""
        sid = self.default_stream_id   if stream_id   is None else stream_id
        sub = self.default_substream_id if substream_id is None else substream_id
        ssv = self.default_ss_id_valid  if ss_id_valid  is None else ss_id_valid
        self._set_dvm_signals(sid, ssv, sub)
        return await self.tr_master.write(iova, data)

    # ------------------------------------------------------------------
    # フォルト系 (Phase 2/3 で多用)
    # ------------------------------------------------------------------
    async def expect_fault_on_read(self, iova: int, *, length: int = 8,
                                     cause: int, **fields) -> "FaultRecord":
        """dev_tr.read を発行し、FQ に期待した cause のレコードが積まれるか確認。

        既定で iotval=iova を期待する (spec §4.2: 1-stage walk なら iotval=元の VA)。
        2-stage 時など別パターンを期待したいなら、明示的に kwargs で上書き:
            await env.expect_fault_on_read(iova, cause=..., iotval2=expected_gpa)
            await env.expect_fault_on_read(iova, cause=..., iotval=None)  # skip

        AXI 応答自体はモジュール実装次第 (0 を返す or SLVERR 等) なので
        ここでは値の assert はしない (必要ならテスト側で)。
        """
        async def _fire():
            try:
                await self.dev_tr_read(iova, length)
            except Exception as e:
                self.log.info(f"  (dev_tr_read raised: {e})")

        cocotb.start_soon(_fire())
        fields.setdefault("iotval", iova)              # spec 通りの既定
        return await expect_fault(self.fq, cause=cause, **fields)

    async def expect_fault_on_write(self, iova: int, data: bytes, *,
                                      cause: int, **fields):
        """write 版の expect_fault。"""
        async def _fire():
            try:
                await self.dev_tr_write(iova, data)
            except Exception as e:
                self.log.info(f"  (dev_tr_write raised: {e})")

        cocotb.start_soon(_fire())
        fields.setdefault("iotval", iova)
        return await expect_fault(self.fq, cause=cause, **fields)

    # ------------------------------------------------------------------
    # おまけ
    # ------------------------------------------------------------------
    async def settle(self, cycles: int = 20):
        """テスト終わりに数サイクル余分に進めて pending な動作を見届ける。"""
        for _ in range(cycles):
            await RisingEdge(self.dut.clk_i)