#!/usr/bin/env python3
"""
cocotb のログから PASS/FAIL を抽出し、モジュールカードの Test Matrix を更新する。

使い方:
    python3 update_test_status.py docs/modules/<module>.md tb_coco/.../sim.log
"""

import re
import sys
from datetime import datetime
from pathlib import Path

# 1. ログから {test_func_name: PASS/FAIL} を抽出
def parse_cocotb_log(log_path):
    results = {}
    pattern_pass = re.compile(r"(test_\w+)\s+passed")
    pattern_fail = re.compile(r"(test_\w+)\s+failed")
    for line in Path(log_path).read_text().splitlines():
        if m := pattern_pass.search(line):
            results[m.group(1)] = "PASS"
        elif m := pattern_fail.search(line):
            results[m.group(1)] = "FAIL"
    return results

# 2. モジュールカードから §11.2 の T-ID → 関数名マップを読む
def parse_tid_mapping(md_path):
    # "| T01 | test_hit |" のような行を拾う
    mapping = {}
    content = Path(md_path).read_text()
    for line in content.splitlines():
        if m := re.match(r"\|\s*\*\*(T\d+)\*\*\s*\|\s*`?(test_\w+)`?\s*\|", line):
            mapping[m.group(1)] = m.group(2)
    return mapping

# 3. §9 のテーブル行 (T-ID 含む) の Status 列を書き換える
def update_matrix(md_path, results, mapping):
    today = datetime.now().strftime("%Y-%m-%d")
    status_icon = {"PASS": "✅ PASS", "FAIL": "❌ FAIL"}
    content = Path(md_path).read_text()
    new_lines = []
    for line in content.splitlines():
        # T-ID 行を検出して Last Run と Status を置換
        for tid, func in mapping.items():
            if f"**{tid}**" in line and "|" in line:
                result = results.get(func, "PENDING")
                icon = status_icon.get(result, "⏱ PENDING")
                cols = line.split("|")
                cols[-3] = f" {today} "   # Last Run
                cols[-2] = f" {icon} "     # Status
                line = "|".join(cols)
                break
        new_lines.append(line)
    Path(md_path).write_text("\n".join(new_lines))

if __name__ == "__main__":
    md, log = sys.argv[1:3]
    results = parse_cocotb_log(log)
    mapping = parse_tid_mapping(md)
    update_matrix(md, results, mapping)
    print(f"✓ {md} updated ({len(results)} test results)")