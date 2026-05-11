"""iommu_tb.memory — DC / PTE / Page Table を ds_ram に書き込むビルダ

★ ビット順の注意 ★
  iohgatp / fsc / msiptp は SATP 互換レイアウト:
      bits [63:60]  MODE
      bits [59:44]  reserved (iohgatp は GSCID)
      bits [43: 0]  PPN
  ddtp は別レイアウト (mode が下位 4 bit):
      bits [ 3: 0]  MODE
      bits [53:10]  PPN
  これを混同すると test_10 で見たような fsc.mode=0 化け bug が起きる。
"""

from .const import (
    DC_SIZE,
    DC_OFF_TC, DC_OFF_IOHGATP, DC_OFF_TA, DC_OFF_FSC,
    DC_OFF_MSIPTP, DC_OFF_MSI_ADDR_MASK, DC_OFF_MSI_ADDR_PATTERN,
    TC_V, TC_PDTV,
    ATGP_MODE_BARE, ATGP_MODE_SV39,
    HGATP_MODE_BARE, HGATP_MODE_SV39X4,
    PTE_NONLEAF, PTE_LEAF_RWX_AD,
    PC_PROCESS_ID_FIXED, PC_PSCID_FIXED,
)

# PDT モード (iommu_data_structures.h RVI_IOMMU_PD* 定義と一致)
PDT_MODE_PD20 = 3   # 3-level PDT, 20-bit process_id


# =============================================================================
# 個別フィールド packer
# =============================================================================
def pack_satp_like(mode: int, ppn: int) -> int:
    """SATP 互換レイアウト: MODE [63:60] / reserved [59:44] / PPN [43:0]。

    fsc / msiptp 用。iohgatp は別関数 pack_iohgatp() を使う。
    """
    return ((mode & 0xF) << 60) | (ppn & 0x0FFF_FFFF_FFFF)


def pack_iohgatp(mode: int, gscid: int, ppn: int) -> int:
    """iohgatp: MODE [63:60] / GSCID [59:44] / PPN [43:0]。"""
    return (((mode  & 0xF)    << 60)
          | ((gscid & 0xFFFF) << 44)
          | ( ppn   & 0x0FFF_FFFF_FFFF))


def pack_ddtp(mode: int, ppn: int, busy: bool = False) -> int:
    """ddtp: MODE [3:0] / BUSY [4] / reserved / PPN [53:10]。"""
    return ((mode & 0xF)
          | ((1 << 4) if busy else 0)
          | ((ppn & 0x0FFF_FFFF_FFFF) << 10))


def pack_msi_pte(valid: bool, msipte_ppn: int = 0) -> int:
    """フラット型 MSI PTE (basic, mode=3)。"""
    # bits [63:32] = reserved + flags (省略), [31:0] = PPN_LO 等
    # 必要になった時に拡張する
    return (1 if valid else 0) | (3 << 1) | ((msipte_ppn & 0x0FFF_FFFF_FFFF) << 10)


# =============================================================================
# Sv39 PTE
# =============================================================================
def make_pte(ppn: int, flags: int) -> bytes:
    """Sv39 PTE 1 個を 8 byte little-endian で返す。

    Args:
        ppn: 物理ページ番号 (44 bit)。次段 PT または leaf SPA。
        flags: V/R/W/X/U/G/A/D の OR (10 bit ぶん)。
    """
    pte = (flags & 0x3FF) | ((ppn & 0x0FFF_FFFF_FFFF) << 10)
    return pte.to_bytes(8, "little")


def vpn_indices_sv39(iova: int):
    """Sv39 IOVA を VPN[2:0] に分解。"""
    return ((iova >> 30) & 0x1FF,    # vpn2 (root, level 2)
            (iova >> 21) & 0x1FF,    # vpn1 (mid,  level 1)
            (iova >> 12) & 0x1FF)    # vpn0 (leaf, level 0)


def vpn_indices_sv39x4(gpa: int):
    """Sv39x4 GPA を VPN[2:0] に分解。

    Sv39x4 は VPN[2] が 11 bit (= 0x7FF) になる点が Sv39 と違う。
    """
    return ((gpa >> 30) & 0x7FF,     # vpn2 (Sv39x4 で 11 bit)
            (gpa >> 21) & 0x1FF,
            (gpa >> 12) & 0x1FF)


