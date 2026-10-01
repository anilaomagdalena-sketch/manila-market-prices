"""実物のPDFから作った見本（tests/fixtures/*.json）で、読み取り結果を突き合わせる。

期待値は、PDFを目で読んだ値（pdftotextの出力で二重に確認）である。
"""
import datetime as dt
import json
from pathlib import Path

import pytest

from mmp.parsers.geometry import Word
from mmp.parsers.pdf import Page, parse_pages

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    raw = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    pages = [Page(p["text"], [Word(*w) for w in p["words"]]) for p in raw["pages"]]
    return parse_pages(pages)


def row(result, raw_name: str) -> dict:
    hits = [r for r in result.rows if r["raw_name"] == raw_name]
    assert len(hits) == 1, f"{raw_name}: {len(hits)} rows"
    return hits[0]


def market(result, market_prefix: str, raw_name: str) -> dict:
    hits = [r for r in result.market_rows
            if r["market"].startswith(market_prefix) and r["raw_name"] == raw_name]
    assert len(hits) == 1, f"{market_prefix}/{raw_name}: {len(hits)} rows"
    return hits[0]


def values(r: dict) -> tuple:
    return (r["low"], r["high"], r["prevailing"], r["average"])


def test_2020_row_table():
    res = load("pm_2020-11-20")
    assert res.report_date == dt.date(2020, 11, 20)
    assert res.layouts == ["rowtable", "skip"]
    assert values(row(res, "Cabbage (Scorpio)")) == (90.0, 150.0, 100.0, None)
    assert values(row(res, "Tomato")) == (140.0, 200.0, 180.0, None)
    assert values(row(res, "Bangus")) == (120.0, 220.0, 160.0, None)
    assert row(res, "Tomato")["spec"] == "15-18 pcs/kg"
    assert row(res, "Tomato")["unit"] == "kg"
    assert not [r for r in res.rows if r["raw_name"] == "White Onion"]  # NOT AVAILABLE


def test_2021_row_table():
    res = load("pm_2021-06-01")
    assert res.report_date == dt.date(2021, 6, 1)
    assert values(row(res, "Tomato")) == (24.0, 50.0, 40.0, None)
    assert values(row(res, "Bangus")) == (130.0, 220.0, 150.0, None)
    assert values(row(res, "White Onion")) == (60.0, 80.0, 80.0, None)


def test_2021_infographic_today_yesterday():
    res = load("pm_2021-09-01")
    assert res.report_date == dt.date(2021, 9, 1)
    assert values(row(res, "Milkfish Bangus")) == (None, None, 160.0, None)
    assert values(row(res, "Tomato Kamatis")) == (None, None, 80.0, None)
    assert values(row(res, "Chayote Sayote")) == (None, None, 100.0, None)  # トマトの左隣の列


def test_2021_market_only_falls_back_to_market_average():
    res = load("pm_2021-11-02")
    assert res.report_date == dt.date(2021, 11, 2)
    assert res.layouts[-1] == "market_only"
    assert len({r["market"] for r in res.market_rows}) == 12
    assert values(row(res, "Tomato (Kamatis)")) == (50.0, 65.0, None, 57.5)
    assert market(res, "Pasay", "Tomato (Kamatis)")["price"] == 60.0
    # Pasay の Cabbage は N/A。隣の列の値を拾っていないこと
    assert not [r for r in res.market_rows
                if r["market"].startswith("Pasay") and "Cabbage" in r["raw_name"]]


def test_2022_infographic_today_yesterday():
    res = load("pm_2022-06-01")
    assert res.report_date == dt.date(2022, 6, 1)
    assert values(row(res, "Cabbage Repolyo")) == (None, None, 80.0, None)   # 昨日は70
    assert values(row(res, "Squash Kalabasa")) == (None, None, 50.0, None)   # 昨日は40
    assert values(row(res, "Local Garlic Bawang")) == (None, None, 275.0, None)
    assert not [r for r in res.rows if r["raw_name"].startswith("Imported Red")]  # NOT AVAILABLE


