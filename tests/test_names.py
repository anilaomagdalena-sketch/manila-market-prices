from pathlib import Path

import pytest

from mmp.names import NameMap, normalize

NM = NameMap(Path(__file__).parent.parent / "data" / "commodities.csv")


@pytest.mark.parametrize("raw, spec, expected", [
    ("Cabbage (Scorpio)", "750 gm - 1 kg/head", "cabbage_scorpio"),   # 2020
    ("Cabbage Repolyo", "", "cabbage"),                               # 2022
    ("Scorpio", "", "cabbage_scorpio"),                               # 2024（品種名だけ）
    ("Cabbage Repolyo (Scorpio)", "", "cabbage_scorpio"),             # 2026
    ("Cabbage (Scorpio), Local", "", "cabbage_scorpio"),              # Daily Price Index
    ("Local Garlic Bawange", "", "garlic_local"),                     # 脚注 e が貼りついている
    ("Indian mackerel Alumahan**", "", "alumahan"),
    ("VEGETABLES Pechay Tagalog", "", "pechay_native"),               # 分類名が前に付いた
    ("(per kg) Tilapia", "", "tilapia"),
    ("Tomato Kamatis", "", "tomato"),
    ("Red Onion", "13-15 pcs/kg", "red_onion_local"),
    ("Red Onion (Imported)", "", "red_onion_imported"),
    ("Bangus", "Large", "bangus_large"),                              # 規格で区別する
    ("Bangus", "Medium (3-4pcs/kg)", "bangus"),
    ("Bangus", "med(3-4pcs/kg)", "bangus"),
    ("Premium", "", None),                                            # 米は対象外
])
def test_lookup(raw, spec, expected):
    assert NM.lookup(raw, spec) == expected


def test_normalize():
    assert normalize("  Local  Garlic   Bawang**  ") == "local garlic bawang"
    assert normalize("Beef Rump (per kg)") == "beef rump"
    assert normalize("Squid (Pusit Bisaya), Local") == "squid (pusit bisaya)"


@pytest.mark.parametrize("raw, expected", [
    ("Mung Bean", "mung_bean"),
    ("Mungbean", "mung_bean"),
    ("Salmon Belly, Imported", "salmon_belly_imported"),
    ("Salmon Head, Imported", "salmon_head"),
    ("Broccoli, Imported", "broccoli_imported"),
    ("Squid, Imported", "squid_imported"),
    ("Pampano, Imported", "pampano_imported"),
    ("Pampano, Local", "pampano_local"),
    ("Ginger, Imported", "ginger_imported"),
    ("Carrots, Imported", "carrot_imported"),
    ("Habichuelas (Baguio beans), local", "baguio_beans"),
])
def test_author_approved_unmapped_names(raw, expected):
    assert NM.lookup(raw) == expected