# =============================================================================
# Sv39 / S1 page table 配置
# =============================================================================
def setup_sv39_4k(ds_ram, *, root_ppn: int, mid_ppn: int, leaf_ppn: int,
                  iova: int, sp_ppn: int, perms: int = PTE_LEAF_RWX_AD):
    """3 段 Sv39 PT を ds_ram に構築 (4K leaf)。

    Args:
        ds_ram: cocotbext-axi の AxiRam インスタンス。
        root_ppn / mid_ppn / leaf_ppn: PT 用に確保する PPN。事前にゼロクリアする。
        iova: 翻訳元 IOVA。
        sp_ppn: 翻訳先 PPN (leaf PTE.PPN)。
        perms: leaf PTE フラグ (V/R/W/X/U/A/D の OR)。0 にすると V=0 でフォルト誘発。
    """
    vpn2, vpn1, vpn0 = vpn_indices_sv39(iova)

    # PT ページを 0 クリア
    for ppn in (root_ppn, mid_ppn, leaf_ppn):
        ds_ram.write(ppn << 12, bytes(4096))

    ds_ram.write((root_ppn << 12) + vpn2 * 8, make_pte(mid_ppn, PTE_NONLEAF))
    ds_ram.write((mid_ppn  << 12) + vpn1 * 8, make_pte(leaf_ppn, PTE_NONLEAF))
    ds_ram.write((leaf_ppn << 12) + vpn0 * 8, make_pte(sp_ppn, perms))


def setup_sv39_2m(ds_ram, *, root_ppn: int, mid_ppn: int,
                  iova: int, sp_ppn: int, perms: int = PTE_LEAF_RWX_AD):
    """2M superpage: level 1 が leaf。leaf PT 不要。

    sp_ppn は 2M aligned (下位 9 bit が 0) であること。
    """
    vpn2, vpn1, _ = vpn_indices_sv39(iova)

    for ppn in (root_ppn, mid_ppn):
        ds_ram.write(ppn << 12, bytes(4096))

    ds_ram.write((root_ppn << 12) + vpn2 * 8, make_pte(mid_ppn, PTE_NONLEAF))
    ds_ram.write((mid_ppn  << 12) + vpn1 * 8, make_pte(sp_ppn, perms))


def setup_sv39_1g(ds_ram, *, root_ppn: int,
                  iova: int, sp_ppn: int, perms: int = PTE_LEAF_RWX_AD):
    """1G superpage: level 2 (root) が leaf。mid/leaf PT 不要。

    sp_ppn は 1G aligned (下位 18 bit が 0) であること。
    """
    vpn2, _, _ = vpn_indices_sv39(iova)

    ds_ram.write(root_ppn << 12, bytes(4096))
    ds_ram.write((root_ppn << 12) + vpn2 * 8, make_pte(sp_ppn, perms))


def setup_sv39_custom_leaf(ds_ram, *, root_ppn: int, mid_ppn: int, leaf_ppn: int,
                            iova: int, leaf_pte_bytes: bytes):
    """leaf PTE を完全に手動で作って差し込みたい場合の low-level API。

    使用例 (reserved bit にゴミを入れて MISCONFIGURED を誘発):
        bad_pte = (PTE_LEAF_RWX_AD | (1 << 60)).to_bytes(8, "little")
        setup_sv39_custom_leaf(..., leaf_pte_bytes=bad_pte)
    """
    vpn2, vpn1, vpn0 = vpn_indices_sv39(iova)
    for ppn in (root_ppn, mid_ppn, leaf_ppn):
        ds_ram.write(ppn << 12, bytes(4096))
    ds_ram.write((root_ppn << 12) + vpn2 * 8, make_pte(mid_ppn,  PTE_NONLEAF))
    ds_ram.write((mid_ppn  << 12) + vpn1 * 8, make_pte(leaf_ppn, PTE_NONLEAF))
    assert len(leaf_pte_bytes) == 8
    ds_ram.write((leaf_ppn << 12) + vpn0 * 8, leaf_pte_bytes)