def test_2023_infographic_range_only():
    res = load("pm_2023-06-01")
    assert res.report_date == dt.date(2023, 6, 1)
    assert values(row(res, "Cabbage Repolyo")) == (60.0, 90.0, None, None)
    assert values(row(res, "Tomato Kamatis")) == (30.0, 80.0, None, None)
    assert values(row(res, "Imported Garlic Bawang")) == (100.0, 150.0, None, None)  # '-150.00' と貼りついている
    assert values(row(res, "Imported Round Scad Galunggong")) == (180.0, 200.0, None, None)  # 脚注 a が間にある
    assert not [r for r in res.market_rows if r["market"].startswith("Cartimar")]


def test_2024_infographic_and_cartimar_ranges():
    res = load("pm_2024-06-01")
    assert res.report_date == dt.date(2024, 6, 1)
    assert values(row(res, "Scorpio")) == (50.0, 100.0, None, None)
    assert values(row(res, "Rare Ball")) == (60.0, 90.0, None, None)
    assert values(row(res, "Tomato")) == (55.0, 90.0, None, None)
    assert values(row(res, "Imported Round Scad Galunggong")) == (None, None, 260.0, None)  # 値が1つだけ
    tilapia = market(res, "Cartimar", "Tilapia")
    assert (tilapia["low"], tilapia["high"], tilapia["price"]) == (150.0, 160.0, 155.0)
    assert market(res, "Cartimar", "Cabbage (Scorpio)")["price"] == 50.0
    assert market(res, "Cartimar", "Tomato")["price"] == 82.5
    # 見出しに日付の行（June 2024）が混ざらないこと
    assert not [r for r in res.market_rows if "2024" in r["raw_name"]]


def test_2025_header_table_four_values():
    res = load("pm_2025-06-02")
    assert res.report_date == dt.date(2025, 6, 2)
    assert values(row(res, "Milkfish (Bangus)")) == (140.0, 250.0, 210.0, 200.56)
    assert values(row(res, "Squid (Pusit Bisaya)")) == (380.0, 450.0, 400.0, 412.73)
    assert values(row(res, "Tomato (Kamatis)")) == (30.0, 90.0, 60.0, 67.02)
    assert values(row(res, "Cabbage Repolyo (Wonder Ball)")) == (70.0, 120.0, 100.0, 92.93)


def test_2026_header_table_and_cartimar():
    res = load("pm_2026-08-28")
    assert res.report_date == dt.date(2026, 8, 28)
    assert values(row(res, "Squid (Pusit Bisaya)")) == (360.0, 560.0, 480.0, 463.6)
    assert values(row(res, "Cabbage Repolyo (Rare Ball)")) == (60.0, 160.0, 120.0, 119.87)
    expected = {"Bangus": 250.0, "Tilapia": 180.0, "Galunggong (Local)": 380.0, "Ampalaya": 200.0,
                "Eggplant": 220.0, "Tomato": 110.0, "Cabbage": 100.0, "Carrots (Local)": 140.0,
                "Chayote": 70.0, "Pechay Baguio": 120.0, "White Potato (Local)": 130.0,
                "Red Onion (Local)": 120.0, "White Onion (Local)": 180.0}
    for name, price in expected.items():
        assert market(res, "Cartimar", name)["price"] == price, name


def test_daily_price_index():
    res = load("dpi_2026-02-23")
    assert res.report_date == dt.date(2026, 2, 23)
    assert set(res.layouts) == {"rowtable"}
    assert values(row(res, "Tomato")) == (None, None, 64.38, None)
    assert values(row(res, "Cabbage (Scorpio)")) == (None, None, 87.2, None)
    assert row(res, "Bangus, Medium")["spec"] == "Medium (3-4 pcs/kg)"


def test_image_only_pdf_yields_nothing():
    res = load("pm_2025-05-01_image_only")
    assert res.rows == [] and res.market_rows == [] and res.report_date is None
