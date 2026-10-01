"""市場別の表（1行＝1市場、1列＝1品目）を読む。"""
from __future__ import annotations

import re

from .geometry import DASHES, NA_WORDS, Word, group_lines, is_num, text_height, to_float

HEADER_SKIP = {"MARKET", "COMMODITY", "(PHP/KG)", "COMMODITIES"}
COLUMN_TOLERANCE = 2.2  # 同じ列とみなすx座標の差（文字の高さの倍数）
HEADER_HEIGHT = 5.3     # 最初の市場の行から上に見出しを探す範囲（文字の高さの倍数）
YEAR_RE = re.compile(r"^20\d\d,?$")


def parse_market_page(words: list[Word]) -> list[dict]:
    """全市場の行を返す。各行は market, raw_name, low, high, price。値幅のセルは中間値をpriceにする。"""
    h = text_height(words)
    lines = group_lines(words)
    data = []
    for line in lines:
        if re.fullmatch(r"\d{1,2}", line[0].text):  # 行番号
            line = line[1:]
        cells = _cells(line)
        if len(cells) < 3 or not line or is_num(line[0].text) or line[0].text in NA_WORDS:
            continue
        first_cell_x = min(c["x0"] for c in cells)
        name = " ".join(w.text for w in line if w.x1 < first_cell_x and w.text not in NA_WORDS)
        if name:
            data.append((name, line[0].top, cells))
    if not data:
        return []

    centers: list[float] = []
    for _, _, cells in data:
        for c in cells:
            if not any(abs(c["cx"] - x) < COLUMN_TOLERANCE * h for x in centers):
                centers.append(c["cx"])
    centers.sort()

    first_top = min(top for _, top, _ in data)
    # 見出しは最初の市場の行のすぐ上。日付の行（年を含む行）より上は見出しにしない
    header_top = first_top - HEADER_HEIGHT * h
    for line in lines:
        if line[0].bottom <= first_top and any(YEAR_RE.match(w.text) for w in line):
            header_top = max(header_top, max(w.bottom for w in line) - 1)
    header: dict[int, list[Word]] = {i: [] for i in range(len(centers))}
    for w in words:
        if (header_top <= w.top and w.bottom <= first_top + 1
                and w.text not in HEADER_SKIP and w.x1 > centers[0] - 5.6 * h):
            i = min(range(len(centers)), key=lambda k: abs(centers[k] - w.cx))
            header[i].append(w)
    names = {
        i: " ".join(w.text for w in sorted(ws, key=lambda w: (round(w.top / 3), w.x0)))
        for i, ws in header.items() if ws
    }

    rows = []
    for market, _, cells in data:
        for c in cells:
            i = min(range(len(centers)), key=lambda k: abs(centers[k] - c["cx"]))
            if i not in names:
                continue
            nums = c["nums"]
            rows.append({"market": market, "raw_name": names[i], "low": min(nums),
                         "high": max(nums), "price": sum(nums) / len(nums)})
    return rows


def _cells(line: list[Word]) -> list[dict]:
    """行の中の数値セル（単独の値、または「安値 - 高値」）を左から順に返す。欠測は含めない。"""
    toks = [w for w in line if is_num(w.text) or w.text in DASHES]
    cells: list[dict] = []
    i = 0
    while i < len(toks):
        w = toks[i]
        if not is_num(w.text):
            i += 1
            continue
        if (i + 2 < len(toks) and toks[i + 1].text in DASHES and is_num(toks[i + 2].text)
                and toks[i + 2].x0 - w.x1 < w.h * 3):
            hi = toks[i + 2]
            cells.append({"nums": [to_float(w.text), to_float(hi.text)], "x0": w.x0,
                          "cx": (w.x0 + hi.x1) / 2})
            i += 3
        else:
            cells.append({"nums": [to_float(w.text)], "x0": w.x0, "cx": w.cx})
            i += 1
    return cells