# =============================================================================
# Sv39x4 (G-stage / S2) page table 配置
#   Sv39x4 は VPN[2] が 11 bit (Sv39 の 9 bit と違う) で、root PT は 16 KiB
#   (= 4 KiB ページ × 4)。root_ppn は 4-page aligned (= PPN[1:0]=0) で確保する。
#   levels: 2=root (1G superpage 位置), 1=mid (2M), 0=leaf (4K)
# =============================================================================
def _sv39x4_root_addr(root_ppn: int, vpn2: int) -> int:
    """Sv39x4 の root PT entry のアドレスを返す。

    VPN[2] は 11 bit (0..2047) で、4 ページにまたがる。
    page_idx = vpn2 >> 9, in-page idx = vpn2 & 0x1FF。
    """
    page_idx = (vpn2 >> 9) & 0x3       # 0..3
    in_page  = (vpn2 & 0x1FF)
    return ((root_ppn + page_idx) << 12) + in_page * 8


def setup_sv39x4_identity_1g(ds_ram, *, root_ppn: int,
                              perms: int = None):
    """G-stage を 1G superpage 1 個で identity 化する (GPA[29:0] == SPA[29:0])。

    ⚠ RTL が 1G superpage 非対応の場合は使えない (= setup_sv39x4_identity_4k_for_ppns
       を使うこと)。ref と RTL の動作差分を見るための debug helper として残してある。
    """
    if perms is None:
        from .const import PTE_LEAF_RWX_AD
        perms = PTE_LEAF_RWX_AD
    for i in range(4):
        ds_ram.write((root_ppn + i) << 12, bytes(4096))
    ds_ram.write(_sv39x4_root_addr(root_ppn, 0), make_pte(0, perms))


def setup_sv39x4_with_override(ds_ram, *,
                                root_ppn: int, mid_ppn: int, leaf_ppn: int,
                                identity_ppns, override_gpa: int,
                                override_pte_bytes: bytes,
                                perms: int = None):
    """G-stage に identity 4K mappings + 1 個の override 用 PTE を置く。

    nested_full 検証で使う:
    - identity_ppns で指定した PPN は identity 4K mapping
    - override_gpa の slot だけ override_pte_bytes (= test S2 PTE) で書き換える

    制限: identity_ppns の全 PPN と override_gpa の VPN[2/1] が同じ 2M region 内に
    収まっていること。
    """
    if perms is None:
        from .const import PTE_LEAF_RWX_AD
        perms = PTE_LEAF_RWX_AD

    assert len(override_pte_bytes) == 8, "PTE は 8 byte 必須"
    unique_ppns = sorted(set(int(p) for p in identity_ppns))

    for i in range(4):
        ds_ram.write((root_ppn + i) << 12, bytes(4096))
    ds_ram.write(mid_ppn << 12, bytes(4096))
    ds_ram.write(leaf_ppn << 12, bytes(4096))

    # 基準は最初の identity PPN (= 全部同じ 2M region 前提)
    sample_gpa = unique_ppns[0] << 12 if unique_ppns else override_gpa
    vpn2_ref, vpn1_ref, _ = vpn_indices_sv39x4(sample_gpa)

    ds_ram.write(_sv39x4_root_addr(root_ppn, vpn2_ref),
                 make_pte(mid_ppn, PTE_NONLEAF))
    ds_ram.write((mid_ppn << 12) + vpn1_ref * 8,
                 make_pte(leaf_ppn, PTE_NONLEAF))

    # Identity entries (skip the override slot if it overlaps)
    override_v2, override_v1, override_vpn0 = vpn_indices_sv39x4(override_gpa)
    if override_v2 != vpn2_ref or override_v1 != vpn1_ref:
        raise ValueError(
            f"override_gpa 0x{override_gpa:x} not in same 2M region as identity range"
        )

    for ppn in unique_ppns:
        v2, v1, vpn0 = vpn_indices_sv39x4(ppn << 12)
        if v2 != vpn2_ref or v1 != vpn1_ref:
            raise ValueError(
                f"identity PPN 0x{ppn:x} not in same 2M region as range start"
            )
        if vpn0 == override_vpn0:
            continue  # override slot: handled below
        ds_ram.write((leaf_ppn << 12) + vpn0 * 8, make_pte(ppn, perms))

    # Override entry
    ds_ram.write((leaf_ppn << 12) + override_vpn0 * 8, override_pte_bytes)


