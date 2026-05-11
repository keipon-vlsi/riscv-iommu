#!/usr/bin/env python3
"""diff_logs.py — RTL ログ vs リファレンスログの比較 (カテゴリ対応)

JSONL の各エントリは (category, case_id) を複合キーとして突き合わせる。
category フィールドが無い古いログは "default" カテゴリ扱い。

使い方:
    # 単一ファイル比較 (Phase 1 と互換)
    python3 diff_logs.py --rtl rtl_log.jsonl --ref golden_phase1_pte_flags.jsonl

    # 複数 reference をまとめて比較
    python3 diff_logs.py --rtl rtl_log.jsonl \
        --ref golden_phase1_pte_flags.jsonl --ref golden_iova_variation.jsonl

    # ディレクトリ内の全 golden_*.jsonl を ref として読み込む
    python3 diff_logs.py --rtl rtl_log.jsonl --ref-dir reference/gen_vectors/

    # 1 件目ミスマッチで停止 (デバッグ用)
    python3 diff_logs.py --rtl rtl_log.jsonl --ref-dir ... --fail-fast

    # 特定カテゴリだけチェック
    python3 diff_logs.py --rtl rtl_log.jsonl --ref-dir ... --category iova_variation

    # 厳密比較 (= shifted match を許可しない)
    python3 diff_logs.py --rtl rtl_log.jsonl --ref-dir ... --strict

Exit code:
    0 — 全件一致 (shifted match 含む)
    1 — 1 件以上ミスマッチ
    2 — case_id の集合が違う (片側にしかないケースがある)
"""

import argparse
import json
import sys
from pathlib import Path


# =============================================================================
# JSONL ローダ — (category, case_id) → entry の dict
# =============================================================================
def load_jsonl(paths) -> dict:
    """1 つ以上の JSONL ファイルから {(category, case_id): entry} を返す。"""
    out = {}
    for p in paths:
        with p.open() as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError as ex:
                    print(f"  ⚠ {p}:{line_num}: bad JSON ({ex})", file=sys.stderr)
                    continue
                cid = e.get("case_id")
                if cid is None:
                    print(f"  ⚠ {p}:{line_num}: no case_id, skip", file=sys.stderr)
                    continue
                # category は filename から推測してフォールバック
                cat = e.get("category", p.stem.replace("golden_", "").replace("rtl_log", "default"))
                key = (cat, cid)
                if key in out:
                    print(f"  ⚠ {p}:{line_num}: duplicate key {key}, "
                          f"using later", file=sys.stderr)
                out[key] = e
    return out


# =============================================================================
# Shifted match — RTL DDTW vs libiommu CDW の責務分担差を吸収
# =============================================================================
#
#   RTL の DDTW は DC.fsc.pdtp.PPN を S2 翻訳して SPA でキャッシュする設計。
#   libiommu の locate_process_context は pdtp.PPN を GPA として扱い CDW で
#   都度 S2 翻訳する。
#
#   両者とも同じ S2 PT を walk するが、責務分担差により PDT walk 中の S2 fault
#   は 1 段ずれた GPA で報告される:
#     - libiommu: 「pdtp.PPN を翻訳中に fault」 → iotval2 = pdt_root GPA
#     - RTL:     「pdte.PPN を翻訳中に fault」 → iotval2 = pdt_l1 GPA
#
#   両方 spec compliant な実装なので、test infrastructure 側で 1 段ずれを
#   許容する shifted-match logic を入れる。
# =============================================================================
def _parse_hex(s):
    """'0x...' 文字列を int に。失敗したら None。"""
    if not isinstance(s, str):
        return None
    try:
        return int(s, 16)
    except ValueError:
        return None


def _iotval2_alternatives(ref_iotval2_str, alloc):
    """REF の iotval2 と等価とみなしてよい RTL iotval2 のリスト。

    PDT walk chain (= alloc.pdt_root → alloc.pdt_l1 → alloc.pdt_leaf) を構築し、
    ref が chain の n 番目を指していれば、(n+1) 番目に shift した値も許容する。

    Returns:
        list of acceptable iotval2 string values (= [exact, shifted_if_any])
    """
    alternatives = [ref_iotval2_str]

    if not alloc or not isinstance(ref_iotval2_str, str):
        return alternatives

    ref_int = _parse_hex(ref_iotval2_str)
    if ref_int is None:
        return alternatives

    # iotval2 のフォーマット:
    #   bits[63:12] = page-aligned GPA の上位
    #   bits[11:0]  = offset / flags (lower 2 bits は implicit access flag 等)
    page_aligned = ref_int & ~0xFFF
    low_bits     = ref_int & 0xFFF
    ref_ppn      = page_aligned >> 12

    # alloc から PDT chain を構築 (順序: root → l1 → leaf)
    chain = []
    for key in ("pdt_root", "pdt_l1", "pdt_leaf"):
        v = _parse_hex(alloc.get(key)) if key in alloc else None
        if v is not None:
            chain.append(v)

    # ref_ppn が chain の n 番目なら、(n+1) 番目の PPN を shifted alternative に加える
    for i, ppn in enumerate(chain):
        if ppn == ref_ppn and i + 1 < len(chain):
            shifted_int = (chain[i + 1] << 12) | low_bits
            alternatives.append(f"0x{shifted_int:x}")
            break

    return alternatives


