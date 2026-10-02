"""Build the compact JSON consumed by the static price chart."""

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo


CATEGORIES = [
    {"id": "vegetable", "label": "野菜"},
    {"id": "spice", "label": "香味野菜"},
    {"id": "fruit", "label": "果物"},
    {"id": "fish", "label": "魚介"},
    {"id": "meat", "label": "肉"},
]


def _number(value):
    return None if value in (None, "") else float(value)


def _series(weekly: list[dict], cid: str, series: str) -> list[list]:
    points = []
    for row in weekly:
        if row["commodity_id"] != cid or row["series"] != series:
            continue
        if series == "ncr":
            points.append([row["week_start"], _number(row["price"]), _number(row.get("low")),
                           _number(row.get("high")), row["basis"]])
        else:
            points.append([row["week_start"], _number(row["price"])])
    return sorted(points, key=lambda point: point[0])


def build(weekly: list[dict], own: list[dict], commodities: list[dict], *, updated: str, latest_report: str) -> dict:
    items = []
    mapped_names = {name for commodity in commodities for name in commodity.get("own_items", "").split("|") if name}
    for commodity in sorted(commodities, key=lambda row: (int(row["order"]), row["commodity_id"])):
        if commodity["display"] != "1":
            continue
        cid = commodity["commodity_id"]
        own_names = set(commodity.get("own_items", "").split("|")) - {""}
        own_points = sorted([[row["date"], _number(row["price"])] for row in own if row["item_ja"] in own_names],
                            key=lambda point: point[0])
        item = dict(id=cid, category=commodity["category"], name_ja=commodity["name_ja"],
                    name_tl=commodity["name_tl"], name_en=commodity["name_en"], unit="kg",
                    ncr=_series(weekly, cid, "ncr"), cartimar=_series(weekly, cid, "cartimar"), own=own_points)
        if item["ncr"] or item["cartimar"] or item["own"]:
            items.append(item)

    unmatched = sorted({row["item_ja"] for row in own if row["item_ja"] not in mapped_names})
    for name in unmatched:
        matching = [row for row in own if row["item_ja"] == name]
        first = matching[0]
        items.append(dict(id=f"own:{name}", category="fish" if first["sheet"] == "魚介" else "vegetable",
                          name_ja=name, name_tl=first["name_tl"], name_en=first["name_en"], unit="kg",
                          ncr=[], cartimar=[], own=sorted([[row["date"], _number(row["price"])] for row in matching],
                                                       key=lambda point: point[0])))
    return {"updated": updated, "latest_report": latest_report, "categories": CATEGORIES, "items": items}


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("site/data.json"))
    args = parser.parse_args(argv)
    sources = _read(args.data_dir / "sources.csv")
    latest_report = max((row["report_date"] for row in sources if row["status"] == "parsed"), default="")
    data = build(_read(args.data_dir / "weekly.csv"), _read(args.data_dir / "own.csv"),
                 _read(args.data_dir / "commodities.csv"),
                 updated=datetime.now(ZoneInfo("Asia/Manila")).date().isoformat(), latest_report=latest_report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