def setup_sv39x4_identity_4k_for_ppns(ds_ram, *,
                                        root_ppn: int, mid_ppn: int, leaf_ppn: int,
                                        ppns, perms: int = None):
    """G-stage に specific PPNs の 4K identity mappings を配置する。

    各 PPN を「自身に対する 4K identity」として S2 leaf に書く。superpage を
    使わないため Phase 1 の「RTL が superpage 非対応」前提でも動く。

    nested 検証で env のレイアウトに合わせて必要な PT ページだけマップしたい
    時に使う典型用途:

        setup_sv39x4_identity_4k_for_ppns(
            ds_ram, root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn,
            leaf_ppn=env.g_leaf_ppn,
            ppns=[env.s1_root_ppn, env.s1_mid_ppn, env.s1_leaf_ppn,
                  s1_leaf_ppn_from_pte_raw])

    制限: 全 PPN が同じ 2M region (= same VPN[2] かつ same VPN[1]) 内に
    収まっている必要がある。違反したら ValueError を上げる (sanity)。
    """
    if perms is None:
        from .const import PTE_LEAF_RWX_AD
        perms = PTE_LEAF_RWX_AD

    unique_ppns = sorted(set(int(p) for p in ppns))
    if not unique_ppns:
        return

    # 触る PT ページを全部ゼロクリア
    for i in range(4):
        ds_ram.write((root_ppn + i) << 12, bytes(4096))
    ds_ram.write(mid_ppn << 12, bytes(4096))
    ds_ram.write(leaf_ppn << 12, bytes(4096))

    # 最初の PPN で root → mid → leaf のチェーンを作る
    sample_gpa = unique_ppns[0] << 12
    vpn2_ref, vpn1_ref, _ = vpn_indices_sv39x4(sample_gpa)

    ds_ram.write(_sv39x4_root_addr(root_ppn, vpn2_ref),
                 make_pte(mid_ppn, PTE_NONLEAF))
    ds_ram.write((mid_ppn << 12) + vpn1_ref * 8,
                 make_pte(leaf_ppn, PTE_NONLEAF))

    # 各 PPN に identity 4K leaf を書く
    for ppn in unique_ppns:
        v2, v1, vpn0 = vpn_indices_sv39x4(ppn << 12)
        if v2 != vpn2_ref or v1 != vpn1_ref:
            raise ValueError(
                f"setup_sv39x4_identity_4k_for_ppns: PPN 0x{ppn:x} is not "
                f"in the same 2M region as PPN 0x{unique_ppns[0]:x} "
                f"(VPN[2/1] mismatch). すべての PPN を同じ 2M region に "
                f"揃えるか、複数 region 対応版を実装してください。"
            )
        ds_ram.write((leaf_ppn << 12) + vpn0 * 8, make_pte(ppn, perms))


def write_sv39x4_pte_at_level_no_clear(ds_ram, *,
                                         root_ppn: int, mid_ppn: int, leaf_ppn: int,
                                         gpa: int, level: int, pte_bytes: bytes):
    """G-stage の既存 PT に PTE を 1 個書く (ゼロクリアなし)。

    setup_sv39x4_identity_4k_for_ppns などで PT チェーンを先に構築した後、
    特定スロットだけ override するために使う。PT 構造 (root/mid/leaf chain) は
    呼び出し前に正しく構築済みであること。
    """
    vpn2, vpn1, vpn0 = vpn_indices_sv39x4(gpa)
    assert len(pte_bytes) == 8, "PTE は 8 byte 必須"
    assert level in (0, 1, 2), f"level は 0/1/2 (got {level})"
    if level == 2:
        ds_ram.write(_sv39x4_root_addr(root_ppn, vpn2), pte_bytes)
    elif level == 1:
        ds_ram.write((mid_ppn << 12) + vpn1 * 8, pte_bytes)
    else:
        ds_ram.write((leaf_ppn << 12) + vpn0 * 8, pte_bytes)


