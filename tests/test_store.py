import pytest

from mmp.store import DailyStore, MarketStore, UnmappedLog, fmt


@pytest.mark.parametrize("x, s", [(100.0, "100"), (82.5, "82.5"), (119.87, "119.87"),
                                  (6.0, "6"), (None, ""), (57.499999, "57.5")])
def test_fmt(x, s):
    assert fmt(x) == s


def drow(cid, **kw):
    base = {"commodity_id": cid, "spec": "", "unit": "kg", "low": None, "high": None,
            "prevailing": None, "average": None, "source_url": "https://x/a.pdf"}
    base.update(kw)
    return base


def test_replace_date_swaps_all_rows_of_that_date(tmp_path):
    st = DailyStore(tmp_path / "daily.csv")
    st.replace_date("2020-11-20", [drow("tomato", prevailing=180.0), drow("cabbage_scorpio", prevailing=100.0)])
    st.replace_date("2020-11-21", [drow("tomato", prevailing=170.0)])
    st.replace_date("2020-11-20", [drow("tomato", prevailing=175.0, source_url="https://x/rev.pdf")])
    rows = st.rows()
    assert [(r["date"], r["commodity_id"]) for r in rows] == [("2020-11-20", "tomato"), ("2020-11-21", "tomato")]
    assert rows[0]["prevailing"] == "175" and rows[0]["source_url"] == "https://x/rev.pdf"


def test_save_sorted_and_reload(tmp_path):
    p = tmp_path / "daily.csv"
    st = DailyStore(p)
    st.replace_date("2021-01-02", [drow("tomato", low=24.0, high=50.0, prevailing=40.0)])
    st.replace_date("2020-11-20", [drow("tomato", prevailing=180.0), drow("bangus", prevailing=160.0)])
    st.save()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "date,commodity_id,spec,unit,low,high,prevailing,average,source_url"
    assert [l.split(",")[:2] for l in lines[1:]] == [
        ["2020-11-20", "bangus"], ["2020-11-20", "tomato"], ["2021-01-02", "tomato"]]
    assert DailyStore(p).rows()[2]["low"] == "24"


def test_last_price_uses_representative_value(tmp_path):
    st = DailyStore(tmp_path / "d.csv")
    st.replace_date("2023-06-01", [drow("tomato", low=30.0, high=80.0)])          # 中間値 55
    st.replace_date("2023-06-02", [drow("tomato", low=40.0, high=160.0, prevailing=120.0, average=103.67)])
    assert st.last_price("tomato", before="2023-06-02") == 55.0
    assert st.last_price("tomato", before="2023-06-03") == 120.0
    assert st.last_price("tomato", before="2023-06-01") is None
    assert st.last_price("squid", before="2030-01-01") is None


def test_last_price_avoids_sorting_store_for_each_lookup(tmp_path, monkeypatch):
    st = DailyStore(tmp_path / "d.csv")
    st.replace_date("2026-01-01", [drow("tomato", prevailing=100.0)])

    def unexpected_sort():
        raise AssertionError("last_price sorted the full store")

    monkeypatch.setattr(st, "rows", unexpected_sort)
    assert st.last_price("tomato", before="2026-01-02") == 100.0
    st.replace_date("2026-01-01", [drow("tomato", prevailing=120.0)])
    assert st.last_price("tomato", before="2026-01-02") == 120.0


def test_market_store_sorted(tmp_path):
    p = tmp_path / "m.csv"
    st = MarketStore(p)
    st.replace_date("2026-08-28", [
        {"market": "Cartimar", "commodity_id": "tomato", "low": 110.0, "high": 110.0, "price": 110.0, "source_url": "u"},
        {"market": "Cartimar", "commodity_id": "bangus", "low": 250.0, "high": 250.0, "price": 250.0, "source_url": "u"}])
    st.save()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "date,market,commodity_id,low,high,price,source_url"
    assert lines[1] == "2026-08-28,Cartimar,bangus,250,250,250,u"


def test_unmapped_log_counts_and_dates(tmp_path):
    p = tmp_path / "u.csv"
    log = UnmappedLog(p)
    log.add("Pompano, Local", "2026-02-23", "https://x/1.pdf")
    log.add("Pompano, Local", "2025-06-01", "https://x/2.pdf")
    log.add("Special", "2020-11-20", "https://x/3.pdf")
    log.save()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "raw_name,first_date,last_date,count,example_url"
    assert lines[1] == '"Pompano, Local",2025-06-01,2026-02-23,2,https://x/1.pdf'
    again = UnmappedLog(p)
    again.add("Special", "2020-11-21", "https://x/4.pdf")
    again.save()
    assert "Special,2020-11-20,2020-11-21,2,https://x/3.pdf" in p.read_text(encoding="utf-8")
