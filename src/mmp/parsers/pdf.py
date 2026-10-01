"""PDF 1本を読み、ページごとに体裁を判定して行を取り出す。"""
from __future__ import annotations

import datetime as dt
import io
import logging
import re
from dataclasses import dataclass, field

from .geometry import Word, extract_words
from .market import parse_market_page
from .rowtable import parse_rowtable_page
from .summary import parse_summary_page

logging.getLogger("pdfminer").setLevel(logging.ERROR)

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_MDY = re.compile(r"([A-Za-z]{3,9})\.? (\d{1,2}), (\d{4})")
DATE_DMY = re.compile(r"(\d{1,2}) ([A-Za-z]{3,9}) (\d{4})")
SUMMARY_TITLE = re.compile(
    r"Retail Prices? (Range )?of Selected Agri-fishery Commodities (at|in) NCR Markets")


@dataclass
class Page:
    text: str
    words: list[Word]


@dataclass
class ParseResult:
    report_date: dt.date | None = None
    layouts: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)          # 首都圏の値
    market_rows: list[dict] = field(default_factory=list)   # 市場別の値（全市場）


def find_date(text: str) -> dt.date | None:
    """本文から最初に見つかった日付を返す。'November 20, 2020' と '1 June 2021' の両方に対応。"""
    best: tuple[int, dt.date] | None = None
    for rx, (mi, di, yi) in ((DATE_MDY, (0, 1, 2)), (DATE_DMY, (1, 0, 2))):
        for m in rx.finditer(text):
            g = m.groups()
            mon = MONTHS.get(g[mi][:3].lower())
            if not mon:
                continue
            try:
                d = dt.date(int(g[yi]), mon, int(g[di]))
            except ValueError:
                continue
            if best is None or m.start() < best[0]:
                best = (m.start(), d)
            break
    return best[1] if best else None


def page_layout(text: str) -> str:
    flat = " ".join(text.split())
    head = flat[:400]
    if "COMMODITY" in flat and "SPECIFICATION" in flat:
        return "rowtable"
    if "per Market" in head:
        return "market"
    if SUMMARY_TITLE.search(head):
        return "summary"
    return "skip"


def load_pages(data: bytes) -> list[Page]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return [Page(p.extract_text() or "", extract_words(p)) for p in pdf.pages]


def parse_pages(pages: list[Page]) -> ParseResult:
    res = ParseResult()
    for page in pages:
        if res.report_date is None:
            res.report_date = find_date(page.text)
        layout = page_layout(page.text)
        res.layouts.append(layout)
        if layout == "rowtable":
            res.rows.extend(parse_rowtable_page(page.words))
        elif layout == "summary":
            res.rows.extend(parse_summary_page(page.words))
        elif layout == "market":
            res.market_rows.extend(parse_market_page(page.words))
    if not res.rows and res.market_rows:
        res.rows = summarize_markets(res.market_rows)
        res.layouts.append("market_only")
    return res


def summarize_markets(market_rows: list[dict]) -> list[dict]:
    """まとめページが読めないPDF用。市場別の値から、品目ごとの平均・最安・最高を作る。"""
    by_name: dict[str, list[dict]] = {}
    for r in market_rows:
        by_name.setdefault(r["raw_name"], []).append(r)
    out = []
    for name, rs in by_name.items():
        out.append({
            "raw_name": name, "spec": "", "unit": "",
            "low": min(r["low"] for r in rs), "high": max(r["high"] for r in rs),
            "prevailing": None,
            "average": round(sum(r["price"] for r in rs) / len(rs), 2),
        })
    return out


def parse_pdf(data: bytes) -> ParseResult:
    return parse_pages(load_pages(data))