def setup_sv39x4_custom_at_level(ds_ram, *,
                                  root_ppn: int, mid_ppn: int, leaf_ppn: int,
                                  gpa: int, level: int, pte_bytes: bytes):
    """G-stage に custom PTE を任意 level で配置する (s2_only テスト用)。

    Sv39 版の setup_sv39_custom_at_level の Sv39x4 版。
    level=0: 4K leaf 位置 (LVL0[vpn0])
    level=1: 中間 (LVL1[vpn1])
    level=2: ルート (LVL2[vpn2])
    """
    vpn2, vpn1, vpn0 = vpn_indices_sv39x4(gpa)
    assert len(pte_bytes) == 8, "PTE は 8 byte 必須"
    assert level in (0, 1, 2), f"level は 0/1/2 (got {level})"

    # root 4 ページゼロクリア
    for i in range(4):
        ds_ram.write((root_ppn + i) << 12, bytes(4096))
    if level <= 1:
        ds_ram.write(mid_ppn << 12, bytes(4096))
    if level == 0:
        ds_ram.write(leaf_ppn << 12, bytes(4096))

    if level == 2:
        # root[vpn2] に直接 PTE
        ds_ram.write(_sv39x4_root_addr(root_ppn, vpn2), pte_bytes)
    elif level == 1:
        # root[vpn2] → non-leaf to mid; mid[vpn1] に PTE
        ds_ram.write(_sv39x4_root_addr(root_ppn, vpn2),
                     make_pte(mid_ppn, PTE_NONLEAF))
        ds_ram.write((mid_ppn << 12) + vpn1 * 8, pte_bytes)
    else:  # level == 0
        # root[vpn2] → mid → leaf に PTE
        ds_ram.write(_sv39x4_root_addr(root_ppn, vpn2),
                     make_pte(mid_ppn, PTE_NONLEAF))
        ds_ram.write((mid_ppn  << 12) + vpn1 * 8, make_pte(leaf_ppn, PTE_NONLEAF))
        ds_ram.write((leaf_ppn << 12) + vpn0 * 8, pte_bytes)


# =============================================================================
# Sv39 1-stage (S1) PT 配置
# =============================================================================
def setup_sv39_custom_at_level(ds_ram, *,
                                root_ppn: int, mid_ppn: int, leaf_ppn: int,
                                iova: int, level: int, pte_bytes: bytes):
    """指定 level に custom PTE を配置する replay 専用 helper.

    gen_vectors の `add_s_stage_pte(..., add_level=tc->level, ...)` と等価。

    Args:
        level=0: 4K leaf 位置 (LVL0[vpn0]) に PTE を配置 — 通常の leaf。
        level=1: 中間レベル (LVL1[vpn1]) に PTE を配置 — 2M superpage 位置。
                  PTE の R/X が立っていれば 2M superpage として解釈される。
                  R=X=0 なら walk が LVL0 に降りようとする → LVL0 PT は未配置 (= 全 0)
                  なので V=0 PTE を読んで fault が起きる。
        level=2: ルート (LVL2[vpn2]) に PTE を配置 — 1G superpage 位置。

        pte_bytes: 8 byte の little-endian PTE 値。gen_vectors の `pte_raw` を
                   そのまま渡す想定。
    """
    vpn2, vpn1, vpn0 = vpn_indices_sv39(iova)
    assert len(pte_bytes) == 8, "PTE は 8 byte 必須"
    assert level in (0, 1, 2), f"level は 0/1/2 のいずれか (got {level})"

    # 触る PT ページは必ずゼロクリア (ホスト側のゴミ残りを排除)
    ds_ram.write(root_ppn << 12, bytes(4096))
    if level <= 1:
        ds_ram.write(mid_ppn << 12, bytes(4096))
    if level == 0:
        ds_ram.write(leaf_ppn << 12, bytes(4096))

    if level == 2:
        # LVL2 root に直接 PTE
        ds_ram.write((root_ppn << 12) + vpn2 * 8, pte_bytes)
    elif level == 1:
        # LVL2 → non-leaf → LVL1 に PTE
        ds_ram.write((root_ppn << 12) + vpn2 * 8, make_pte(mid_ppn, PTE_NONLEAF))
        ds_ram.write((mid_ppn  << 12) + vpn1 * 8, pte_bytes)
    else:  # level == 0
        # LVL2 → non-leaf → LVL1 → non-leaf → LVL0 に PTE
        ds_ram.write((root_ppn << 12) + vpn2 * 8, make_pte(mid_ppn,  PTE_NONLEAF))
        ds_ram.write((mid_ppn  << 12) + vpn1 * 8, make_pte(leaf_ppn, PTE_NONLEAF))
        ds_ram.write((leaf_ppn << 12) + vpn0 * 8, pte_bytes)