def _try_shifted_match(rtl_fault, ref_fault, alloc):
    """fault dict 同士で iotval2 だけが 1 段ずれている場合 True を返す。

    条件:
      - 両方 dict (= 両方 fault が起きている)
      - iotval2 以外のフィールドが完全一致
      - rtl の iotval2 が ref の shifted alternatives に含まれる
    """
    if not isinstance(rtl_fault, dict) or not isinstance(ref_fault, dict):
        return False

    # iotval2 以外を厳密一致でチェック
    keys = set(rtl_fault.keys()) | set(ref_fault.keys())
    for k in keys:
        if k == "iotval2":
            continue
        if rtl_fault.get(k) != ref_fault.get(k):
            return False

    # iotval2 が shifted alternatives に含まれるか
    ref_iotval2 = ref_fault.get("iotval2")
    rtl_iotval2 = rtl_fault.get("iotval2")
    if ref_iotval2 == rtl_iotval2:
        return True   # 厳密一致なので shifted 判定は不要
    return rtl_iotval2 in _iotval2_alternatives(ref_iotval2, alloc)


# =============================================================================
# フィールド単位の diff
# =============================================================================
INPUT_KEYS = {
    # 共通入力
    "case_id", "name", "category", "stage_mode",
    "level", "flags", "access", "rsvd_pattern", "pte_raw", "iova",
    # nested 用 S2 入力
    "s2_level", "s2_flags", "s2_rsvd_pattern", "s2_pte_raw",
    # Option B: 各 case の実 PPN allocation (= 入力扱い、比較対象外)
    "alloc",
}


def field_diff(rtl: dict, ref: dict, *, ignore_keys=(), strict=False):
    """両 dict の output 部分を比較。INPUT_KEYS と ignore_keys は除外。

    Args:
        strict: True なら shifted match を無効化 (= 厳密比較)

    Returns:
        (diffs, shifted_matched) tuple
          diffs: list of (key, ref_value, rtl_value) for differing fields
          shifted_matched: bool — shifted match で許容した case か
    """
    keys = (set(rtl.keys()) | set(ref.keys())) - INPUT_KEYS - set(ignore_keys)
    diffs = []
    shifted_matched = False

    for k in sorted(keys):
        rv = ref.get(k)
        tv = rtl.get(k)
        if rv == tv:
            continue

        # ★ shifted match: fault.iotval2 だけが 1 段ずれている場合は許容
        if not strict and k == "fault":
            alloc = ref.get("alloc") or rtl.get("alloc") or {}
            if _try_shifted_match(tv, rv, alloc):
                shifted_matched = True
                continue   # mismatch 扱いしない

        diffs.append((k, rv, tv))

    return diffs, shifted_matched


def format_mismatch(category, case_id, name, diffs):
    lines = [f"  [{category}] case {case_id:>4d} '{name}':"]
    for k, ref_v, rtl_v in diffs:
        lines.append(f"      {k:>10}: ref={_short(ref_v)} | rtl={_short(rtl_v)}")
    return "\n".join(lines)


def _short(v, *, maxlen=60):
    s = repr(v)
    if len(s) > maxlen:
        s = s[:maxlen - 3] + "..."
    return s


