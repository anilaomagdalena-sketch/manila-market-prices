"""PDFの単語を座標つきで取り出し、数値のかたまりと行にまとめる。"""
from __future__ import annotations

import re
from dataclasses import dataclass

NUM_RE = re.compile(r"^\*{0,2}\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\*{0,2}$")
GLUED_RE = re.compile(r"^(\*{0,2}[\d,]+\.\d{2})?([-–])(\*{0,2}[\d,]+\.\d{2})?$")
DASHES = ("-", "–")
NA_WORDS = ("NOT", "AVAILABLE", "N/A", "n/a", "NONE")
FOOTNOTE_RE = re.compile(r"^[a-zᵃᵇᶜᵈᵉ*]$")


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def h(self) -> float:
        return self.bottom - self.top


def is_num(text: str) -> bool:
    return bool(NUM_RE.match(text)) and "." in text


def to_float(text: str) -> float:
    return float(text.strip("*").replace(",", ""))


def extract_words(page) -> list[Word]:
    """pdfplumberのページから単語を取り出す。'-150.00' のように貼りついた記号は分ける。"""
    out: list[Word] = []
    for w in page.extract_words(x_tolerance=1.5, y_tolerance=2):
        text = w["text"]
        m = GLUED_RE.match(text)
        if m and (m.group(1) or m.group(3)) and len(text) > 1:
            parts = [p for p in m.groups() if p]
            cw = (w["x1"] - w["x0"]) / len(text)
            x = w["x0"]
            for p in parts:
                out.append(Word(p, x, x + cw * len(p), w["top"], w["bottom"]))
                x += cw * len(p)
        else:
            out.append(Word(text, w["x0"], w["x1"], w["top"], w["bottom"]))
    return out


@dataclass
class ValueGroup:
    nums: list[Word]
    has_dash: bool
    x0: float
    x1: float
    top: float
    bottom: float

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def h(self) -> float:
        return self.bottom - self.top


def value_groups(words: list[Word], max_gap: float) -> list[ValueGroup]:
    """同じ行で隣り合う数値（と間のダッシュ）を1つのかたまりにする。

    max_gap は、かたまりの中で許す横の隙間（文字の高さの何倍か）。
    間にラベルの単語が挟まっていたら、隙間が小さくても別のかたまりにする。
    """
    labels = [w for w in words if not is_num(w.text) and w.text not in DASHES]
    toks = sorted(
        (w for w in words if is_num(w.text) or w.text in DASHES),
        key=lambda w: (round(w.cy / 3), w.x0),
    )
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in toks:
        if cur:
            p = cur[-1]
            same_line = abs(w.cy - p.cy) < p.h * 0.6
            gap = w.x0 - p.x1
            blocked = any(
                p.x1 <= lw.x0 and lw.x1 <= w.x0 and abs(lw.cy - p.cy) < p.h * 1.2
                for lw in labels
            )
            if same_line and -1 <= gap < p.h * max_gap and not blocked:
                cur.append(w)
                continue
            groups.append(cur)
        cur = [w]
    if cur:
        groups.append(cur)
    out = []
    for g in groups:
        nums = [w for w in g if is_num(w.text)]
        if not nums:
            continue
        out.append(
            ValueGroup(
                nums=nums,
                has_dash=any(w.text in DASHES for w in g),
                x0=g[0].x0,
                x1=g[-1].x1,
                top=min(w.top for w in g),
                bottom=max(w.bottom for w in g),
            )
        )
    return out


def label_words(words: list[Word]) -> list[Word]:
    """ラベルになりうる単語（数値・ダッシュ・欠測表記・脚注記号を除く）。"""
    return [
        w
        for w in words
        if not is_num(w.text)
        and w.text not in DASHES
        and w.text not in NA_WORDS
        and not FOOTNOTE_RE.match(w.text)
    ]


def label_left_of(group: ValueGroup, labels: list[Word], max_dist: float = 16.0) -> str | None:
    """数値のかたまりのすぐ左にあるラベルを返す。max_dist は文字の高さの何倍まで離れてよいか。

    ラベルは値の行の上下に2行で書かれることがあるので、縦は文字1つ分まで許す。
    いちばん近い単語から始めて、横に重なる（同じ列の）単語だけを集める。
    """
    h = group.h
    cand = [
        w
        for w in labels
        if w.x1 <= group.x0 + 2 and group.x0 - w.x1 < max_dist * h and abs(w.cy - group.cy) < h * 1.0
    ]
    if not cand:
        return None
    near = max(cand, key=lambda w: w.x1)
    cx0, cx1 = near.x0, near.x1
    picked = [near]
    rest = [w for w in cand if w is not near]
    changed = True
    while changed:
        changed = False
        for w in rest[:]:
            if w.x1 >= cx0 - h * 0.6 and w.x0 <= cx1 + h * 0.6:
                picked.append(w)
                rest.remove(w)
                cx0, cx1 = min(cx0, w.x0), max(cx1, w.x1)
                changed = True
    picked.sort(key=lambda w: (round(w.top / 3), w.x0))
    return " ".join(w.text for w in picked)


def group_lines(words: list[Word]) -> list[list[Word]]:
    """単語を行にまとめる（上から下、左から右）。"""
    lines: list[list[Word]] = []
    for w in sorted(words, key=lambda w: (w.cy, w.x0)):
        if lines:
            ref = lines[-1]
            ref_cy = sum(x.cy for x in ref) / len(ref)
            if abs(ref_cy - w.cy) < max(w.h, max(x.h for x in ref)) * 0.5:
                ref.append(w)
                continue
        lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w.x0)
    return lines


def text_height(words: list[Word]) -> float:
    """ページの本文の文字の高さ（数値の単語の中央値）。ページの縮尺に合わせた閾値に使う。"""
    hs = sorted(w.h for w in words if is_num(w.text))
    return hs[len(hs) // 2] if hs else 8.0
