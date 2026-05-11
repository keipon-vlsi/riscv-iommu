"""test_replay_golden — golden_*.jsonl の各カテゴリを RTL に流す replay 試験

実行:
    cd tb_coco/test
    make replay              # 全カテゴリ実行 + diff
    make replay-fail-fast    # 1 件目 mismatch で停止

入力 (env で上書き可):
    GOLDEN_DIR    reference 側ログを置いてあるディレクトリ。
                  省略時 ../tb_coco/test/reference/gen_vectors/
                  ここの golden_*.jsonl を全部 auto discovery する。
    GOLDEN_JSONL  単一ファイルだけを指定したいとき (1 カテゴリだけ流す)
    RTL_LOG_JSONL RTL 側ログの出力先。省略時 ./rtl_log.jsonl

各 entry に対して:
  1. DUT を reset → FQ 再 enable
  2. install_dc_sv39_s1() で DDT/DC を再構築
  3. setup_for_entry() で entry の PTE と IOVA をメモリに配置
  4. drive_one() で dev_tr リクエストを発行 → 応答を golden 同形式で取得
  5. log file に追記 (category フィールド付き)

カテゴリを跨いで連続実行されるが、各 entry の category は rtl_log にコピーされるので、
diff_logs.py が (category, case_id) 複合キーで突き合わせる。
"""

import json
import logging
import os
from pathlib import Path

import cocotb

from helpers import IommuEnv
from helpers.replay import (
    parse_jsonl,
    setup_dc_for_entry,
    setup_for_entry,
    drive_one,
    reset_for_replay,
    GOLDEN_DID,
)


log = logging.getLogger("cocotb.tb.replay_test")


def _resolve_paths():
    """env var or default から入出力 JSONL のパスを解決。

    優先順:
      GOLDEN_FILES (= space-separated パス列)  ← tier 別 replay で使う (Makefile が指定)
        > GOLDEN_JSONL (= 単一ファイル)         ← 単カテゴリデバッグ用
        > GOLDEN_DIR/glob                       ← 自動 discovery (= ディレクトリ内全部)
    """
    here = Path(__file__).resolve().parent           # .../tb_coco/test/scenarios
    test_dir = here.parent                            # .../tb_coco/test

    default_golden_dir = test_dir / "reference" / "gen_vectors"
    default_rtl_log    = test_dir / "rtl_log.jsonl"

    explicit_list = os.environ.get("GOLDEN_FILES")
    explicit_one  = os.environ.get("GOLDEN_JSONL")

    if explicit_list:
        # tier 別 replay: Makefile が必要な JSONL だけ列挙して渡す
        golden_paths = [Path(p) for p in explicit_list.split() if p]
    elif explicit_one:
        explicit_path = Path(explicit_one)
        if not explicit_path.is_absolute():
            explicit_path = test_dir / explicit_path
        golden_paths = [explicit_path]
    else:
        golden_dir = Path(os.environ.get("GOLDEN_DIR", default_golden_dir))
        golden_paths = sorted(golden_dir.glob("golden_*.jsonl"))

    rtl_log = Path(os.environ.get("RTL_LOG_JSONL", default_rtl_log))
    return golden_paths, rtl_log


@cocotb.test(timeout_time=600_000, timeout_unit="ms")    # = 600 秒分のシミュレーション時間
async def test_replay_golden(dut):
    """全カテゴリの golden_*.jsonl を RTL に replay し、rtl_log.jsonl に書き出す。"""
    golden_paths, rtl_log_path = _resolve_paths()

    if not golden_paths:
        raise RuntimeError(
            "No golden_*.jsonl files found.\n"
            "→ まず `make -C reference/gen_vectors run` でリファレンスログを生成してください。"
        )

    # 全 JSONL を読み込み、category フィールドで分類しつつ順に蓄積
    all_entries = []
    cat_counts = {}
    for gp in golden_paths:
        cat_name = gp.stem.replace("golden_", "")     # "phase1_pte_flags" 等
        n = 0
        for entry in parse_jsonl(gp):
            entry.setdefault("category", cat_name)    # 古いログ互換: category 欠損なら filename から
            all_entries.append(entry)
            n += 1
        cat_counts[cat_name] = n
        log.info(f"  loaded {gp.name:35s} ({n} cases)")

    log.info(f"=== Replay {len(all_entries)} cases total "
             f"({len(golden_paths)} categories) ===")
    log.info(f"=== RTL log → {rtl_log_path} ===")

    # ---- env 初期化は 1 度だけ (AxiMaster/AxiRam は持ち越し) ----
    env = IommuEnv(dut)
    await env.setup(enable_fq=True)

    # ---- 出力ファイル準備 (上書き) ----
    rtl_log_path.parent.mkdir(parents=True, exist_ok=True)
    n_total = len(all_entries)
    n_ok    = 0
    n_err   = 0

    with rtl_log_path.open("w") as logf:
        for i, entry in enumerate(all_entries):
            cid      = entry["case_id"]
            name     = entry["name"]
            category = entry["category"]

            try:
                # ---- 1. リセット + FQ 再 enable (最初のケースは setup() 直後なのでスキップ) ----
                if i > 0:
                    await reset_for_replay(env)

                # ---- 2. DC / DDT を install (stage_mode に応じて切替) ----
                await setup_dc_for_entry(env, entry)

                # ---- 3. PTE をメモリに配置 + PPN マーカー (per-entry IOVA) ----
                setup_for_entry(env, entry)

                # ---- 4. translation を駆動して結果を捕捉 ----
                rtl_resp = await drive_one(env, entry)
                n_ok += 1

            except Exception as e:
                # 1 ケースの失敗で全体を諦めず、catch して継続
                log.error(f"  [{category}] case {cid:4d} ({name}): EXCEPTION "
                          f"{type(e).__name__}: {e}")
                rtl_resp = {
                    "case_id":      cid,
                    "name":         name,
                    "category":     category,
                    "level":        entry.get("level"),
                    "flags":        entry.get("flags"),
                    "access":       entry.get("access"),
                    "rsvd_pattern": entry.get("rsvd_pattern", 0),
                    "pte_raw":      entry.get("pte_raw"),
                    "iova":         entry.get("iova"),
                    "status":       -1,
                    "PPN":          "0xEXCEPTION",
                    "S":            0,
                    "fault":        {"error": f"{type(e).__name__}: {e}"},
                }
                n_err += 1

            # category は drive_one 経由でも _common_fields がコピーするが、念のため
            rtl_resp["category"] = category

            logf.write(json.dumps(rtl_resp) + "\n")
            logf.flush()

            if (i + 1) % 100 == 0:
                log.info(f"  ... {i+1:5d}/{n_total} done")

    log.info(f"=== Replay complete: {n_ok} ok, {n_err} exceptions ===")
    log.info(f"=== Wrote {rtl_log_path} ===")

    # 全件 exception はインフラの問題なので test fail
    assert n_err < n_total, "All replay cases hit exceptions — check setup"