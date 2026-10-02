"""Deterministic CSV stores for observations and processing logs."""

import csv
import os
from pathlib import Path


DAILY_FIELDS = ("date", "commodity_id", "spec", "unit", "low", "high", "prevailing", "average", "source_url")
MARKET_FIELDS = ("date", "market", "commodity_id", "low", "high", "price", "source_url")
UNMAPPED_FIELDS = ("raw_name", "first_date", "last_date", "count", "example_url")
REJECTED_FIELDS = ("date", "commodity_id", "value", "previous", "reason", "source_url")


def fmt(x: float | None) -> str:
    if x is None or x == "":
        return ""
    return f"{float(x):.2f}".rstrip("0").rstrip(".")


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _save(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


class _DateStore:
    fields: tuple[str, ...]
    sort_fields: tuple[str, ...]

    def __init__(self, path: Path):
        self.path = Path(path)
        self._rows = _read(self.path)

    def replace_date(self, date: str, rows: list[dict]) -> None:
        self._rows = [row for row in self._rows if row["date"] != date]
        for row in rows:
            self._rows.append({field: date if field == "date" else fmt(row.get(field)) if field in ("low", "high", "prevailing", "average", "price") else str(row.get(field, "")) for field in self.fields})

    def rows(self) -> list[dict]:
        return sorted(self._rows, key=lambda row: tuple(row[field] for field in self.sort_fields))

    def save(self) -> None:
        _save(self.path, self.fields, self.rows())


class DailyStore(_DateStore):
    fields = DAILY_FIELDS
    sort_fields = ("date", "commodity_id")

    def __init__(self, path: Path):
        super().__init__(path)
        self._last_before = None
        self._last_values = {}

    def replace_date(self, date: str, rows: list[dict]) -> None:
        super().replace_date(date, rows)
        self._last_before = None

    def dates_with_source(self, url: str) -> set[str]:
        return {row["date"] for row in self._rows if row["source_url"] == url}

    def last_price(self, commodity_id: str, before: str) -> float | None:
        if self._last_before != before:
            latest = {}
            for row in self._rows:
                if row["date"] >= before:
                    continue
                value = None
                for field in ("prevailing", "average"):
                    if row[field] != "":
                        value = float(row[field])
                        break
                if value is None and row["low"] != "" and row["high"] != "":
                    value = (float(row["low"]) + float(row["high"])) / 2
                if value is not None:
                    old = latest.get(row["commodity_id"])
                    if old is None or row["date"] >= old[0]:
                        latest[row["commodity_id"]] = (row["date"], value)
            self._last_values = {cid: value for cid, (_, value) in latest.items()}
            self._last_before = before
        return self._last_values.get(commodity_id)


class MarketStore(_DateStore):
    fields = MARKET_FIELDS
    sort_fields = ("date", "market", "commodity_id")


class UnmappedLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._rows = {row["raw_name"]: row for row in _read(self.path)}

    def add(self, raw_name: str, date: str, url: str) -> None:
        row = self._rows.get(raw_name)
        if row is None:
            self._rows[raw_name] = dict(raw_name=raw_name, first_date=date, last_date=date, count="1", example_url=url)
        else:
            row["first_date"] = min(row["first_date"], date)
            row["last_date"] = max(row["last_date"], date)
            row["count"] = str(int(row["count"]) + 1)

    def retire_mapped(self, lookup, start: str | None, end: str | None) -> None:
        self._rows = {name: row for name, row in self._rows.items()
                      if not (lookup(name) is not None
                              and (start is None or row["first_date"] >= start)
                              and (end is None or row["last_date"] <= end))}

    def save(self) -> None:
        rows = sorted(self._rows.values(), key=lambda row: (-int(row["count"]), row["raw_name"]))
        _save(self.path, UNMAPPED_FIELDS, rows)


class RejectedLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._rows = _read(self.path)

    def add(self, date: str, commodity_id: str, value: float, previous: float | None, reason: str, source_url: str) -> None:
        self._rows.append(dict(date=date, commodity_id=commodity_id, value=fmt(value), previous=fmt(previous), reason=reason, source_url=source_url))

    def remove_source(self, url: str) -> None:
        self._rows = [row for row in self._rows if row["source_url"] != url]

    def save(self) -> None:
        rows = sorted(self._rows, key=lambda row: (row["date"], row["commodity_id"], row["source_url"]))
        _save(self.path, REJECTED_FIELDS, rows)