# =============================================================================
# Device Context (DC) — Extended format (64 byte)
# =============================================================================
def build_dc(*,
    tc_bits: int = TC_V,
    iohgatp_mode: int = 0, iohgatp_gscid: int = 0, iohgatp_ppn: int = 0,
    pscid: int = 0,
    fsc_mode: int = 0, fsc_ppn: int = 0,
    msiptp_mode: int = 0, msiptp_ppn: int = 0,
    msi_addr_mask: int = 0,
    msi_addr_pattern: int = 0,
) -> bytes:
    """64-byte DC (Extended format) を生成する。

    各 SATP-like field は **MODE が上位 4 bit** に乗る。
    iohgatp は GSCID が中段 [59:44] に挟まる。
    """
    dc = bytearray(DC_SIZE)

    tc      = tc_bits & 0xFFFF_FFFF_FFFF_FFFF
    iohgatp = pack_iohgatp(iohgatp_mode, iohgatp_gscid, iohgatp_ppn)
    ta      = (pscid & 0xFFFFF) << 12       # ta: PSCID [31:12]
    fsc     = pack_satp_like(fsc_mode, fsc_ppn)
    msiptp  = pack_satp_like(msiptp_mode, msiptp_ppn)

    dc[DC_OFF_TC     :DC_OFF_TC     +8] = tc.to_bytes(8, "little")
    dc[DC_OFF_IOHGATP:DC_OFF_IOHGATP+8] = iohgatp.to_bytes(8, "little")
    dc[DC_OFF_TA     :DC_OFF_TA     +8] = ta.to_bytes(8, "little")
    dc[DC_OFF_FSC    :DC_OFF_FSC    +8] = fsc.to_bytes(8, "little")
    dc[DC_OFF_MSIPTP :DC_OFF_MSIPTP +8] = msiptp.to_bytes(8, "little")
    dc[DC_OFF_MSI_ADDR_MASK   :DC_OFF_MSI_ADDR_MASK   +8] = msi_addr_mask.to_bytes(8, "little")
    dc[DC_OFF_MSI_ADDR_PATTERN:DC_OFF_MSI_ADDR_PATTERN+8] = msi_addr_pattern.to_bytes(8, "little")
    # offset 56 (reserved DW) は CDW が読まないので 0 のまま

    return bytes(dc)


# =============================================================================
# DC プリセット (よく使う組み合わせ)
# =============================================================================
def build_dc_identity() -> bytes:
    """両 stage Bare = identity 翻訳。tc.V=1 だけ。"""
    return build_dc(tc_bits=TC_V)


def build_dc_sv39_s1(s1_root_ppn: int) -> bytes:
    """1-stage Sv39 (S-stage), G-stage Bare, no PC。

    PTW が S1 walk を実行するメインの DC。
    """
    return build_dc(
        tc_bits      = TC_V,
        iohgatp_mode = HGATP_MODE_BARE,
        fsc_mode     = ATGP_MODE_SV39,
        fsc_ppn      = s1_root_ppn,
    )


def build_dc_sv39x4_s2(g_root_ppn: int, gscid: int = 0) -> bytes:
    """S-stage Bare, G-stage Sv39x4 (only-Stage-2 walk)。"""
    return build_dc(
        tc_bits       = TC_V,
        iohgatp_mode  = HGATP_MODE_SV39X4,
        iohgatp_gscid = gscid,
        iohgatp_ppn   = g_root_ppn,
        fsc_mode      = ATGP_MODE_BARE,
    )


def build_dc_sv39_2stage(s1_root_ppn: int, g_root_ppn: int, gscid: int = 0) -> bytes:
    """両 stage 有効: S=Sv39, G=Sv39x4。最複雑のケース。"""
    return build_dc(
        tc_bits       = TC_V,
        iohgatp_mode  = HGATP_MODE_SV39X4,
        iohgatp_gscid = gscid,
        iohgatp_ppn   = g_root_ppn,
        fsc_mode      = ATGP_MODE_SV39,
        fsc_ppn       = s1_root_ppn,
    )


