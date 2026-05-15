"""test_replay_golden — golden_*.jsonl の各カテゴリを RTL に流す replay 試験

実行:
    cd tb_coco/test
    make replay              # 全カテゴリ実行 + diff
    make replay-fail-fast    # 1 件目 mismatch で停止

入力 (env で上書き可):
    GOLDEN_DIR    reference 側ログを置いてあるディレクトリ。
    GOLDEN_JSONL  単一ファイルだけを指定したいとき (1 カテゴリだけ流す)
    RTL_LOG_JSONL RTL 側ログの出力先。省略時 ./rtl_log.jsonl

    -- デバッグ用 env --
    REPLAY_LOG_EVERY      各ケースの開始 log を何ケース毎に出すか
                          1 (デフォルト) = 全ケース、 100 = 100 ケース毎、 0 = カテゴリ境界のみ
    REPLAY_START_FROM     何ケース目から開始するか (= 0 開始の index、 デフォルト 0)
    REPLAY_STOP_AFTER     何ケース実行したら終了するか (デフォルト 0 = 全部)
    REPLAY_LOG_TIMEOUTS   timeout 検出時に個別 log を残す数の上限 (デフォルト 10)

v3 追加 (= timeout 集計):
    - PPN="0xNORESP" のケース (= settle_cycles 枯渇) を timeout として計上
    - 最終 summary で per-category 内訳 + 最初の数件の case 名を表示
"""

import json
import logging
import os
import time
from collections import defaultdict
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


# =============================================================================
# Debug env vars
# =============================================================================
LOG_EVERY        = int(os.environ.get("REPLAY_LOG_EVERY",     "1"))
START_FROM       = int(os.environ.get("REPLAY_START_FROM",    "0"))
STOP_AFTER       = int(os.environ.get("REPLAY_STOP_AFTER",    "0"))
LOG_TIMEOUTS_MAX = int(os.environ.get("REPLAY_LOG_TIMEOUTS", "10"))


def _resolve_paths():
    """env var or default から入出力 JSONL のパスを解決。"""
    here = Path(__file__).resolve().parent
    test_dir = here.parent

    default_golden_dir = test_dir / "reference" / "gen_vectors"
    default_rtl_log    = test_dir / "rtl_log.jsonl"

    explicit_list = os.environ.get("GOLDEN_FILES")
    explicit_one  = os.environ.get("GOLDEN_JSONL")

    if explicit_list:
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


def _fmt_case(i, n_total, entry, sim_t_ns, real_t_s, tag=""):
    """1 行の case log を組み立てる。"""
    cid      = entry.get("case_id", "?")
    name     = entry.get("name", "?")
    category = entry.get("category", "?")
    access   = entry.get("access", "?")
    return (f"{tag:>4s} [{i+1:5d}/{n_total}] "
            f"sim={sim_t_ns/1000:9.1f}us real={real_t_s:6.1f}s "
            f"{category:28s} #{cid:4d} ({access:5s}) {name}")


def _is_timeout(rtl_resp):
    """rtl_resp が timeout (= dev_tr 応答無し) を示しているか判定。"""
    if rtl_resp.get("status") != 0:
        return False
    return rtl_resp.get("PPN") == "0xNORESP"


