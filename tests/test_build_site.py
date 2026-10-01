from mmp.build_site import build

COMMODITIES = [
    {"commodity_id": "tomato", "category": "vegetable", "name_ja": "トマト", "name_tl": "Kamatis",
     "name_en": "Tomato", "aliases": "Tomato", "own_items": "トマトローカル", "display": "1", "order": "30"},
    {"commodity_id": "cabbage", "category": "vegetable", "name_ja": "キャベツ", "name_tl": "Repolyo",
     "name_en": "Cabbage", "aliases": "Cabbage", "own_items": "キャベツ", "display": "1", "order": "100"},
    {"commodity_id": "cabbage_scorpio", "category": "vegetable", "name_ja": "キャベツ（スコーピオ種）",
     "name_tl": "Repolyo", "name_en": "Cabbage (Scorpio)", "aliases": "Scorpio", "own_items": "キャベツ",
     "display": "1", "order": "101"},
    {"commodity_id": "bangus_large", "category": "fish", "name_ja": "バンゴス（大）", "name_tl": "Bangus",
     "name_en": "Milkfish (large)", "aliases": "x", "own_items": "", "display": "0", "order": "501"},
    {"commodity_id": "celery", "category": "vegetable", "name_ja": "セロリ", "name_tl": "",
     "name_en": "Celery", "aliases": "Celery", "own_items": "セロリ", "display": "1", "order": "190"},
    {"commodity_id": "melon", "category": "fruit", "name_ja": "メロン", "name_tl": "Melon",
     "name_en": "Melon", "aliases": "Melon", "own_items": "", "display": "1", "order": "450"},
]


def w(week, cid, price, series="ncr", low="", high="", basis="prevailing"):
    return {"week_start": week, "series": series, "commodity_id": cid, "price": price,
            "low": low, "high": high, "basis": basis, "n_days": "3"}


def o(date, item, price, sheet="野菜", tl="", en=""):
    return {"date": date, "sheet": sheet, "item_ja": item, "name_tl": tl, "name_en": en,
            "price": price, "market": "Cartimar"}


WEEKLY = [
    w("2020-11-16", "tomato", "170", low="120", high="210"),
    w("2022-06-06", "tomato", "80"),
    w("2024-06-03", "tomato", "82.5", series="cartimar", basis="market"),
    w("2020-11-16", "cabbage_scorpio", "100"),
    w("2025-06-02", "bangus_large", "219.44"),
]
OWN = [
    o("2020-11-20", "キャベツ", "100", en="Cabbage", tl="Repolyo"),
    o("2021-01-29", "トマトローカル", "100"),
    o("2024-05-23", "セロリ", "120"),
    o("2021-01-21", "パセリ", "400"),
    o("2020-12-22", "カラス貝", "150", sheet="魚介", tl="Tahong"),
]


def build_default():
    return build(WEEKLY, OWN, COMMODITIES, updated="2026-10-05", latest_report="2026-10-02")


def item(data, item_id):
    return next(i for i in data["items"] if i["id"] == item_id)


def test_header_and_categories():
    data = build_default()
    assert (data["updated"], data["latest_report"]) == ("2026-10-05", "2026-10-02")
    assert [c["id"] for c in data["categories"]] == ["vegetable", "spice", "fruit", "fish"]
    assert data["categories"][1]["label"] == "香味野菜"


def test_item_series_shapes():
    tomato = item(build_default(), "tomato")
    assert tomato["ncr"] == [["2020-11-16", 170, 120, 210, "prevailing"], ["2022-06-06", 80, None, None, "prevailing"]]
    assert tomato["cartimar"] == [["2024-06-03", 82.5]]
    assert tomato["own"] == [["2021-01-29", 100]]
    assert (tomato["name_ja"], tomato["name_tl"], tomato["name_en"], tomato["unit"]) == ("トマト", "Kamatis", "Tomato", "kg")


def test_one_own_item_can_feed_two_commodities():
    data = build_default()
    assert item(data, "cabbage")["own"] == [["2020-11-20", 100]]
    assert item(data, "cabbage_scorpio")["own"] == [["2020-11-20", 100]]


def test_own_only_commodity_is_kept_and_empty_or_hidden_ones_are_dropped():
    ids = [i["id"] for i in build_default()["items"]]
    assert "celery" in ids                 # 公的データは無いが実測値がある
    assert "cabbage" in ids                # 同上
    assert "melon" not in ids              # どの系列も空
    assert "bangus_large" not in ids       # display=0


def test_unmatched_own_items_become_standalone_items_at_the_end():
    data = build_default()
    ids = [i["id"] for i in data["items"]]
    assert ids == ["tomato", "cabbage", "cabbage_scorpio", "celery", "own:カラス貝", "own:パセリ"]
    shell = item(data, "own:カラス貝")
    assert (shell["category"], shell["name_ja"], shell["name_tl"]) == ("fish", "カラス貝", "Tahong")
    assert shell["ncr"] == [] and shell["cartimar"] == [] and shell["own"] == [["2020-12-22", 150]]
    assert item(data, "own:パセリ")["category"] == "vegetable"