# =============================================================================
# DDT に DC を配置する低レベル helper
# =============================================================================
def install_dc_1lvl(ds_ram, *, ddt_base_ppn: int, did: int, dc_bytes: bytes):
    """1LVL DDT に DC を 1 個書く。

    1LVL では DDT は flat array、entry size = 64 byte (Extended) なので
    アドレス = (ddt_base << 12) + (did[5:0] * 64)。
    """
    assert len(dc_bytes) == DC_SIZE, f"DC must be {DC_SIZE} byte"
    addr = (ddt_base_ppn << 12) + (did & 0x3F) * 64
    ds_ram.write(addr, dc_bytes)
    return addr


# =============================================================================
# PDTV=1 用: Process Context (PC) / PDT ビルダ
# =============================================================================
def pack_pdte(ppn: int) -> bytes:
    """PDT non-leaf エントリ (8 byte): V=1, PPN=[53:10]。"""
    raw = 1 | ((ppn & 0x0FFF_FFFF_FFFF) << 10)
    return raw.to_bytes(8, "little")


def pack_pc_ta(*, v: int = 1, ens: int = 1, sum_: int = 1,
               pscid: int = PC_PSCID_FIXED) -> bytes:
    """process_context_t.ta (8 byte little-endian).

    Layout (spec §3.1.3.2):
      bit 0       = V
      bit 1       = ENS
      bit 2       = SUM
      bits [31:12] = PSCID (20 bit)
      bits [63:32] = reserved
    """
    raw = (v & 1) | ((ens & 1) << 1) | ((sum_ & 1) << 2) | ((pscid & 0xFFFFF) << 12)
    return raw.to_bytes(8, "little")


def pack_pc_fsc(mode: int, ppn: int) -> bytes:
    """process_context_t.fsc (8 byte little-endian): SATP 互換レイアウト。"""
    return pack_satp_like(mode, ppn).to_bytes(8, "little")


def install_pdt_pd20(ds_ram, *,
                     root_ppn: int, l1_ppn: int, leaf_ppn: int,
                     process_id: int,
                     pc_ta_bytes: bytes,
                     pc_fsc_bytes: bytes):
    """PD20 (3-level PDT) に 1 個の PC エントリを書く。

    PDI[2] = process_id[19:17] (3 bit, root index, 8 entries)
    PDI[1] = process_id[16:8]  (9 bit, L1 index, 512 entries)
    PDI[0] = process_id[7:0]   (8 bit, leaf index, 256 × 16 byte)

    root_ppn: PDT root (1 page, 8 entries × 8 byte = 64 byte)
    l1_ppn:   PDT L1   (1 page, 512 entries × 8 byte = 4 KiB)
    leaf_ppn: PDT leaf (1 page, 256 entries × 16 byte = 4 KiB)
    """
    assert len(pc_ta_bytes)  == 8
    assert len(pc_fsc_bytes) == 8

    pdi2 = (process_id >> 17) & 0x7
    pdi1 = (process_id >>  8) & 0x1FF
    pdi0 = (process_id >>  0) & 0xFF

    # ゼロクリア
    ds_ram.write(root_ppn << 12, bytes(4096))
    ds_ram.write(l1_ppn   << 12, bytes(4096))
    ds_ram.write(leaf_ppn << 12, bytes(4096))

    # root[PDI[2]] → L1
    ds_ram.write((root_ppn << 12) + pdi2 * 8, pack_pdte(l1_ppn))
    # L1[PDI[1]] → leaf
    ds_ram.write((l1_ppn << 12) + pdi1 * 8, pack_pdte(leaf_ppn))
    # leaf[PDI[0]] = PC (16 byte: ta + fsc)
    pc_addr = (leaf_ppn << 12) + pdi0 * 16
    ds_ram.write(pc_addr,     pc_ta_bytes)
    ds_ram.write(pc_addr + 8, pc_fsc_bytes)