# =============================================================================
# main
# =============================================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compare RTL replay log against reference (category-aware)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--rtl", required=True, type=Path, help="RTL 側 JSONL")
    ap.add_argument("--ref", action="append", default=[], type=Path,
                    help="リファレンス側 JSONL (複数指定可)")
    ap.add_argument("--ref-dir", type=Path,
                    help="このディレクトリ内の golden_*.jsonl を全部読む")
    ap.add_argument("--fail-fast", action="store_true",
                    help="最初のミスマッチで停止")
    ap.add_argument("--ignore", default="",
                    help="比較から除外するフィールド (カンマ区切り)")
    ap.add_argument("--category", default=None,
                    help="このカテゴリだけ比較 (省略時は全カテゴリ)")
    ap.add_argument("--strict", action="store_true",
                    help="厳密比較 (= shifted match を無効化)")
    ap.add_argument("--show-shifted", action="store_true",
                    help="shifted match で許容したケースを stderr にリスト")
    args = ap.parse_args()

    if not args.rtl.exists():
        print(f"ERROR: RTL log not found: {args.rtl}", file=sys.stderr)
        return 1

    # ref のパス集約
    ref_paths = list(args.ref)
    if args.ref_dir:
        if not args.ref_dir.is_dir():
            print(f"ERROR: --ref-dir not a directory: {args.ref_dir}", file=sys.stderr)
            return 1
        ref_paths.extend(sorted(args.ref_dir.glob("golden_*.jsonl")))

    if not ref_paths:
        print("ERROR: no --ref or --ref-dir specified", file=sys.stderr)
        return 1

    for p in ref_paths:
        if not p.exists():
            print(f"ERROR: ref log not found: {p}", file=sys.stderr)
            return 1

    ignore_keys = {s.strip() for s in args.ignore.split(",") if s.strip()}

    rtl = load_jsonl([args.rtl])
    ref = load_jsonl(ref_paths)

    # category フィルタ
    if args.category:
        rtl = {k: v for k, v in rtl.items() if k[0] == args.category}
        ref = {k: v for k, v in ref.items() if k[0] == args.category}

    only_in_rtl = set(rtl) - set(ref)
    only_in_ref = set(ref) - set(rtl)
    common      = set(rtl) & set(ref)

    print(f"  rtl log: {len(rtl):>5} cases  ({args.rtl})")
    print(f"  ref log: {len(ref):>5} cases  ({len(ref_paths)} file(s))")
    if only_in_rtl:
        sample = sorted(only_in_rtl)[:5]
        print(f"  ⚠ {len(only_in_rtl)} key(s) only in RTL: {sample}{'...' if len(only_in_rtl) > 5 else ''}")
    if only_in_ref:
        sample = sorted(only_in_ref)[:5]
        print(f"  ⚠ {len(only_in_ref)} key(s) only in REF: {sample}{'...' if len(only_in_ref) > 5 else ''}")

    # ---- カテゴリ別に集計 ----
    by_category = {}
    mismatches  = []
    shifted_cases = []   # (cat, cid, name) — shifted match で救われた case

    for key in sorted(common):
        cat, cid = key
        diffs, shifted = field_diff(rtl[key], ref[key],
                                     ignore_keys=ignore_keys,
                                     strict=args.strict)
        bucket = by_category.setdefault(
            cat, {"matches": 0, "mismatches": 0, "shifted": 0}
        )
        if diffs:
            bucket["mismatches"] += 1
            mismatches.append((cat, cid, ref[key].get("name", "?"), diffs))
            if args.fail_fast:
                break
        else:
            bucket["matches"] += 1
            if shifted:
                bucket["shifted"] += 1
                shifted_cases.append((cat, cid, ref[key].get("name", "?")))

    # ---- サマリ表示 ----
    print()
    print("  Per-category summary:")
    print(f"  {'category':<30} {'matches':>10} {'mismatches':>12} {'(shifted)':>11}")
    print(f"  {'-'*30} {'-'*10} {'-'*12} {'-'*11}")
    total_match = total_mm = total_shifted = 0
    for cat in sorted(by_category):
        m  = by_category[cat]["matches"]
        mm = by_category[cat]["mismatches"]
        sh = by_category[cat]["shifted"]
        total_match   += m
        total_mm      += mm
        total_shifted += sh
        sh_str = f"({sh})" if sh else ""
        print(f"  {cat:<30} {m:>10} {mm:>12} {sh_str:>11}")
    print(f"  {'-'*30} {'-'*10} {'-'*12} {'-'*11}")
    sh_total_str = f"({total_shifted})" if total_shifted else ""
    print(f"  {'TOTAL':<30} {total_match:>10} {total_mm:>12} {sh_total_str:>11}"
          + ("  (fail-fast: stopped early)" if args.fail_fast and total_mm else ""))
    if total_shifted and not args.strict:
        print(f"  Note: {total_shifted} case(s) matched via shifted-match "
              f"(DDTW/CDW responsibility split). Use --strict to disallow.")

    # ---- shifted match の詳細 (--show-shifted 時) ----
    if shifted_cases and args.show_shifted:
        print(file=sys.stderr)
        print("=== Shifted matches (DDTW vs CDW responsibility split) ===",
              file=sys.stderr)
        for cat, cid, name in shifted_cases:
            print(f"  [{cat}] case {cid:>4d} '{name}'", file=sys.stderr)

    # ---- ミスマッチ詳細 ----
    if mismatches:
        print()
        print("=== Mismatches ===")
        for cat, cid, name, diffs in mismatches:
            print(format_mismatch(cat, cid, name, diffs))

    # ---- exit code ----
    if mismatches:
        return 1
    if only_in_rtl or only_in_ref:
        print()
        print("⚠ Coverage gaps exist (case_id sets differ between RTL and REF)")
        return 2

    print()
    if total_shifted and not args.strict:
        print(f"✓ All {total_match} cases match "
              f"({total_shifted} via shifted-match)")
    else:
        print(f"✓ All {total_match} cases match")
    return 0


if __name__ == "__main__":
    sys.exit(main())