@cocotb.test(timeout_time=600_000, timeout_unit="ms")
async def test_replay_golden(dut):
    """全カテゴリの golden_*.jsonl を RTL に replay し、rtl_log.jsonl に書き出す。"""
    golden_paths, rtl_log_path = _resolve_paths()

    if not golden_paths:
        raise RuntimeError(
            "No golden_*.jsonl files found.\n"
            "→ まず `make -C reference/gen_vectors run` でリファレンスログを生成してください。"
        )

    # ---- 全 JSONL を読み込み ----
    all_entries = []
    cat_counts = {}
    for gp in golden_paths:
        cat_name = gp.stem.replace("golden_", "")
        n = 0
        for entry in parse_jsonl(gp):
            entry.setdefault("category", cat_name)
            all_entries.append(entry)
            n += 1
        cat_counts[cat_name] = n
        log.info(f"  loaded {gp.name:35s} ({n} cases)")

    n_total = len(all_entries)
    log.info(f"=== Replay {n_total} cases total ({len(golden_paths)} categories) ===")
    log.info(f"=== RTL log → {rtl_log_path} ===")

    # ---- range の絞り込み ----
    start_idx = max(0, START_FROM)
    if STOP_AFTER > 0:
        end_idx = min(n_total, start_idx + STOP_AFTER)
    else:
        end_idx = n_total
    range_filtered = (start_idx > 0) or (end_idx < n_total)
    if range_filtered:
        log.info(f"=== Range filter: cases [{start_idx}, {end_idx}) "
                 f"(= {end_idx - start_idx} cases) ===")
    if LOG_EVERY != 1:
        log.info(f"=== REPLAY_LOG_EVERY={LOG_EVERY} (= 進捗 log の間引き) ===")

    # ---- env 初期化 ----
    env = IommuEnv(dut)
    await env.setup(enable_fq=True)

    rtl_log_path.parent.mkdir(parents=True, exist_ok=True)

    # ---- カウンタ + 集計用辞書 ----
    n_ok       = 0
    n_err      = 0
    n_timeout  = 0
    timeout_per_category = defaultdict(int)   # {category: count}
    timeout_examples     = []                  # 最初の N 件の (i, entry) を集める

    real_time_start = time.time()
    cur_i      = start_idx
    cur_entry  = all_entries[start_idx] if n_total else None
    prev_cat   = None

    try:
        with rtl_log_path.open("w") as logf:
            for i in range(start_idx, end_idx):
                entry = all_entries[i]
                cur_i = i
                cur_entry = entry

                if entry["category"] != prev_cat:
                    sim_t  = cocotb.utils.get_sim_time(unit="ns")
                    real_t = time.time() - real_time_start
                    log.info(f"  ─── enter category '{entry['category']}' at "
                             f"sim={sim_t/1000:.1f}us real={real_t:.1f}s ───")
                    prev_cat = entry["category"]

                if LOG_EVERY > 0 and (i % LOG_EVERY == 0):
                    sim_t  = cocotb.utils.get_sim_time(unit="ns")
                    real_t = time.time() - real_time_start
                    log.info(_fmt_case(i, n_total, entry, sim_t, real_t, tag="▶"))

                try:
                    if i > start_idx:
                        await reset_for_replay(env)
                    await setup_dc_for_entry(env, entry)
                    setup_for_entry(env, entry)
                    rtl_resp = await drive_one(env, entry)
                    n_ok += 1

                except Exception as e:
                    sim_t = cocotb.utils.get_sim_time(unit="ns")
                    log.error(f"  [{entry['category']}] case {entry['case_id']:4d} "
                              f"({entry['name']}): EXCEPTION at sim={sim_t/1000:.1f}us "
                              f"{type(e).__name__}: {e}")
                    rtl_resp = {
                        "case_id":      entry["case_id"],
                        "name":         entry["name"],
                        "category":     entry["category"],
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

                rtl_resp["category"] = entry["category"]

                # ★ Timeout 検出 (= PPN="0xNORESP" → dev_tr 応答無し)
                if _is_timeout(rtl_resp):
                    n_timeout += 1
                    timeout_per_category[entry["category"]] += 1
                    if len(timeout_examples) < LOG_TIMEOUTS_MAX:
                        timeout_examples.append((i, entry))
                        sim_t = cocotb.utils.get_sim_time(unit="ns")
                        log.warning(f"  ⏱ TIMEOUT [{i+1:5d}/{n_total}] "
                                    f"{entry['category']}#{entry['case_id']:4d} "
                                    f"({entry.get('access','?')}) {entry['name']} "
                                    f"at sim={sim_t/1000:.1f}us")

                logf.write(json.dumps(rtl_resp) + "\n")
                logf.flush()

                if (i + 1) % 100 == 0 and LOG_EVERY != 1:
                    sim_t  = cocotb.utils.get_sim_time(unit="ns")
                    real_t = time.time() - real_time_start
                    log.info(f"  ... progress {i+1:5d}/{n_total} "
                             f"(ok={n_ok}, err={n_err}, timeout={n_timeout}, "
                             f"sim={sim_t/1000:.1f}us real={real_t:.1f}s)")

    except (KeyboardInterrupt, SystemExit) as e:
        sim_t  = cocotb.utils.get_sim_time(unit="ns")
        real_t = time.time() - real_time_start
        log.error("=" * 80)
        log.error(f"  ★★★ INTERRUPTED by user ({type(e).__name__}) ★★★")
        log.error(_fmt_case(cur_i, n_total, cur_entry, sim_t, real_t, tag="★"))
        log.error(f"  ★★★ ok={n_ok}, err={n_err}, timeout={n_timeout}, "
                  f"sim_t={sim_t/1000:.1f}us, real_t={real_t:.1f}s ★★★")
        log.error("=" * 80)
        _print_timeout_summary(n_timeout, timeout_per_category, timeout_examples)
        raise

    except BaseException as e:
        sim_t  = cocotb.utils.get_sim_time(unit="ns")
        real_t = time.time() - real_time_start
        log.error("=" * 80)
        log.error(f"  ★★★ FATAL: {type(e).__name__}: {e} ★★★")
        log.error(_fmt_case(cur_i, n_total, cur_entry, sim_t, real_t, tag="★"))
        log.error(f"  ★★★ ok={n_ok}, err={n_err}, timeout={n_timeout}, "
                  f"sim_t={sim_t/1000:.1f}us, real_t={real_t:.1f}s ★★★")
        log.error("=" * 80)
        _print_timeout_summary(n_timeout, timeout_per_category, timeout_examples)
        raise

    # ---- 完走 summary ----
    log.info("=" * 80)
    log.info(f"=== Replay complete: ok={n_ok}, exceptions={n_err}, "
             f"timeouts={n_timeout} (= {100*n_timeout/max(n_ok,1):.1f}%) ===")
    log.info(f"=== Wrote {rtl_log_path} ===")
    _print_timeout_summary(n_timeout, timeout_per_category, timeout_examples)
    log.info("=" * 80)

    assert n_err < n_total, "All replay cases hit exceptions — check setup"


# =============================================================================
# Timeout summary を log に出すヘルパー
# =============================================================================
def _print_timeout_summary(n_timeout, timeout_per_category, timeout_examples):
    """Timeout した case の内訳を log に出力。"""
    if n_timeout == 0:
        log.info("  ✓ No timeout cases (= 全ケース dev_tr が応答 or fault を返した)")
        return

    log.error(f"  ⏱ TIMEOUT summary: {n_timeout} case(s) returned 0xNORESP")
    log.error(f"     (= settle_cycles 枯渇、 dev_tr 応答も FQ enqueue もなかったケース)")

    # Per-category breakdown
    log.error(f"  ⏱ Per-category breakdown:")
    log.error(f"     {'category':30s} {'count':>8s}")
    log.error(f"     {'-' * 30} {'-' * 8}")
    for cat, cnt in sorted(timeout_per_category.items(), key=lambda x: -x[1]):
        log.error(f"     {cat:30s} {cnt:>8d}")

    # First N examples
    log.error(f"  ⏱ First {len(timeout_examples)} timeout example(s):")
    for i, entry in timeout_examples:
        log.error(f"     [{i+1:5d}] {entry['category']:28s} "
                  f"#{entry.get('case_id', '?'):>4} "
                  f"({entry.get('access','?'):5s}) {entry.get('name','?')}")
    if n_timeout > len(timeout_examples):
        log.error(f"     ... and {n_timeout - len(timeout_examples)} more "
                  f"(set REPLAY_LOG_TIMEOUTS=N to see more)")