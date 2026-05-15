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

v2 (= デバッグ追加):
  drive_one() に poll watchdog を追加。 settle_cycles 中に
  進捗が無いまま長時間ポーリングしている場合に warn ログを残す。
  これで hang したケースの polling 状況が見える。
"""

import json
import logging
import os
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
# Default values
# =============================================================================
DEFAULT_IOVA = 0x002345
GOLDEN_DID   = 0
DEFAULT_PAGE_OFFSET = DEFAULT_IOVA & 0xFFF
GOLDEN_IOVA = DEFAULT_IOVA

# =============================================================================
# Debug: watchdog 設定 (= env で override 可)
# =============================================================================
#   POLL_WATCHDOG_EVERY     : この回数毎に polling 中であることを warn log
#                             (= 0 で無効化、 デフォルト 100)
#   POLL_WATCHDOG_VERBOSE   : =1 で各 watchdog log に AXI master の最後の挙動も付ける
POLL_WATCHDOG_EVERY   = int(os.environ.get("POLL_WATCHDOG_EVERY",   "100"))
POLL_WATCHDOG_VERBOSE = int(os.environ.get("POLL_WATCHDOG_VERBOSE", "0"))

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
    """エントリから IOVA を取り出す。無ければ default 0x002345。"""
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


def _apply_alloc_override(env, entry):
    """JSONL の "alloc" field から PPN を読み取って env の対応属性を上書き。"""
    alloc = entry.get("alloc")
    if not alloc:
        return

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
    """entry の stage_mode に応じて DC を配置する。"""
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
    """1 entry 分の PT 配置 + comp_ram の PPN マーカーを書く (stage_mode で分岐)。"""
    iova     = _entry_iova(entry)
    page_off = iova & 0xFFF
    mode     = entry.get("stage_mode", "s1_only")

    pte_raw   = int(entry["pte_raw"], 16)
    pte_bytes = pte_raw.to_bytes(8, "little")

    if mode == "s1_only":
        setup_sv39_custom_at_level(
            env.ds_ram,
            root_ppn=env.s1_root_ppn, mid_ppn=env.s1_mid_ppn, leaf_ppn=env.s1_leaf_ppn,
            iova=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "s2_only":
        setup_sv39x4_custom_at_level(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            gpa=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "nested":
        leaf_ppn_from_pte = (pte_raw >> 10) & 0x0FFF_FFFF_FFFF
        setup_sv39x4_identity_4k_for_ppns(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            ppns=[
                env.s1_root_ppn,
                env.s1_mid_ppn,
                env.s1_leaf_ppn,
                leaf_ppn_from_pte,
            ],
        )
        setup_sv39_custom_at_level(
            env.ds_ram,
            root_ppn=env.s1_root_ppn, mid_ppn=env.s1_mid_ppn, leaf_ppn=env.s1_leaf_ppn,
            iova=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "nested_full":
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
        setup_sv39_custom_at_level(
            env.ds_ram,
            root_ppn=env.s1_root_ppn, mid_ppn=env.s1_mid_ppn, leaf_ppn=env.s1_leaf_ppn,
            iova=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode == "pc_s2_only":
        pdt_ppns = [env.pdt_root_ppn, env.pdt_l1_ppn, env.pdt_leaf_ppn]
        setup_sv39x4_identity_4k_for_ppns(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            ppns=pdt_ppns,
        )
        write_sv39x4_pte_at_level_no_clear(
            env.ds_ram,
            root_ppn=env.g_root_ppn, mid_ppn=env.g_mid_ppn, leaf_ppn=env.g_leaf_ppn,
            gpa=iova, level=entry["level"], pte_bytes=pte_bytes,
        )

    elif mode in ("pc_nested", "pc_nested_full_quick"):
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

    expected_ppn = int(entry["PPN"], 16)
    if expected_ppn:
        target = (expected_ppn << 12) + page_off
        env.comp_ram.write(target, expected_ppn.to_bytes(8, "little"))


# =============================================================================
# 1 case の駆動: dev_tr_read/write を fire-and-forget しつつ FQ をポーリング
# =============================================================================
async def drive_one(env, entry, *, settle_cycles: int = 300, post_cycles: int = 30):
    """Drive translation for one entry, return RTL response dict (golden schema).

    v2 改善: settle_cycles 中の watchdog log を追加。
      POLL_WATCHDOG_EVERY 回のポーリング毎に warn log を出す。
      これで「同一ケースで延々と polling し続けている」 状況が log で見える。
    """
    access   = entry["access"]
    iova     = _entry_iova(entry)
    mode     = entry.get("stage_mode", "s1_only")
    cid      = entry.get("case_id", "?")
    category = entry.get("category", "?")

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
            log.debug(f"  case {category}#{cid}: dev_tr raised "
                      f"{type(e).__name__}: {e}")
        finally:
            rd_done.set()

    cocotb.start_soon(_fire())

    # ----- ポーリングループ (= watchdog 付き) -----
    found_fault = None
    n_iter = 0
    for n_iter in range(1, settle_cycles + 1):
        tail = await env.fq.read_tail()
        if tail != env.fq.head_local:
            records = await env.fq.drain()
            found_fault = records[0]
            break
        if rd_done.is_set():
            break
        await RisingEdge(env.dut.clk_i)

        # ★ Watchdog: POLL_WATCHDOG_EVERY 回ごとに warn
        if POLL_WATCHDOG_EVERY > 0 and (n_iter % POLL_WATCHDOG_EVERY == 0):
            sim_t = cocotb.utils.get_sim_time(unit="ns")
            log.warning(
                f"  ⚠ case {category}#{cid} ({access}, iova=0x{iova:x}): "
                f"polling iter={n_iter}/{settle_cycles}, "
                f"fqt={tail} head={env.fq.head_local}, "
                f"rd_done={rd_done.is_set()}, sim={sim_t/1000:.1f}us"
            )

    # ★ settle_cycles 使い切ったのに何も起きなかった = この case が問題の可能性大
    if not rd_done.is_set() and found_fault is None:
        sim_t = cocotb.utils.get_sim_time(unit="ns")
        log.error(
            f"  ✖ case {category}#{cid} ({access}, iova=0x{iova:x}): "
            f"SETTLE_CYCLES EXHAUSTED after {settle_cycles} polls, "
            f"no fault and dev_tr not done. sim={sim_t/1000:.1f}us"
        )

    # ----- 後追いの遅延 fault -----
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
# レスポンス整形
# =============================================================================
def _common_fields(entry):
    """エントリ → 出力 dict の共通部分。"""
    out = {
        "case_id":      entry["case_id"],
        "name":         entry["name"],
        "category":     entry.get("category", "default"),
        "stage_mode":   entry.get("stage_mode", "s1_only"),
        "level":        entry["level"],
        "flags":        entry["flags"],
        "access":       entry["access"],
        "rsvd_pattern": entry["rsvd_pattern"],
        "pte_raw":      entry["pte_raw"],
    }
    for k in ("iova",
              "s2_level", "s2_flags", "s2_rsvd_pattern", "s2_pte_raw",
              "alloc",
              "msi_index", "msi_pte_v", "msi_pte_c",
              "msi_pte_m", "msi_pte_ppn", "msi_pte_rsvd"):
        if k in entry:
            out[k] = entry[k]
    return out


def _format_fault(entry, fault):
    out = _common_fields(entry)
    out.update({
        "status": 1,
        "PPN":    "0x0",
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
    out = _common_fields(entry)
    expected_ppn = int(entry["PPN"], 16)

    if entry["access"] == "write":
        out_ppn = entry["PPN"]
    elif rd_data is None:
        out_ppn = "0xNORESP"
    elif rd_data == expected_ppn:
        out_ppn = entry["PPN"]
    else:
        out_ppn = f"0x{rd_data:x}"

    out.update({
        "status": 0,
        "PPN":    out_ppn,
        "S":      0,
        "fault":  None,
    })
    return out


# =============================================================================
# 各 case の前にやるリセット
# =============================================================================
async def reset_for_replay(env):
    """前 case の状態を消して FQ を再初期化。"""
    from .env import reset_dut
    await reset_dut(env.dut)

    env.fq.head_local = 0
    await env.fq.setup()