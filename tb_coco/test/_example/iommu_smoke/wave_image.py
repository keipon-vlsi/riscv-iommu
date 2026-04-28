#!/usr/bin/env python3
"""
wave_image.py — VCD からテストごとの SVG 波形画像を生成

使い方:
    # 全テスト分の SVG を wave_images/ に生成
    python wave_image.py --all

    # 単一テストだけ
    python wave_image.py --test test_06 -o test_06.svg

    # 任意の時刻範囲
    python wave_image.py --time 3500-4500 --groups tr_ar,tr_r -o range.svg

依存:
    pip install vcdvcd
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# wave_snapshot.py から共通ロジックを再利用
sys.path.insert(0, str(Path(__file__).parent))
from wave_snapshot import (
    VCDVCD,
    SIGNAL_GROUPS, TEST_PRESETS, TOPLEVEL,
    parse_sim_log, find_vcd, get_timescale_to_ns,
    collect_signal_history, value_at_time, fmt_value,
)


# =============================================================================
# Layout 定数
# =============================================================================
NAME_WIDTH      = 160      # 信号名カラム幅 (px)
PLOT_WIDTH      = 1100     # 波形描画エリア幅
RIGHT_MARGIN    = 20
TOP_TITLE_H     = 35       # タイトル + 時刻軸
GROUP_GAP       = 14       # グループ間の余白
ROW_HEIGHT      = 36
SIG_HIGH_OFFSET = 8        # 行内で 1 を描く高さ (上から)
SIG_LOW_OFFSET  = 28       # 行内で 0 を描く高さ
PADDING_BOTTOM  = 16

COLOR_HIGH      = "#1a8a1a"   # 1-bit のライン
COLOR_BUS       = "#1a8a1a"
COLOR_BUS_FILL  = "#dff5df"
COLOR_X         = "#c00"
COLOR_GRID      = "#eee"
COLOR_AXIS      = "#888"
COLOR_HS_MARK   = "#e0a800"   # handshake マーカー


def compute_grid_step(duration_ns: float) -> float:
    """duration に応じて時刻グリッドの刻みを決める"""
    if duration_ns <= 200:    return 20
    if duration_ns <= 1000:   return 100
    if duration_ns <= 5000:   return 500
    if duration_ns <= 20000:  return 2000
    return 5000


# =============================================================================
# 1 グループ分の波形描画ロジック
# =============================================================================
def collect_transitions(
    vcd: VCDVCD, signal_short: str, t_start: float, t_end: float
) -> Tuple[List[Tuple[float, str]], bool]:
    """指定信号の (時刻, 値) 列を t_start..t_end の範囲で抽出。
    先頭は t_start 時点の値で初期化。
    Returns: (transitions, found?)
    """
    full = f"{TOPLEVEL}.{signal_short}"
    h = collect_signal_history(vcd, full)
    if h is None:
        return [], False

    # t_start 時点での値
    initial = value_at_time(h, t_start)
    transitions: List[Tuple[float, str]] = [(t_start, initial if initial is not None else "x")]

    for ts, v in h:
        if t_start < ts <= t_end:
            transitions.append((ts, v))

    # 末尾の値を t_end まで延長 (描画用)
    transitions.append((t_end, transitions[-1][1]))
    return transitions, True


def is_single_bit(transitions: List[Tuple[float, str]]) -> bool:
    """全値が 1-bit なら True"""
    for _, v in transitions:
        if v is None:
            continue
        v_clean = v.strip().lstrip("b")
        if v_clean.lower() in ("0", "1", "x", "z"):
            continue
        return False
    return True


def render_signal_row(
    sig: str,
    transitions: List[Tuple[float, str]],
    y_top: float,
    x_func,
) -> List[str]:
    """1 信号の波形を SVG 要素として返す"""
    elems: List[str] = []
    y_high = y_top + SIG_HIGH_OFFSET
    y_low  = y_top + SIG_LOW_OFFSET
    y_mid  = (y_high + y_low) / 2

    # 信号名
    elems.append(
        f'<text x="{NAME_WIDTH-8}" y="{y_mid+4:.1f}" font-size="11" '
        f'text-anchor="end" fill="#333">{sig}</text>'
    )

    # ベースラインの薄いガイド (1 のレベル / 0 のレベル)
    x_left = x_func(transitions[0][0])
    x_right = x_func(transitions[-1][0])
    elems.append(
        f'<line x1="{x_left:.1f}" y1="{y_low:.1f}" x2="{x_right:.1f}" y2="{y_low:.1f}" '
        f'stroke="{COLOR_GRID}" stroke-width="0.5"/>'
    )

    if is_single_bit(transitions):
        # ─── 1-bit: ステップ波形 ───
        points: List[Tuple[float, float]] = []
        for i, (t, v) in enumerate(transitions):
            xt = x_func(t)
            v_clean = v.strip().lstrip("b").lower() if v else "x"
            if v_clean == "1":
                y = y_high
            elif v_clean == "0":
                y = y_low
            else:
                y = y_mid

            if i == 0:
                points.append((xt, y))
            else:
                prev_y = points[-1][1]
                if prev_y != y:
                    points.append((xt, prev_y))
                points.append((xt, y))

        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        elems.append(
            f'<polyline points="{path}" stroke="{COLOR_HIGH}" '
            f'fill="none" stroke-width="1.5"/>'
        )
    else:
        # ─── 多 bit: バス形 ───
        for i in range(len(transitions) - 1):
            t1, v = transitions[i]
            t2, _ = transitions[i + 1]
            x1 = x_func(t1)
            x2 = x_func(t2)
            w = x2 - x1
            if w < 1:
                continue

            v_str = fmt_value(v)
            is_x = "X" in v_str.upper()
            fill = "#fcc" if is_x else COLOR_BUS_FILL
            stroke = COLOR_X if is_x else COLOR_BUS

            # バスの形 (両端を斜めにカットした六角形風)
            cut = min(4.0, w / 4)
            pts = (
                f"{x1:.1f},{y_mid:.1f} "
                f"{x1+cut:.1f},{y_high:.1f} "
                f"{x2-cut:.1f},{y_high:.1f} "
                f"{x2:.1f},{y_mid:.1f} "
                f"{x2-cut:.1f},{y_low:.1f} "
                f"{x1+cut:.1f},{y_low:.1f}"
            )
            elems.append(
                f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
            )

            # ラベル (幅が足りるときだけ)
            if w > 30:
                cx = (x1 + x2) / 2
                # 長い hex は短縮表示
                disp = v_str if len(v_str) <= 16 else v_str[:13] + "..."
                elems.append(
                    f'<text x="{cx:.1f}" y="{y_mid+4:.1f}" font-size="10" '
                    f'text-anchor="middle" fill="#222">{disp}</text>'
                )

    return elems


def detect_handshakes(
    transitions_by_sig: Dict[str, List[Tuple[float, str]]],
    sig_names: List[str],
) -> List[float]:
    """グループ内に *valid と *ready があり、両方 1 になる瞬間の時刻リスト"""
    valid_sig = next((s for s in sig_names if s.endswith("valid")), None)
    ready_sig = next((s for s in sig_names if s.endswith("ready")), None)
    if not valid_sig or not ready_sig:
        return []

    v_tr = transitions_by_sig.get(valid_sig)
    r_tr = transitions_by_sig.get(ready_sig)
    if not v_tr or not r_tr:
        return []

    # 共通の時刻点で両方を評価
    all_times = sorted({t for t, _ in v_tr} | {t for t, _ in r_tr})
    handshakes = []
    for t in all_times:
        v_val = value_at_time([(tt, vv) for tt, vv in v_tr], t)
        r_val = value_at_time([(tt, vv) for tt, vv in r_tr], t)
        if v_val == "1" and r_val == "1":
            handshakes.append(t)

    # 連続した時刻は最初の 1 個だけ残す (sticky な high の連続を圧縮)
    compressed = []
    for t in handshakes:
        if not compressed or t - compressed[-1] > 5:  # 5ns 以上空いたら別イベント
            compressed.append(t)
    return compressed


# =============================================================================
# テスト 1 つ分の SVG を構築
# =============================================================================
def render_test_svg(
    vcd: VCDVCD,
    title: str,
    t_start: float,
    t_end: float,
    groups: List[str],
) -> str:
    duration = max(t_end - t_start, 1.0)

    # 全グループの全信号について transitions を取得
    sections: List[Tuple[str, List[str], Dict[str, list], List[float]]] = []
    total_rows = 0
    for g in groups:
        signals = SIGNAL_GROUPS.get(g, [])
        if not signals:
            continue
        tr_by_sig: Dict[str, list] = {}
        valid_signals: List[str] = []
        for s in signals:
            tr, ok = collect_transitions(vcd, s, t_start, t_end)
            if not ok:
                continue
            tr_by_sig[s] = tr
            valid_signals.append(s)
        if not valid_signals:
            continue
        hs = detect_handshakes(tr_by_sig, valid_signals)
        sections.append((g, valid_signals, tr_by_sig, hs))
        total_rows += len(valid_signals)

    if not sections:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="60">' \
               f'<text x="20" y="40">No signals found for: {", ".join(groups)}</text></svg>'

    # 全体寸法
    width = NAME_WIDTH + PLOT_WIDTH + RIGHT_MARGIN
    height = (TOP_TITLE_H + total_rows * ROW_HEIGHT
              + GROUP_GAP * len(sections) + PADDING_BOTTOM)

    def x_func(t: float) -> float:
        return NAME_WIDTH + (t - t_start) / duration * PLOT_WIDTH

    elems: List[str] = []
    elems.append(f'<?xml version="1.0" encoding="UTF-8"?>')
    elems.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" font-family="ui-monospace, Menlo, monospace">'
    )
    elems.append(f'<rect width="100%" height="100%" fill="white"/>')

    # タイトルと時刻範囲
    elems.append(
        f'<text x="10" y="20" font-size="13" font-weight="bold" fill="#222">{title}</text>'
    )
    elems.append(
        f'<text x="{NAME_WIDTH}" y="20" font-size="10" fill="#666">{t_start:.0f} ns</text>'
    )
    elems.append(
        f'<text x="{width-RIGHT_MARGIN}" y="20" font-size="10" fill="#666" '
        f'text-anchor="end">{t_end:.0f} ns</text>'
    )

    # 時刻軸
    axis_y = TOP_TITLE_H - 5
    elems.append(
        f'<line x1="{NAME_WIDTH}" y1="{axis_y}" x2="{width-RIGHT_MARGIN}" '
        f'y2="{axis_y}" stroke="{COLOR_AXIS}"/>'
    )

    # グリッド (時刻目盛)
    grid_step = compute_grid_step(duration)
    g = ((t_start // grid_step) + 1) * grid_step
    while g < t_end:
        gx = x_func(g)
        elems.append(
            f'<line x1="{gx:.1f}" y1="{axis_y}" x2="{gx:.1f}" '
            f'y2="{height-PADDING_BOTTOM}" stroke="{COLOR_GRID}" stroke-width="0.5"/>'
        )
        elems.append(
            f'<text x="{gx:.1f}" y="{axis_y-3}" font-size="9" fill="#888" '
            f'text-anchor="middle">{g:.0f}</text>'
        )
        g += grid_step

    # 各グループ・信号を描画
    cur_y = TOP_TITLE_H
    for group_name, signals, tr_by_sig, handshakes in sections:
        # グループ名ヘッダ
        elems.append(
            f'<text x="6" y="{cur_y+11:.1f}" font-size="11" font-weight="bold" '
            f'fill="#666">[{group_name}]</text>'
        )
        # ハンドシェイクの縦線 + ★ マーク
        for hs_t in handshakes:
            hx = x_func(hs_t)
            elems.append(
                f'<line x1="{hx:.1f}" y1="{cur_y:.1f}" x2="{hx:.1f}" '
                f'y2="{cur_y + len(signals)*ROW_HEIGHT:.1f}" '
                f'stroke="{COLOR_HS_MARK}" stroke-width="1" stroke-dasharray="3,2" opacity="0.7"/>'
            )
            elems.append(
                f'<text x="{hx:.1f}" y="{cur_y-2:.1f}" font-size="11" '
                f'text-anchor="middle" fill="{COLOR_HS_MARK}">★</text>'
            )

        for sig in signals:
            row_elems = render_signal_row(sig, tr_by_sig[sig], cur_y, x_func)
            elems.extend(row_elems)
            cur_y += ROW_HEIGHT

        cur_y += GROUP_GAP

    elems.append('</svg>')
    return "\n".join(elems)


# =============================================================================
# main
# =============================================================================
def select_groups_for_test(test_name: str) -> List[str]:
    for key, groups in TEST_PRESETS:
        if key in test_name:
            return groups
    return ["ck"]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--vcd", default=None, help="VCD path (auto-detect if omitted)")
    p.add_argument("--log", default="sim.log", help="cocotb sim.log path")
    p.add_argument("--test", help="Test name (substring match)")
    p.add_argument("--time", help="Time range (ns), e.g. 3500-4500")
    p.add_argument("--groups", help="Signal groups (comma-separated, or 'all')")
    p.add_argument("--all", action="store_true", help="Generate SVG for all tests")
    p.add_argument("-o", "--output", default=None,
                   help="Output file (single mode) or directory (--all mode)")
    args = p.parse_args()

    vcd_path = find_vcd(args.vcd)
    if vcd_path is None:
        print("ERROR: VCD not found. Run `make sim-log` first or specify --vcd.", file=sys.stderr)
        sys.exit(1)
    print(f"Loading VCD: {vcd_path} ...", file=sys.stderr)
    vcd = VCDVCD(str(vcd_path))

    test_ranges = parse_sim_log(Path(args.log))

    if args.all:
        out_dir = Path(args.output or "wave_images")
        out_dir.mkdir(exist_ok=True)
        for name, (s, e) in test_ranges.items():
            groups = (args.groups.split(",") if args.groups and args.groups != "all"
                      else (list(SIGNAL_GROUPS.keys()) if args.groups == "all"
                            else select_groups_for_test(name)))
            svg = render_test_svg(vcd, name, s, e, groups)
            out_path = out_dir / f"{name}.svg"
            out_path.write_text(svg)
            print(f"  wrote {out_path}", file=sys.stderr)
        print(f"\nTotal: {len(test_ranges)} SVG files in {out_dir}/", file=sys.stderr)
        return

    if args.test:
        matches = [n for n in test_ranges if args.test in n]
        if not matches:
            print(f"ERROR: no test matches '{args.test}'", file=sys.stderr)
            print("Available:", list(test_ranges.keys()), file=sys.stderr)
            sys.exit(1)
        name = matches[0]
        s, e = test_ranges[name]
        groups = (args.groups.split(",") if args.groups and args.groups != "all"
                  else (list(SIGNAL_GROUPS.keys()) if args.groups == "all"
                        else select_groups_for_test(name)))
        svg = render_test_svg(vcd, name, s, e, groups)
    elif args.time:
        s_str, e_str = args.time.split("-")
        s, e = float(s_str), float(e_str)
        groups = args.groups.split(",") if args.groups else list(SIGNAL_GROUPS.keys())[:5]
        svg = render_test_svg(vcd, f"Time range {s}-{e} ns", s, e, groups)
    else:
        print("ERROR: specify --test, --time, or --all", file=sys.stderr)
        sys.exit(1)

    out_path = args.output or "wave.svg"
    Path(out_path).write_text(svg)
    print(f"Wrote: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()