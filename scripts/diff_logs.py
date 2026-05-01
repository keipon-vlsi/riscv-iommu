#!/usr/bin/env python3
"""diff_logs.py — RTL ログ vs リファレンスログ (golden_vectors.jsonl) の比較

使い方:
    # 基本: 全ケース比較してミスマッチ一覧 → exit 0/1
    python3 diff_logs.py --rtl rtl_log.jsonl --ref golden_vectors.jsonl

    # 1 件ミスマッチで停止 (デバッグ時に便利)
    python3 diff_logs.py --rtl rtl_log.jsonl --ref golden_vectors.jsonl --fail-fast

    # 特定フィールドを無視 (例: PPN は除外して fault 系だけ見る)
    python3 diff_logs.py --rtl rtl.jsonl --ref ref.jsonl --ignore PPN,S

Exit code:
    0 — 全件一致
    1 — 1 件以上ミスマッチ
    2 — case_id の集合が違う (片側にしかないケースがある)
"""

import argparse
import json
import sys
from pathlib import Path


# =============================================================================
# JSONL ローダ — case_id 単位の dict にして返す
# =============================================================================
def load_jsonl(path: Path) -> dict:
    """{case_id: entry_dict} を返す。case_id が無いか重複していたら警告。"""
    out = {}
    with path.open() as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError as ex:
                print(f"  ⚠ {path}:{line_num}: bad JSON ({ex})", file=sys.stderr)
                continue
            cid = e.get("case_id")
            if cid is None:
                print(f"  ⚠ {path}:{line_num}: no case_id, skip", file=sys.stderr)
                continue
            if cid in out:
                print(f"  ⚠ {path}:{line_num}: duplicate case_id {cid}, "
                      f"using later one", file=sys.stderr)
            out[cid] = e
    return out


# =============================================================================
# フィールド単位の diff
# =============================================================================
# 比較対象から除外する key (入力部分は両側で同じはずなので diff 不要)
INPUT_KEYS = {"case_id", "name", "level", "flags", "access",
              "rsvd_pattern", "pte_raw"}


def field_diff(rtl: dict, ref: dict, *, ignore_keys: set = ()) -> list:
    """両 dict の output 部分を比較、ミスマッチを (key, ref_val, rtl_val) のリストで返す。

    INPUT_KEYS はスキップ (= 入力なのでテストデータに従い同一であるべき)。
    `fault` フィールドは nested dict なので == で素直に比較。
    """
    keys = (set(rtl.keys()) | set(ref.keys())) - INPUT_KEYS - set(ignore_keys)
    diffs = []
    for k in sorted(keys):
        rv = ref.get(k)
        tv = rtl.get(k)
        if rv != tv:
            diffs.append((k, rv, tv))
    return diffs


# =============================================================================
# 表示フォーマッタ
# =============================================================================
def format_mismatch(case_id: int, name: str, diffs: list) -> str:
    lines = [f"  case {case_id:>4d} '{name}':"]
    for k, ref_v, rtl_v in diffs:
        lines.append(f"      {k:>10}: ref={_short(ref_v)} | rtl={_short(rtl_v)}")
    return "\n".join(lines)


def _short(v, *, maxlen: int = 60) -> str:
    s = repr(v)
    if len(s) > maxlen:
        s = s[:maxlen - 3] + "..."
    return s


# =============================================================================
# main
# =============================================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compare RTL replay log against reference (golden_vectors.jsonl)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--rtl", required=True, type=Path, help="RTL 側 JSONL のパス")
    ap.add_argument("--ref", required=True, type=Path, help="リファレンス側 JSONL のパス")
    ap.add_argument("--fail-fast", action="store_true",
                    help="最初のミスマッチで停止 (詳細を 1 件だけ表示)")
    ap.add_argument("--ignore", default="",
                    help="比較から除外するフィールド名 (カンマ区切り、例: 'PPN,S')")
    args = ap.parse_args()

    if not args.rtl.exists():
        print(f"ERROR: RTL log not found: {args.rtl}", file=sys.stderr)
        return 1
    if not args.ref.exists():
        print(f"ERROR: ref log not found: {args.ref}", file=sys.stderr)
        return 1

    ignore_keys = set(s.strip() for s in args.ignore.split(",") if s.strip())

    rtl = load_jsonl(args.rtl)
    ref = load_jsonl(args.ref)

    only_in_rtl = set(rtl) - set(ref)
    only_in_ref = set(ref) - set(rtl)
    common      = set(rtl) & set(ref)

    print(f"  rtl log: {len(rtl):>5} cases  ({args.rtl})")
    print(f"  ref log: {len(ref):>5} cases  ({args.ref})")
    if only_in_rtl:
        head = sorted(only_in_rtl)[:10]
        ellip = "..." if len(only_in_rtl) > 10 else ""
        print(f"  ⚠ {len(only_in_rtl)} case_ids only in RTL: {head}{ellip}")
    if only_in_ref:
        head = sorted(only_in_ref)[:10]
        ellip = "..." if len(only_in_ref) > 10 else ""
        print(f"  ⚠ {len(only_in_ref)} case_ids only in REF: {head}{ellip}")

    # ---- 比較 ----
    mismatches = []
    matches = 0
    for cid in sorted(common):
        diffs = field_diff(rtl[cid], ref[cid], ignore_keys=ignore_keys)
        if diffs:
            mismatches.append((cid, ref[cid].get("name", "?"), diffs))
            if args.fail_fast:
                break
        else:
            matches += 1

    print()
    print(f"  matches    : {matches}")
    print(f"  mismatches : {len(mismatches)}{' (fail-fast: stopped early)' if args.fail_fast and mismatches else ''}")

    if mismatches:
        print()
        print("=== Mismatches ===")
        for cid, name, diffs in mismatches:
            print(format_mismatch(cid, name, diffs))

    # ---- exit code ----
    if mismatches:
        return 1
    if only_in_rtl or only_in_ref:
        print()
        print("⚠ Coverage gaps exist (case_id sets differ between RTL and REF)")
        return 2

    print()
    print(f"✓ All {matches} cases match")
    return 0


if __name__ == "__main__":
    sys.exit(main())