# =============================================================================
# PC 用 DC プリセット (PDTV=1, DC.fsc = pdtp)
# =============================================================================
def build_dc_sv39_s1_pc(pdt_root_ppn: int) -> bytes:
    """PDTV=1, PC.fsc=Sv39, G=Bare。pdtp が DC.fsc に入る。"""
    return build_dc(
        tc_bits      = TC_V | TC_PDTV,
        iohgatp_mode = HGATP_MODE_BARE,
        fsc_mode     = PDT_MODE_PD20,
        fsc_ppn      = pdt_root_ppn,
    )


def build_dc_sv39x4_s2_pc(pdt_root_ppn: int, g_root_ppn: int,
                            gscid: int = 0) -> bytes:
    """PDTV=1, PC.fsc=Bare, G=Sv39x4。"""
    return build_dc(
        tc_bits       = TC_V | TC_PDTV,
        iohgatp_mode  = HGATP_MODE_SV39X4,
        iohgatp_gscid = gscid,
        iohgatp_ppn   = g_root_ppn,
        fsc_mode      = PDT_MODE_PD20,
        fsc_ppn       = pdt_root_ppn,
    )


def build_dc_sv39_2stage_pc(pdt_root_ppn: int, g_root_ppn: int,
                              gscid: int = 0) -> bytes:
    """PDTV=1, PC.fsc=Sv39, G=Sv39x4。"""
    return build_dc(
        tc_bits       = TC_V | TC_PDTV,
        iohgatp_mode  = HGATP_MODE_SV39X4,
        iohgatp_gscid = gscid,
        iohgatp_ppn   = g_root_ppn,
        fsc_mode      = PDT_MODE_PD20,
        fsc_ppn       = pdt_root_ppn,
    )


# =============================================================================
# MSI PT helpers (riscv-iommu spec §3.1.3 + libiommu/iommu_msi_translation.c)
#
# MSI PTE format (16B), spec compliant:
#   bit  0      : V       (Valid)
#   bits 2:1    : M       (00=reserved, 01=MRIF, 10=reserved, 11=Basic)
#   bits 9:3    : reserved (translate_rw.reserved)
#   bits 53:10  : PPN     (44 bits)
#   bits 62:54  : reserved
#   bit  63     : C       (Custom; reference では C=1 で cause=263)
# =============================================================================
import struct as _struct


def pack_msi_pte_raw(*, v: int, m: int, ppn: int,
                      c: int = 0, rsvd_3_9: int = 0) -> int:
    """MSI PTE 下位 8 byte を 64bit int で返す。"""
    raw = 0
    raw |= (v & 1) << 0
    raw |= (m & 3) << 1
    raw |= (rsvd_3_9 & 0x7F) << 3
    raw |= (ppn & ((1 << 44) - 1)) << 10
    raw |= (c & 1) << 63
    return raw


def setup_msi_pt_flat(ds_ram, *, msi_pt_root_ppn: int,
                       index: int,
                       pte_low_raw: int, pte_high_raw: int = 0):
    """MSI PT (Flat) の指定 index に MSI PTE 16 byte を書き込む。"""
    base = msi_pt_root_ppn << 12
    addr = base + index * 16
    ds_ram.write(addr,     pte_low_raw.to_bytes(8, "little"))
    ds_ram.write(addr + 8, pte_high_raw.to_bytes(8, "little"))


def build_dc_msi(*, s1_root_ppn: int, g_root_ppn: int,
                  msi_pt_root_ppn: int,
                  msi_addr_pattern: int, msi_addr_mask: int,
                  gscid: int = 0) -> bytes:
    """msiptp + msi_addr_pattern + msi_addr_mask を含む 64-byte DC を構築。"""
    return build_dc(
        tc_bits           = TC_V,
        iohgatp_mode      = HGATP_MODE_SV39X4,
        iohgatp_gscid     = gscid,
        iohgatp_ppn       = g_root_ppn,
        fsc_mode          = ATGP_MODE_SV39,
        fsc_ppn           = s1_root_ppn,
        msiptp_mode       = 1,   # MSIPTP_Flat = 1
        msiptp_ppn        = msi_pt_root_ppn,
        msi_addr_mask     = msi_addr_mask    & ((1 << 52) - 1),
        msi_addr_pattern  = msi_addr_pattern & ((1 << 52) - 1),
    )