#!/usr/bin/env python3
"""
wave_snapshot.py — VCD から指定テストの主要 AXI 信号変化を markdown table で抽出

使い方:
    # テスト一覧表示
    python wave_snapshot.py --list-tests

    # 信号グループ一覧表示
    python wave_snapshot.py --list-groups

    # test_06 のプリセット (推奨グループ) で出力
    python wave_snapshot.py --test test_06

    # 明示的にグループ指定
    python wave_snapshot.py --test test_06 --groups tr_ar,tr_r,comp_ar,comp_r

    # 全テストを 1 ファイルにまとめて出力
    python wave_snapshot.py --all -o report.md

    # 時刻範囲を直接指定 (test 名と関係なく)
    python wave_snapshot.py --time 3500-4500 --groups tr_ar,comp_ar

依存:
    pip install vcdvcd
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, TextIO

try:
    from vcdvcd import VCDVCD
except ImportError:
    print("ERROR: vcdvcd not installed. Run: pip install vcdvcd", file=sys.stderr)
    sys.exit(1)


# =============================================================================
# 設定: ラッパのトップ階層名と信号グループ
# =============================================================================
TOPLEVEL = "tb_riscv_iommu_wrapper"

# 信号グループ: name → [short signal names...]
SIGNAL_GROUPS: Dict[str, List[str]] = {
    # Clock & reset
    "ck":        ["clk_i", "rst_ni"],

    # prog interface (Slave AXI: register access)
    "prog_aw":   ["prog_awvalid", "prog_awready", "prog_awaddr"],
    "prog_w":    ["prog_wvalid",  "prog_wready",  "prog_wdata", "prog_wstrb"],
    "prog_b":    ["prog_bvalid",  "prog_bready",  "prog_bresp"],
    "prog_ar":   ["prog_arvalid", "prog_arready", "prog_araddr"],
    "prog_r":    ["prog_rvalid",  "prog_rready",  "prog_rdata", "prog_rresp"],

    # dev_tr interface (Slave AXI + DVM)
    "tr_aw":     ["tr_awvalid", "tr_awready", "tr_awaddr"],
    "tr_w":      ["tr_wvalid",  "tr_wready",  "tr_wdata"],
    "tr_b":      ["tr_bvalid",  "tr_bready",  "tr_bresp"],
    "tr_ar":     ["tr_arvalid", "tr_arready", "tr_araddr"],
    "tr_r":      ["tr_rvalid",  "tr_rready",  "tr_rdata", "tr_rresp"],
    "tr_dvm":    ["tr_aw_stream_id", "tr_aw_ss_id_valid", "tr_aw_substream_id",
                  "tr_ar_stream_id", "tr_ar_ss_id_valid", "tr_ar_substream_id"],

    # dev_comp interface (Master AXI)
    "comp_aw":   ["comp_awvalid", "comp_awready", "comp_awaddr"],
    "comp_w":    ["comp_wvalid",  "comp_wready",  "comp_wdata"],
    "comp_b":    ["comp_bvalid",  "comp_bready",  "comp_bresp"],
    "comp_ar":   ["comp_arvalid", "comp_arready", "comp_araddr"],
    "comp_r":    ["comp_rvalid",  "comp_rready",  "comp_rdata", "comp_rresp"],

    # その他
    "wsi":       ["wsi_wires_o"],
}

# テスト名の部分一致で「推奨グループ」を選ぶ
TEST_PRESETS: List[Tuple[str, List[str]]] = [
    ("test_01_reset_only",                  ["ck", "wsi"]),
    ("test_02_read_capabilities",           ["prog_ar", "prog_r"]),
    ("test_03_write_read_fctl",             ["prog_aw", "prog_w", "prog_b", "prog_ar", "prog_r"]),
    ("test_04_register_dump",               ["prog_ar", "prog_r"]),
    ("test_05_configure_bare_mode",         ["prog_aw", "prog_w", "prog_b", "prog_ar", "prog_r"]),
    ("test_06_bare_mode_passthrough",       ["tr_ar", "tr_r", "comp_ar", "comp_r"]),
    ("test_07_bare_mode_write_passthrough", ["tr_aw", "tr_w", "tr_b", "comp_aw", "comp_w", "comp_b"]),
]


# =============================================================================
# sim.log パース: テスト名 → (start_ns, end_ns)
# =============================================================================
def parse_sim_log(log_path: Path) -> Dict[str, Tuple[float, float]]:
    test_ranges: Dict[str, Tuple[float, float]] = {}
    if not log_path.exists():
        print(f"WARNING: {log_path} not found", file=sys.stderr)
        return test_ranges

    log_text = log_path.read_text(errors="replace")
    current_test: Optional[str] = None
    start_time: Optional[float] = None
    last_time = 0.0

    time_re = re.compile(r"^\s*([0-9.]+)\s*ns")
    run_re = re.compile(r"running\s+\S+?(test_\S+)")
    done_re = re.compile(r"\S+?(test_\S+)\s+(passed|failed)")

    for line in log_text.splitlines():
        m_t = time_re.search(line)
        if m_t:
            last_time = float(m_t.group(1))

        m_r = run_re.search(line)
        if m_r and m_t:
            t = float(m_t.group(1))
            name = m_r.group(1)
            if current_test:
                test_ranges[current_test] = (start_time or 0.0, t)
            current_test = name
            start_time = t
            continue

        m_d = done_re.search(line)
        if m_d and m_t:
            t = float(m_t.group(1))
            name = m_d.group(1)
            if current_test == name:
                test_ranges[current_test] = (start_time or 0.0, t)
                current_test = None
                start_time = None

    if current_test and start_time is not None:
        test_ranges[current_test] = (start_time, last_time)

    return test_ranges


# =============================================================================
# VCD 読み出し
# =============================================================================
def get_timescale_to_ns(vcd: VCDVCD) -> float:
    """VCD の timescale を ns 換算の係数として返す"""
    ts = vcd.timescale
    # vcdvcd は magnitude を Decimal で返してくる場合があるので float に正規化
    mag = float(ts.get("magnitude", 1))
    unit = ts.get("unit", "ns")
    table = {"s": 1e9, "ms": 1e6, "us": 1e3, "ns": 1.0, "ps": 1e-3, "fs": 1e-6}
    return mag * table.get(unit, 1.0)


def fmt_value(val: str) -> str:
    """生の VCD 値を読みやすく整形"""
    if val is None:
        return "-"
    val = val.strip().lstrip("b")  # 多ビット値は 'b' で始まる
    if not val:
        return "-"
    if "x" in val.lower():
        return "X"
    if "z" in val.lower():
        return "Z"
    if all(c in "01" for c in val):
        if len(val) == 1:
            return val
        try:
            iv = int(val, 2)
            hexw = (len(val) + 3) // 4
            return f"0x{iv:0{hexw}x}"
        except ValueError:
            return val
    return val


def collect_signal_history(
    vcd: VCDVCD, full_name: str
) -> Optional[List[Tuple[float, str]]]:
    """信号の (時刻ns, 値) リストを返す。見つからなければ None。"""
    if full_name not in vcd.references_to_ids:
        return None
    sig_id = vcd.references_to_ids[full_name]
    tv = vcd.data[sig_id].tv  # [(ts_int, val_str), ...]
    scale = get_timescale_to_ns(vcd)
    return [(ts * scale, val) for ts, val in tv]


def value_at_time(history: List[Tuple[float, str]], t: float) -> Optional[str]:
    """指定時刻時点での値 (それ以前の最後の変化点)"""
    if history is None:
        return None
    last_val = None
    for ts, v in history:
        if ts <= t:
            last_val = v
        else:
            break
    return last_val


# =============================================================================
# タイムライン構築
# =============================================================================
def build_timeline(
    vcd: VCDVCD,
    signal_short_names: List[str],
    t_start: float,
    t_end: float,
) -> Tuple[List[Tuple[float, Dict[str, str]]], Dict[str, bool]]:
    """信号群について、変化があった時刻だけ抽出してテーブル化
    Returns:
      timeline: [(time, {short_name: value}), ...]
      missing:  {short_name: True/False}  # VCD に見つからなかった信号フラグ
    """
    histories: Dict[str, Optional[List[Tuple[float, str]]]] = {}
    missing: Dict[str, bool] = {}

    for short in signal_short_names:
        full = f"{TOPLEVEL}.{short}"
        h = collect_signal_history(vcd, full)
        histories[short] = h
        missing[short] = h is None

    # 範囲内の変化時刻を集める
    change_times = {t_start}
    for short, h in histories.items():
        if h is None:
            continue
        for ts, _ in h:
            if t_start <= ts <= t_end:
                change_times.add(ts)

    sorted_times = sorted(change_times)

    timeline = []
    for t in sorted_times:
        row = {}
        for short in signal_short_names:
            v = value_at_time(histories[short], t)
            row[short] = fmt_value(v)
        timeline.append((t, row))

    # 連続する同一行を圧縮 (=変化があった行だけ残す)
    compressed = []
    prev_row = None
    for t, row in timeline:
        if row != prev_row:
            compressed.append((t, row))
            prev_row = row

    return compressed, missing


# =============================================================================
# ハンドシェイク検出 (valid & ready が両方 1 の行)
# =============================================================================
def handshake_marker(row: Dict[str, str], group: str) -> str:
    """グループ内に valid と ready があり、両方 1 のとき "← handshake" を返す"""
    valid_sig = ready_sig = None
    for k in row:
        if k.endswith("valid"):
            valid_sig = k
        elif k.endswith("ready"):
            ready_sig = k
    if valid_sig and ready_sig:
        if row.get(valid_sig) == "1" and row.get(ready_sig) == "1":
            return " ← handshake"
    return ""


# =============================================================================
# Markdown 出力
# =============================================================================
def emit_group_table(
    out: TextIO,
    group_name: str,
    signals: List[str],
    timeline,
    missing,
):
    print(f"\n### {group_name}", file=out)

    # 行が無いか全部欠損なら警告だけ出す
    available = [s for s in signals if not missing.get(s)]
    if not available:
        print(f"_(no signals found in VCD: {', '.join(signals)})_\n", file=out)
        return

    if missing and any(missing.get(s) for s in signals):
        m = [s for s in signals if missing.get(s)]
        print(f"_(skipped: {', '.join(m)} not found in VCD)_\n", file=out)

    if not timeline:
        print("_(no changes in this time range)_\n", file=out)
        return

    headers = ["Time(ns)"] + available + [""]
    widths = [len(h) for h in headers]

    rows = []
    for t, row in timeline:
        sub = {s: row[s] for s in available}
        marker = handshake_marker(sub, group_name)
        r = [f"{t:.1f}"] + [sub[s] for s in available] + [marker]
        rows.append(r)
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(c))

    sep = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    hline = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    print(hline, file=out)
    print(sep, file=out)
    for r in rows:
        print("| " + " | ".join(c.ljust(w) for c, w in zip(r, widths)) + " |", file=out)


# =============================================================================
# 1 区間の処理
# =============================================================================
def report_range(
    out: TextIO,
    vcd: VCDVCD,
    title: str,
    t_start: float,
    t_end: float,
    groups: List[str],
):
    print(f"\n## {title}", file=out)
    print(f"_Time range: {t_start:.0f} ns – {t_end:.0f} ns_\n", file=out)

    for g in groups:
        signals = SIGNAL_GROUPS.get(g)
        if signals is None:
            print(f"_(unknown group: {g})_", file=out)
            continue
        timeline, missing = build_timeline(vcd, signals, t_start, t_end)
        emit_group_table(out, g, signals, timeline, missing)


# =============================================================================
# main
# =============================================================================
def select_groups_for_test(test_name: str) -> List[str]:
    for key, groups in TEST_PRESETS:
        if key in test_name:
            return groups
    return ["ck"]


def find_vcd(explicit_path: Optional[str] = None) -> Optional[Path]:
    """VCD ファイルを自動検索。Verilator は cwd 次第で出力先が変わるので
    複数の典型的な場所を当たる。"""
    if explicit_path:
        p = Path(explicit_path)
        if p.exists():
            return p
        # 明示指定だが存在しない場合も None で返して呼び出し側に判断させる
        return None

    candidates = [
        Path("dump.vcd"),
        Path("sim_build/dump.vcd"),
        Path("dump.fst"),
        Path("sim_build/dump.fst"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--vcd", default=None,
                   help="VCD file path (auto-detect: dump.vcd or sim_build/dump.vcd)")
    p.add_argument("--log", default="sim.log", help="cocotb sim.log path")
    p.add_argument("--test", help="Test name (substring match)")
    p.add_argument("--time", help="Time range (ns), e.g. 3500-4500")
    p.add_argument("--groups", help="Signal groups (comma-separated, or 'all')")
    p.add_argument("--all", action="store_true",
                   help="Process all tests in sim.log")
    p.add_argument("--list-tests", action="store_true")
    p.add_argument("--list-groups", action="store_true")
    p.add_argument("-o", "--output", default=None, help="Output file (default stdout)")
    args = p.parse_args()

    if args.list_groups:
        print("Available signal groups:")
        for name, sigs in SIGNAL_GROUPS.items():
            print(f"  {name:10s}: {', '.join(sigs)}")
        return

    log_path = Path(args.log)
    test_ranges = parse_sim_log(log_path)

    if args.list_tests:
        print(f"Tests detected in {log_path}:")
        for name, (s, e) in test_ranges.items():
            print(f"  {name:50s} {s:8.0f} - {e:8.0f} ns")
        return

    # VCD ロード (重い)
    vcd_path = find_vcd(args.vcd)
    if vcd_path is None:
        if args.vcd:
            print(f"ERROR: VCD file not found at specified path: {args.vcd}", file=sys.stderr)
        else:
            print("ERROR: VCD file not found in any of:", file=sys.stderr)
            print("  dump.vcd, sim_build/dump.vcd, dump.fst, sim_build/dump.fst", file=sys.stderr)
            print("Run `make sim-log` first, or specify --vcd <path>", file=sys.stderr)
        sys.exit(1)
    print(f"Loading VCD: {vcd_path} ...", file=sys.stderr)
    vcd = VCDVCD(str(vcd_path))

    out = open(args.output, "w") if args.output else sys.stdout
    print(f"# Wave snapshot ({vcd_path})", file=out)

    # ----- ターゲット決定 -----
    if args.all:
        # 全テストをループ
        for name, (s, e) in test_ranges.items():
            groups = (args.groups.split(",") if args.groups and args.groups != "all"
                      else (list(SIGNAL_GROUPS.keys()) if args.groups == "all"
                            else select_groups_for_test(name)))
            report_range(out, vcd, name, s, e, groups)
    elif args.test:
        matches = [n for n in test_ranges if args.test in n]
        if not matches:
            print(f"ERROR: no test matches '{args.test}'", file=sys.stderr)
            print("Available:", list(test_ranges.keys()), file=sys.stderr)
            sys.exit(1)
        if len(matches) > 1:
            print(f"WARNING: multiple matches ({matches}), using first", file=sys.stderr)
        name = matches[0]
        s, e = test_ranges[name]
        groups = (args.groups.split(",") if args.groups and args.groups != "all"
                  else (list(SIGNAL_GROUPS.keys()) if args.groups == "all"
                        else select_groups_for_test(name)))
        report_range(out, vcd, name, s, e, groups)
    elif args.time:
        s_str, e_str = args.time.split("-")
        s, e = float(s_str), float(e_str)
        groups = args.groups.split(",") if args.groups else list(SIGNAL_GROUPS.keys())[:5]
        report_range(out, vcd, f"Time range {s}-{e} ns", s, e, groups)
    else:
        print("ERROR: specify --test, --time, --all, or --list-tests", file=sys.stderr)
        sys.exit(1)

    if args.output:
        out.close()
        print(f"Wrote: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()