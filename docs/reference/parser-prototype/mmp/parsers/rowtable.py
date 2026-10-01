"""素直な行の表（2020〜2021年のPrice Monitoring 1ページ目と、Daily Price Index）を読む。"""
from __future__ import annotations

import re

from .geometry import NA_WORDS, Word, group_lines, is_num, to_float

UNITS = {"kg", "pc", "pc.", "pcs", "ml", "L", "l", "bottle"}
FIELD_HEADERS = {"High": "high", "Low": "low", "Prevailing": "prevailing"}


def parse_rowtable_page(words: list[Word]) -> list[dict]:
    lines = group_lines(words)
    heads = [w for line in lines for w in line if w.text in FIELD_HEADERS]
    rows = []
    for line in lines:
        nums = []
        while line and is_num(line[-1].text):
            nums.insert(0, line.pop())
        if not nums or not line:
            continue
        if re.fullmatch(r"\d{1,3}", line[0].text):  # 行番号
            line = line[1:]
        if not line or line[0].text in NA_WORDS:
            continue
        unit = ""
        if line[-1].text in UNITS:
            unit = line.pop().text
        if not line:
            continue
        # 品目名と規格は、最初の大きな隙間で分ける
        cut = len(line)
        for i in range(1, len(line)):
            if line[i].x0 - line[i - 1].x1 > line[i].h * 1.2:
                cut = i
                break
        name = " ".join(w.text for w in line[:cut])
        spec = " ".join(w.text for w in line[cut:])
        row = {"raw_name": name, "spec": spec, "unit": unit, "low": None, "high": None,
               "prevailing": None, "average": None}
        if len(heads) >= 3 and len(nums) == 3:
            for n in nums:
                head = min(heads, key=lambda h: abs(h.cx - n.cx))
                row[FIELD_HEADERS[head.text]] = to_float(n.text)
        elif len(nums) == 1:
            row["prevailing"] = to_float(nums[0].text)
        else:
            continue
        rows.append(row)
    return rows
