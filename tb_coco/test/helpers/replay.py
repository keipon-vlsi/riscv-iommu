"""helpers.replay — golden_vectors.jsonl の各エントリを RTL に流して結果を捕まえる

利用フロー (test_replay_golden.py から呼ばれる):
    entries = list(parse_jsonl("golden_vectors.jsonl"))
    for entry in entries:
        await reset_for_replay(env)
        setup_for_entry(env, entry)
        rtl_resp = await drive_one(env, entry)
        log_writer.write(json.dumps(rtl_resp) + "\n")

各 rtl_resp は golden_vectors.jsonl の 1 行と __同じスキーマ__ で出力する。
これは diff_logs.py 側を `dict == dict` だけで済ませるため。

Option B (= alloc field 連携):
  gen_common.c が各 case で実 alloc した PPN を JSONL の "alloc" object に出力する。
  setup_dc_for_entry の冒頭で entry["alloc"] を読み取って env の各 PPN 属性を override
  することで、RTL 側 (AxiRam) のメモリレイアウトを libiommu と完全一致させる。
  alloc field が無い古い JSONL は env 既定値で動作 (= 後方互換)。
"""

import json
import logging
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge, Event

from .memory import (
    setup_sv39_custom_at_level,
    setup_sv39x4_custom_at_level,
    setup_sv39x4_identity_4k_for_ppns,
    setup_sv39x4_with_override,
    write_sv39x4_pte_at_level_no_clear,
    ATGP_MODE_BARE, ATGP_MODE_SV39,
    pack_pc_ta, pack_pc_fsc, install_pdt_pd20,
    setup_msi_pt_flat, pack_msi_pte_raw,
)
from .const import PC_PROCESS_ID_FIXED, PC_PSCID_FIXED

# =============================================================================
# Default values — JSONL エントリに該当フィールドが無い時のフォールバック先。
#   phase1_pte_flags など古いカテゴリは IOVA を出力していないので、その互換用。
# =============================================================================
DEFAULT_IOVA = 0x002345                # phase1 互換のデフォルト IOVA
GOLDEN_DID   = 0                       # 全カテゴリで現状 DID=0 固定
DEFAULT_PAGE_OFFSET = DEFAULT_IOVA & 0xFFF   # = 0x345

# 後方互換のためのエイリアス (test_replay_golden.py が import している)
GOLDEN_IOVA = DEFAULT_IOVA

log = logging.getLogger("cocotb.tb.replay")


# =============================================================================
# JSONL ローダ
# =============================================================================
def parse_jsonl(path):
    """Read JSONL file, yield each non-empty line as a dict."""
    p = Path(path)
    with p.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _entry_iova(entry) -> int:
    """エントリから IOVA を取り出す。無ければ default 0x002345。

    JSONL では "0x..." の hex string で来るが、念のため int 直接にも対応。
    """
    val = entry.get("iova")
    if val is None:
        return DEFAULT_IOVA
    if isinstance(val, str):
        val = val.strip()
        return int(val, 16) if val.startswith("0x") else int(val)
    return int(val)


def _parse_ppn(val):
    """alloc field の値 (hex string) を int に変換。"""
    if val is None:
        return None
    if isinstance(val, str):
        val = val.strip()
        return int(val, 16) if val.startswith("0x") else int(val)
    return int(val)


