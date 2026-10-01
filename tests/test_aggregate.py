import pytest

from mmp.aggregate import aggregate, representative, week_start


@pytest.mark.parametrize("date, monday", [
    ("2020-11-20", "2020-11-16"),   # 金曜
    ("2020-11-16", "2020-11-16"),   # 月曜
    ("2020-11-22", "2020-11-16"),   # 日曜
    ("2020-12-31", "2020-12-28"),   # 年またぎ
    ("2021-01-03", "2020-12-28"),
    ("2024-02-29", "2024-02-26"),   # うるう日
])
def test_week_start(date, monday):
    assert week_start(date) == monday


def d(date, cid="tomato", low="", high="", prevailing="", average=""):
    return {"date": date, "commodity_id": cid, "spec": "", "unit": "kg", "low": low, "high": high,
            "prevailing": prevailing, "average": average, "source_url": "u"}


def test_representative_priority():
    assert representative(d("2026-08-28", low="40", high="160", prevailing="120", average="103.67")) == (120.0, "prevailing")
    assert representative(d("2025-02-01", low="50", high="130", average="93.58")) == (93.58, "average")
    assert representative(d("2023-06-01", low="30", high="80")) == (55.0, "midpoint")
    assert representative(d("2023-06-01", low="30")) is None
    assert representative(d("2023-06-01")) is None


def test_weekly_mean_and_range():
    rows = aggregate([
        d("2020-11-16", low="140", high="200", prevailing="180"),
        d("2020-11-18", low="120", high="190", prevailing="160"),
        d("2020-11-20", low="130", high="210", prevailing="170"),
        d("2020-11-23", low="100", high="150", prevailing="120"),
    ], [])
    assert rows == [
        {"week_start": "2020-11-16", "series": "ncr", "commodity_id": "tomato", "price": 170.0,
         "low": 120.0, "high": 210.0, "basis": "prevailing", "n_days": 3},
        {"week_start": "2020-11-23", "series": "ncr", "commodity_id": "tomato", "price": 120.0,
         "low": 100.0, "high": 150.0, "basis": "prevailing", "n_days": 1},
    ]


def test_basis_is_majority_and_range_may_be_missing():
    rows = aggregate([
        d("2023-06-05", low="30", high="80"),
        d("2023-06-06", low="40", high="80"),
        d("2023-06-07", prevailing="70"),
    ], [])
    assert rows[0]["basis"] == "midpoint" and rows[0]["price"] == 61.67 and rows[0]["n_days"] == 3
    rows = aggregate([d("2022-06-01", prevailing="80"), d("2022-06-02", prevailing="90")], [])
    assert rows[0]["low"] is None and rows[0]["high"] is None and rows[0]["price"] == 85.0


def test_basis_tie_prefers_prevailing():
    rows = aggregate([d("2023-06-05", low="30", high="80"), d("2023-06-06", prevailing="70")], [])
    assert rows[0]["basis"] == "prevailing"


def test_rows_without_any_value_are_ignored():
    assert aggregate([d("2023-06-05")], []) == []


def test_cartimar_series():
    m = lambda date, price, low, high: {"date": date, "market": "Cartimar", "commodity_id": "tilapia",
                                         "low": low, "high": high, "price": price, "source_url": "u"}
    rows = aggregate([], [m("2024-06-03", "155", "150", "160"), m("2024-06-05", "180", "180", "180")])
    assert rows == [{"week_start": "2024-06-03", "series": "cartimar", "commodity_id": "tilapia",
                     "price": 167.5, "low": 150.0, "high": 180.0, "basis": "market", "n_days": 2}]


def test_output_order_is_series_commodity_week():
    rows = aggregate([d("2021-01-04", cid="tomato", prevailing="1"), d("2020-11-16", cid="tomato", prevailing="1"),
                      d("2020-11-16", cid="bangus", prevailing="1")], [])
    assert [(r["commodity_id"], r["week_start"]) for r in rows] == [
        ("bangus", "2020-11-16"), ("tomato", "2020-11-16"), ("tomato", "2021-01-04")]
