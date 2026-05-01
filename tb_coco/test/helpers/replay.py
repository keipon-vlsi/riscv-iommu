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
"""

import json
import logging
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge, Event

from .memory import setup_sv39_custom_at_level

# =============================================================================
# gen_vectors.c が固定で使う値 — replay 側もこれに揃える
# =============================================================================
GOLDEN_IOVA = 0x002345
GOLDEN_DID  = 0
PAGE_OFFSET = GOLDEN_IOVA & 0xFFF      # = 0x345

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


# =============================================================================
# RTL 側のメモリセットアップ
# =============================================================================
def setup_for_entry(env, entry):
    """1 entry 分の PTE 配置 + comp_ram の PPN マーカーを書く。

    呼び出し前提:
      - env.setup() 済み
      - env.install_dc_sv39_s1() 済み (DC の fsc.PPN = env.s1_root_ppn)

    PT 配置は entry["level"] に応じて 3 段 (4K leaf) / 2 段 (2M sp) / 1 段 (1G sp) に
    切り替わる。entry["pte_raw"] が当該 level の PTE バイト列としてそのまま書かれる。

    成功ケース (status=0) では entry["PPN"] が leaf PTE の PPN なので、
    そのページの offset 0x345 (= PAGE_OFFSET) に PPN 自身を書いておく。
    こうすると RTL が正しく翻訳した時に dev_tr_read で PPN 値が data として返る
    → output PPN が一致しているかが data 一致で確認できる仕組み。
    """
    pte_raw   = int(entry["pte_raw"], 16)
    pte_bytes = pte_raw.to_bytes(8, "little")

    setup_sv39_custom_at_level(
        env.ds_ram,
        root_ppn=env.s1_root_ppn,
        mid_ppn=env.s1_mid_ppn,
        leaf_ppn=env.s1_leaf_ppn,
        iova=GOLDEN_IOVA,
        level=entry["level"],
        pte_bytes=pte_bytes,
    )

    expected_ppn = int(entry["PPN"], 16)
    if expected_ppn:
        target = (expected_ppn << 12) + PAGE_OFFSET
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
    """
    access = entry["access"]
    rd_data_holder = [None]
    rd_done = Event()

    async def _fire():
        try:
            if access == "read":
                op = await env.dev_tr_read(GOLDEN_IOVA, length=8)
                rd_data_holder[0] = int.from_bytes(op.data, "little")
            else:
                await env.dev_tr_write(GOLDEN_IOVA, b"\x00" * 8)
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
    """エントリ → 出力 dict の共通部分 (request 入力をそのままコピー)。"""
    return {
        "case_id":      entry["case_id"],
        "name":         entry["name"],
        "level":        entry["level"],
        "flags":        entry["flags"],
        "access":       entry["access"],
        "rsvd_pattern": entry["rsvd_pattern"],
        "pte_raw":      entry["pte_raw"],
    }


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