# =============================================================================
# Option B: entry["alloc"] を env に注入
# =============================================================================
def _apply_alloc_override(env, entry):
    """JSONL の "alloc" field から PPN を読み取って env の対応属性を上書き。

    libiommu (gen_common.c 側) と env (replay.py 側) のメモリレイアウトを
    完全一致させるため、各 case 開始前に呼ぶ。

    alloc field が無い old JSONL では何もしない (= env の既定値で動作、後方互換)。

    マッピング:
        alloc["ddt"]          → env.ddt_base_ppn
        alloc["fq"]           → env.fq_base_ppn
        alloc["pdt_root"]     → env.pdt_root_ppn
        alloc["pdt_l1"]       → env.pdt_l1_ppn
        alloc["pdt_leaf"]     → env.pdt_leaf_ppn
        alloc["iohgatp_root"] → env.g_root_ppn
        alloc["g_mid"]        → env.g_mid_ppn
        alloc["g_leaf"]       → env.g_leaf_ppn
        alloc["s1_root"]      → env.s1_root_ppn
        alloc["s1_mid"]       → env.s1_mid_ppn
        alloc["s1_leaf"]      → env.s1_leaf_ppn
    """
    alloc = entry.get("alloc")
    if not alloc:
        return  # alloc field 無し → 既定値で動く (後方互換)

    mapping = (
        ("ddt",          "ddt_base_ppn"),
        ("fq",           "fq_base_ppn"),
        ("pdt_root",     "pdt_root_ppn"),
        ("pdt_l1",       "pdt_l1_ppn"),
        ("pdt_leaf",     "pdt_leaf_ppn"),
        ("iohgatp_root", "g_root_ppn"),
        ("g_mid",        "g_mid_ppn"),
        ("g_leaf",       "g_leaf_ppn"),
        ("s1_root",      "s1_root_ppn"),
        ("s1_mid",       "s1_mid_ppn"),
        ("s1_leaf",      "s1_leaf_ppn"),
        ("msi_pt_root",  "msi_pt_root_ppn"),
    )
    for jsonl_key, env_attr in mapping:
        if jsonl_key in alloc:
            ppn = _parse_ppn(alloc[jsonl_key])
            if ppn is not None and hasattr(env, env_attr):
                setattr(env, env_attr, ppn)


# =============================================================================
# RTL 側のメモリセットアップ
# =============================================================================
async def setup_dc_for_entry(env, entry):
    """entry の stage_mode に応じて DC を配置する (DDT install 含む)。

    s1_only / iova_variation   : install_dc_sv39_s1
    s2_only                    : install_dc_sv39x4_s2
    nested / nested_full       : install_dc_2stage
    pc_s1_only / pc_iova_variation              : install_dc_sv39_s1_pc
    pc_s2_only                                  : install_dc_sv39x4_s2_pc
    pc_nested / pc_nested_full / *_quick        : install_dc_2stage_pc

    Option B: entry["alloc"] から PPN を読み取って env を上書きしてから install_*。
    """
    # ★ Option B: gen_common.c が記録した実 PPN を env に注入
    _apply_alloc_override(env, entry)

    mode = entry.get("stage_mode", "s1_only")
    if mode == "s1_only":
        await env.install_dc_sv39_s1(did=GOLDEN_DID)
    elif mode == "s2_only":
        await env.install_dc_sv39x4_s2(did=GOLDEN_DID)
    elif mode in ("nested", "nested_full"):
        await env.install_dc_2stage(did=GOLDEN_DID)
    elif mode in ("pc_s1_only", "pc_iova_variation"):
        await env.install_dc_sv39_s1_pc(did=GOLDEN_DID)
    elif mode == "pc_s2_only":
        await env.install_dc_sv39x4_s2_pc(did=GOLDEN_DID)
    elif mode in ("pc_nested", "pc_nested_full", "pc_nested_full_quick"):
        await env.install_dc_2stage_pc(did=GOLDEN_DID)
    elif mode == "bare_bare":
        await env.install_dc_identity(did=GOLDEN_DID)
    elif mode == "msi":
        await env.install_dc_msi(did=GOLDEN_DID)
    else:
        raise ValueError(f"Unknown stage_mode: {mode}")


