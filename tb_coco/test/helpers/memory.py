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
)


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