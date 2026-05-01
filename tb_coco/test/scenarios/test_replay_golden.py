"""test_replay_golden — golden_vectors.jsonl の 1124 ケースを RTL に流す replay 試験

実行:
    cd tb_coco/test
    make sim MODULE=test_replay_golden
    # または
    make replay   # ← 実行 + 自動 diff

入力:
    GOLDEN_JSONL  (env)  reference 側ログのパス。
                          省略時 ../reference/gen_vectors/golden_vectors.jsonl
出力:
    RTL_LOG_JSONL (env)  RTL 側ログを書き出すパス。
                          省略時 ./rtl_log.jsonl (= cocotb の cwd)

各 entry に対して:
  1. DUT を reset → FQ 再 enable
  2. install_dc_sv39_s1() で DDT/DC を再構築
  3. setup_for_entry() で entry の PTE をメモリに配置
  4. drive_one() で dev_tr リクエストを発行 → 応答を golden 同形式で取得
  5. log file に追記

ケース間で reset を打つので動作は遅め (1124 ケース × reset ~50 cycle で
シミュレーション時間ベースで数 ms オーダー、wall-clock では数分の見込み)。
速度を詰めたくなったら CQ 経由の IOTINVAL に置き換える。
"""

import json
import logging
import os
from pathlib import Path

import cocotb

from helpers import IommuEnv
from helpers.replay import (
    parse_jsonl,
    setup_for_entry,
    drive_one,
    reset_for_replay,
    GOLDEN_DID,
)


log = logging.getLogger("cocotb.tb.replay_test")


def _resolve_paths():
    """env var or default で入出力 JSONL のパスを決定。"""
    here = Path(__file__).resolve().parent           # .../tb_coco/test/scenarios
    test_dir = here.parent                            # .../tb_coco/test

    default_golden = test_dir / "reference" / "gen_vectors" / "golden_vectors.jsonl"
    default_rtl_log = test_dir / "rtl_log.jsonl"

    golden = Path(os.environ.get("GOLDEN_JSONL", default_golden))
    rtl_log = Path(os.environ.get("RTL_LOG_JSONL", default_rtl_log))
    return golden, rtl_log


@cocotb.test(timeout_time=600_000, timeout_unit="ms")    # = 600 秒分のシミュレーション時間
                                                          # (実際の wall-clock とは別物)
async def test_replay_golden(dut):
    """1124 ケースを RTL に replay し、結果を rtl_log.jsonl に書き出す。"""
    golden_path, rtl_log_path = _resolve_paths()

    if not golden_path.exists():
        raise RuntimeError(
            f"golden_vectors.jsonl not found: {golden_path}\n"
            "→ まず `make -C reference/gen_vectors run` でリファレンスログを生成してください。"
        )

    entries = list(parse_jsonl(golden_path))
    log.info(f"=== Replay {len(entries)} cases from {golden_path} ===")
    log.info(f"=== RTL log → {rtl_log_path} ===")

    # ---- env 初期化は 1 度だけ (AxiMaster/AxiRam は持ち越し) ----
    env = IommuEnv(dut)
    await env.setup(enable_fq=True)

    # ---- 出力ファイル準備 (上書き) ----
    rtl_log_path.parent.mkdir(parents=True, exist_ok=True)
    n_cases = len(entries)
    n_ok    = 0
    n_err   = 0

    with rtl_log_path.open("w") as logf:
        for i, entry in enumerate(entries):
            cid  = entry["case_id"]
            name = entry["name"]

            try:
                # ---- 1. リセット + FQ 再 enable ----
                # 最初のケースは setup() 直後なのでスキップしても OK だが、
                # 一貫性のため毎回打つ。
                if i > 0:
                    await reset_for_replay(env)

                # ---- 2. DC / DDT を install ----
                await env.install_dc_sv39_s1(did=GOLDEN_DID)

                # ---- 3. PTE をメモリに配置 + PPN マーカー ----
                setup_for_entry(env, entry)

                # ---- 4. translation を駆動して結果を捕捉 ----
                rtl_resp = await drive_one(env, entry)
                n_ok += 1

            except Exception as e:
                # 1 ケースの失敗で 1124 全部諦めたくないので catch して継続
                log.error(f"  case {cid:4d} ({name}): EXCEPTION "
                          f"{type(e).__name__}: {e}")
                rtl_resp = {
                    **{k: entry[k] for k in
                       ("case_id", "name", "level", "flags", "access",
                        "rsvd_pattern", "pte_raw")},
                    "status": -1,
                    "PPN":    "0xEXCEPTION",
                    "S":      0,
                    "fault":  {"error": f"{type(e).__name__}: {e}"},
                }
                n_err += 1

            # ---- 5. log に追記 ----
            logf.write(json.dumps(rtl_resp) + "\n")
            logf.flush()

            if (i + 1) % 100 == 0:
                log.info(f"  ... {i+1:4d}/{n_cases} done")

    log.info(f"=== Replay complete: {n_ok} ok, {n_err} exceptions ===")
    log.info(f"=== Wrote {rtl_log_path} ===")

    # 単体ケースの fail でテスト全体を fail にはしない (diff_logs 側で判定)。
    # ただし全件 exception になっていたら何かおかしいので fail。
    assert n_err < n_cases, "All replay cases hit exceptions — check setup"