from pathlib import Path

from mmp.import_own import main, read_own

XLSX = Path(__file__).parent.parent / "docs" / "reference" / "own-cartimar-prices-2020-2024.xlsx"


def pick(rows, item, date):
    hits = [r for r in rows if r["item_ja"] == item and r["date"] == date]
    assert len(hits) == 1
    return hits[0]


def test_counts_match_the_workbook():
    rows = read_own(XLSX)
    assert sum(1 for r in rows if r["sheet"] == "野菜") == 121
    assert sum(1 for r in rows if r["sheet"] == "魚介") == 6
    assert {r["market"] for r in rows} == {"Cartimar"}


def test_three_date_header_formats():
    rows = read_own(XLSX)
    assert pick(rows, "キャベツ", "2020-11-20")["price"] == 100     # シリアル値 44155
    assert pick(rows, "ジャガイモ", "2024-02-29")["price"] == 150   # datetime
    assert pick(rows, "ジャガイモ", "2024-05-23")["price"] == 120   # 文字列 '　5/23/2024'
    assert pick(rows, "ショウガ", "2024-05-23")["price"] == 240
    assert pick(rows, "カラス貝", "2020-12-22")["price"] == 150     # 魚介シートのシリアル値 44187
    assert pick(rows, "カラス貝", "2021-01-14")["price"] == 145


def test_names_are_trimmed_but_inner_spaces_kept():
    rows = read_own(XLSX)
    items = {r["item_ja"] for r in rows}
    assert "メアジ" in items and "メアジ　" not in items
    assert "ナス　ローカル" in items
    assert pick(rows, "カラス貝", "2020-12-22")["name_tl"] == "Tahong"
    assert pick(rows, "キャベツ", "2020-11-20")["name_en"] == "Cabbage"


def test_items_without_prices_produce_no_rows():
    assert not [r for r in read_own(XLSX) if r["item_ja"] == "マンゴー"]


def test_main_writes_sorted_csv(tmp_path):
    out = tmp_path / "own.csv"
    assert main([str(XLSX), "--out", str(out)]) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "date,sheet,item_ja,name_tl,name_en,price,market"
    assert len(lines) == 128
    assert lines[1].split(",")[1] == "野菜" and lines[-1].split(",")[1] == "魚介"
