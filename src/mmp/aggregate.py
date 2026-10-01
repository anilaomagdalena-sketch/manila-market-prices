"""Aggregate daily DA observations into Monday-based weekly series."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, timedelta
from pathlib import Path

from .store import fmt


FIELDS = ("week_start", "series", "commodity_id", "price", "low", "high", "basis", "n_days")
_BASIS_ORDER = {"prevailing": 0, "average": 1, "midpoint": 2}


def week_start(value: str) -> str:
    day = date.fromisoformat(value)
    return (day - timedelta(days=day.weekday())).isoformat()


def representative(row: dict) -> tuple[float, str] | None:
    for field in ("prevailing", "average"):
        if row.get(field) not in (None, ""):
            return float(row[field]), field
    if row.get("low") not in (None, "") and row.get("high") not in (None, ""):
        return (float(row["low"]) + float(row["high"])) / 2, "midpoint"
    return None


def _extreme(rows: list[dict], field: str, fn):
    values = [float(row[field]) for row in rows if row.get(field) not in (None, "")]
    return fn(values) if values else None


def aggregate(daily: list[dict], market_daily: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in daily:
        value = representative(row)
        if value is not None:
            groups[("ncr", row["commodity_id"], week_start(row["date"]))].append((row, value))
    for row in market_daily:
        if row.get("price") not in (None, ""):
            groups[("cartimar", row["commodity_id"], week_start(row["date"]))].append((row, (float(row["price"]), "market")))

    output = []
    for (series, cid, monday), observations in groups.items():
        rows = [row for row, _ in observations]
        basis_count = Counter(basis for _, (_, basis) in observations)
        basis = min(basis_count, key=lambda key: (-basis_count[key], _BASIS_ORDER.get(key, 3)))
        output.append(dict(week_start=monday, series=series, commodity_id=cid,
                           price=round(sum(value for _, (value, _) in observations) / len(observations), 2),
                           low=_extreme(rows, "low", min), high=_extreme(rows, "high", max),
                           basis=basis, n_days=len(observations)))
    return sorted(output, key=lambda row: (row["series"], row["commodity_id"], row["week_start"]))


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)
    rows = aggregate(_read(args.data_dir / "daily.csv"), _read(args.data_dir / "market_daily.csv"))
    path = args.data_dir / "weekly.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: fmt(value) if key in ("price", "low", "high") else value
                          for key, value in row.items()} for row in rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