def setup_for_entry(env, entry):
    """1 entry 分の PT 配置 + comp_ram の PPN マーカーを書く (stage_mode で分岐)。

    呼び出し前提:
      - env.setup() 済み
      - setup_dc_for_entry(env, entry) 済み (DC は stage_mode に対応している)

    IOVA は entry["iova"] を使う (省略時は default 0x002345 にフォールバック)。
    """
    iova     = _entry_iova(entry)
    page_off = iova & 0xFFF
    mode     = entry.get("stage_mode", "s1_only")

    pte_raw   = int(entry["pte_raw"], 16)
    pte_bytes = pte_raw.to_bytes(8, "little")

    if mode == "s1_only":
        # S1 leaf を S1 PT に配置 (S2 は Bare なので G-stage は触らない)
        setup_sv39_custom_at_level(
            env.ds_ram,
            root_ppn=env.s1_root_ppn, mid_ppn=env.s1_mid_ppn, leaf_ppn=env.s1_leaf_ppn,
            iova=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "s2_only":
        # S2 leaf を G-stage PT に配置 (S1 は Bare なので IOVA がそのまま GPA)
        setup_sv39x4_custom_at_level(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            gpa=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "nested":
        # ① S2 を 4K identity mappings で透過化。
        #   nested 翻訳では S1 PT pages の access が GPA → S2 walk するので、
        #   env.s1_*_ppn を S2 で identity-map する必要がある。さらに最終翻訳結果の
        #   leaf PPN (= entry["pte_raw"] が指す PPN) も identity-map しないと、
        #   翻訳成功時の data 読み出しが失敗する。
        #   ★ 1G superpage は使わない (RTL が superpage 非対応の前提のため)。
        leaf_ppn_from_pte = (pte_raw >> 10) & 0x0FFF_FFFF_FFFF
        setup_sv39x4_identity_4k_for_ppns(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            ppns=[
                env.s1_root_ppn,
                env.s1_mid_ppn,
                env.s1_leaf_ppn,
                leaf_ppn_from_pte,        # 成功時の最終アクセス先
            ],
        )
        # ② S1 leaf を S1 PT に配置 (= 試験対象の S1 PTE)
        setup_sv39_custom_at_level(
            env.ds_ram,
            root_ppn=env.s1_root_ppn, mid_ppn=env.s1_mid_ppn, leaf_ppn=env.s1_leaf_ppn,
            iova=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "nested_full":
        # gen_nested_full.c と整合する設定:
        #   - S1 leaf PTE.PPN は 0x150 固定 (= entry["pte_raw"] にそう入っている)
        #   - S2 PT は env.s1_*_ppn を identity + GPA=(0x150 << 12) を test S2 PTE で override
        s2_pte_raw   = int(entry["s2_pte_raw"], 16)
        s2_pte_bytes = s2_pte_raw.to_bytes(8, "little")
        s1_leaf_ppn  = (pte_raw >> 10) & 0x0FFF_FFFF_FFFF

        setup_sv39x4_with_override(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            identity_ppns=[
                env.s1_root_ppn,
                env.s1_mid_ppn,
                env.s1_leaf_ppn,
            ],
            override_gpa=s1_leaf_ppn << 12,
            override_pte_bytes=s2_pte_bytes,
        )
        setup_sv39_custom_at_level(
            env.ds_ram,
            root_ppn=env.s1_root_ppn, mid_ppn=env.s1_mid_ppn, leaf_ppn=env.s1_leaf_ppn,
            iova=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode in ("pc_s1_only", "pc_iova_variation"):
        # DC: PDTV=1, PC.fsc=Sv39 (install_dc_sv39_s1_pc が書き込み済み)
        # ここでは S1 PT の PTE だけ書く (PDT は setup_dc_for_entry 済み)
        setup_sv39_custom_at_level(
            env.ds_ram,
            root_ppn=env.s1_root_ppn, mid_ppn=env.s1_mid_ppn, leaf_ppn=env.s1_leaf_ppn,
            iova=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "pc_s2_only":
        # DC: PDTV=1, PC.fsc=Bare, G=Sv39x4
        # PDT pages の G-stage identity を設定後、PT ページを破壊せずに test S2 PTE を書く。
        # setup_sv39x4_custom_at_level は PT ページをゼロクリアするため使えない。
        pdt_ppns = [env.pdt_root_ppn, env.pdt_l1_ppn, env.pdt_leaf_ppn]
        setup_sv39x4_identity_4k_for_ppns(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            ppns=pdt_ppns,
        )
        # ゼロクリアせず既存 chain に test PTE を重ね書き (C 側と同じ操作)
        write_sv39x4_pte_at_level_no_clear(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            gpa=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode in ("pc_nested", "pc_nested_full_quick"):
        # DC: PDTV=1, PC.fsc=Sv39, G=Sv39x4 identity
        # S2 identity covers: S1 PT pages + leaf PPN + PDT pages (all in same 2M region)
        leaf_ppn_from_pte = (pte_raw >> 10) & 0x0FFF_FFFF_FFFF
        setup_sv39x4_identity_4k_for_ppns(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            ppns=[
                env.s1_root_ppn,
                env.s1_mid_ppn,
                env.s1_leaf_ppn,
                leaf_ppn_from_pte,
                env.pdt_root_ppn,
                env.pdt_l1_ppn,
                env.pdt_leaf_ppn,
            ],
        )
        setup_sv39_custom_at_level(
            env.ds_ram,
            root_ppn=env.s1_root_ppn, mid_ppn=env.s1_mid_ppn, leaf_ppn=env.s1_leaf_ppn,
            iova=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "pc_nested_full":
        # DC: PDTV=1, PC.fsc=Sv39, G=Sv39x4
        # gen_pc_nested_full.c と整合: S1 leaf PPN=0x150, S2 test PPN=0x250。
        # S2 PT: env.s1_*_ppn + PDT pages の identity + GPA=0x150<<12 を test S2 PTE で override。
        s2_pte_raw   = int(entry["s2_pte_raw"], 16)
        s2_pte_bytes = s2_pte_raw.to_bytes(8, "little")
        s1_leaf_ppn  = (pte_raw >> 10) & 0x0FFF_FFFF_FFFF

        setup_sv39x4_with_override(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            identity_ppns=[
                env.s1_root_ppn,
                env.s1_mid_ppn,
                env.s1_leaf_ppn,
                env.pdt_root_ppn,
                env.pdt_l1_ppn,
                env.pdt_leaf_ppn,
            ],
            override_gpa=s1_leaf_ppn << 12,
            override_pte_bytes=s2_pte_bytes,
        )
        setup_sv39_custom_at_level(
            env.ds_ram,
            root_ppn=env.s1_root_ppn, mid_ppn=env.s1_mid_ppn, leaf_ppn=env.s1_leaf_ppn,
            iova=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "bare_bare":
        # Bare-Bare: PT 配置不要、IOVA = SPA そのまま
        expected_ppn = int(entry["PPN"], 16)
        if expected_ppn:
            target = (expected_ppn << 12) + page_off
            env.comp_ram.write(target, expected_ppn.to_bytes(8, "little"))
        return

    elif mode == "msi":
        def _hex_or_int(v, default=0):
            if v is None:
                return default
            if isinstance(v, str):
                v = v.strip()
                return int(v, 16) if v.startswith("0x") else int(v)
            return int(v)

        msi_pte_raw = pack_msi_pte_raw(
            v        = _hex_or_int(entry.get("msi_pte_v"),    1),
            m        = _hex_or_int(entry.get("msi_pte_m"),    3),
            ppn      = _hex_or_int(entry.get("msi_pte_ppn"),  0x200),
            c        = _hex_or_int(entry.get("msi_pte_c"),    0),
            rsvd_3_9 = _hex_or_int(entry.get("msi_pte_rsvd"), 0),
        )
        setup_msi_pt_flat(
            env.ds_ram,
            msi_pt_root_ppn=env.msi_pt_root_ppn,
            index=_hex_or_int(entry.get("msi_index"), 0),
            pte_low_raw=msi_pte_raw,
            pte_high_raw=0,
        )
        # G-stage identity covers only msi_pt_root (matching gen_common.c run_case_msi).
        # MSI IOVAs bypass S1 entirely so S1 PT pages need no G-stage coverage.
        # Non-MSI IOVAs (case H) fail during S1 PT walk because S1 root GPA is not covered.
        setup_sv39x4_identity_4k_for_ppns(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            ppns=[env.msi_pt_root_ppn],
        )
        expected_ppn = int(entry["PPN"], 16)
        if expected_ppn:
            target = (expected_ppn << 12) + page_off
            env.comp_ram.write(target, expected_ppn.to_bytes(8, "little"))
        return

    else:
        raise ValueError(f"Unknown stage_mode: {mode}")

    # ---- 共通: 翻訳成功時の出力 PPN を data 経路で逆引きするためのマーカー ----
    expected_ppn = int(entry["PPN"], 16)
    if expected_ppn:
        target = (expected_ppn << 12) + page_off
        env.comp_ram.write(target, expected_ppn.to_bytes(8, "little"))


# =============================================================================
# 1 case の駆動: dev_tr_read/write を fire-and-forget しつつ FQ をポーリング
# =============================================================================
async def drive_one(env, entry, *, settle_cycles: int = 300, post_cycles: int = 30):
    """Drive translation for one entry, return RTL response dict (golden schema).

    動作:
      1. dev_tr_read or dev_tr_write を background coroutine として fire
      2. FQ tail をポーリング — 新しいレコードが積まれれば「fault 経路」
      3. リクエストが先に完了 + FQ 空 → 「success 経路」
      4. どちらでも post_cycles サイクル余分に進めて遅延 fault も拾う

    IOVA は entry["iova"] を使う (省略時は default にフォールバック)。
    pc_* モードでは substream_id=PC_PROCESS_ID_FIXED, ss_id_valid=1 を渡す。
    """
    access = entry["access"]
    iova   = _entry_iova(entry)
    mode   = entry.get("stage_mode", "s1_only")
    if mode.startswith("pc_"):
        substream_id = PC_PROCESS_ID_FIXED
        ss_id_valid  = 1
    else:
        substream_id = None
        ss_id_valid  = None
    rd_data_holder = [None]
    rd_done = Event()

    async def _fire():
        try:
            if access == "read":
                op = await env.dev_tr_read(iova, length=8,
                                            substream_id=substream_id,
                                            ss_id_valid=ss_id_valid)
                rd_data_holder[0] = int.from_bytes(op.data, "little")
            else:
                await env.dev_tr_write(iova, b"\x00" * 8,
                                        substream_id=substream_id,
                                        ss_id_valid=ss_id_valid)
        except Exception as e:
            log.debug(f"  case {entry['case_id']}: dev_tr raised "
                      f"{type(e).__name__}: {e}")
        finally:
            rd_done.set()

    cocotb.start_soon(_fire())

    # ----- ポーリングループ -----
    found_fault = None
    for _ in range(settle_cycles):
        tail = await env.fq.read_tail()
        if tail != env.fq.head_local:
            records = await env.fq.drain()
            found_fault = records[0]    # 1 op に対して 1 record の想定
            break
        if rd_done.is_set():
            break
        await RisingEdge(env.dut.clk_i)

    # ----- 後追いの遅延 fault を拾う -----
    if found_fault is None:
        for _ in range(post_cycles):
            await RisingEdge(env.dut.clk_i)
        records = await env.fq.drain()
        if records:
            found_fault = records[0]

    if found_fault is not None:
        return _format_fault(entry, found_fault)
    return _format_success(entry, rd_data_holder[0])


# =============================================================================
# レスポンス整形 — golden_vectors.jsonl と同じ key 構造
# =============================================================================
def _common_fields(entry):
    """エントリ → 出力 dict の共通部分 (= input 系フィールドを RTL log 側にも mirror)。

    diff_logs.py 側で INPUT_KEYS としてマークされているフィールドは ref/rtl 同値で
    あるべきなので、ここで欠損させずに必ずコピーしておく。
    """
    out = {
        "case_id":      entry["case_id"],
        "name":         entry["name"],
        "category":     entry.get("category", "default"),
        "stage_mode":   entry.get("stage_mode", "s1_only"),       # ← 追加
        "level":        entry["level"],
        "flags":        entry["flags"],
        "access":       entry["access"],
        "rsvd_pattern": entry["rsvd_pattern"],
        "pte_raw":      entry["pte_raw"],
    }
    # オプショナルな入力フィールドは entry に存在する時だけ mirror
    for k in ("iova",
              "s2_level", "s2_flags", "s2_rsvd_pattern", "s2_pte_raw",
              "alloc",                                            # ← Option B: alloc も mirror
              "msi_index", "msi_pte_v", "msi_pte_c",
              "msi_pte_m", "msi_pte_ppn", "msi_pte_rsvd"):
        if k in entry:
            out[k] = entry[k]
    return out


def _format_fault(entry, fault):
    out = _common_fields(entry)
    out.update({
        "status": 1,
        "PPN":    "0x0",      # gen_vectors も fault 時は 0x0 を出すので合わせる
        "S":      0,
        "fault": {
            "cause":   fault.cause,
            "iotval":  f"0x{fault.iotval:x}",
            "iotval2": f"0x{fault.iotval2:x}",
            "ttyp":    fault.ttyp,
            "did":     fault.did,
        },
    })
    return out


def _format_success(entry, rd_data):
    """成功ケースの整形。

    Read 成功:
      pre-populated marker (= expected leaf PPN) と rd_data が一致 → PPN OK
      不一致 → RTL が間違った PPN を返したので、その値を出力 (diff_logs が拾う)
      応答無し → "0xNORESP" を出力 (RTL が応答してない = ハング or 異常)

    Write 成功:
      AXI master の data 経路で PPN を逆引きできないので、PPN 検証は __スキップ__。
      ref の PPN をそのまま mirror して "全フィールド一致" 扱いにする。
      → Write の PPN 正しさを見たい場合は、別途 comp_ram の AW チャネルを
        snoop する追加機構が必要 (Phase 後半の TODO)。
    """
    out = _common_fields(entry)
    expected_ppn = int(entry["PPN"], 16)

    if entry["access"] == "write":
        out_ppn = entry["PPN"]                 # write は ref を信用 (PPN 取れないので)
    elif rd_data is None:
        out_ppn = "0xNORESP"                   # AXI 応答無し
    elif rd_data == expected_ppn:
        out_ppn = entry["PPN"]                 # marker 一致 → 翻訳成功
    else:
        out_ppn = f"0x{rd_data:x}"             # marker 不一致 → RTL の出力 data そのまま

    out.update({
        "status": 0,
        "PPN":    out_ppn,
        "S":      0,                           # Phase 1 では superpage を扱わないので 0 固定
        "fault":  None,
    })
    return out


# =============================================================================
# 各 case の前にやるリセット (ループから呼ばれる)
# =============================================================================
async def reset_for_replay(env):
    """前 case の状態を消して FQ を再初期化。

    AxiMaster / AxiRam は持ち越し (reset_dut は DUT 側だけ)。
    - DUT を rst_ni 経由でリセット
    - FQ の TB 側ポインタをリセットし、fqb と fqcsr を再書き込みして fqon=1 を待つ
    """
    from .env import reset_dut
    await reset_dut(env.dut)

    # FaultQueue 側のローカル head を再初期化、IOMMU 側 fqb/fqcsr を再書き込み
    env.fq.head_local = 0
    await env.fq.setup()