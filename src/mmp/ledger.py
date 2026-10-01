"""Persistent record of DA report URLs and their processing status."""

import csv
import os
from pathlib import Path


FIELDS = ("url", "kind", "revised", "report_date", "status", "layout", "rows", "sha256", "fetched_at", "error")


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._entries = {}
        if self.path.exists():
            with self.path.open(encoding="utf-8", newline="") as handle:
                for entry in csv.DictReader(handle):
                    self.put(entry)

    def has(self, url: str) -> bool:
        return url in self._entries

    def get(self, url: str) -> dict | None:
        return self._entries.get(url)

    def put(self, entry: dict) -> None:
        self._entries[entry["url"]] = {field: str(entry.get(field, "")) for field in FIELDS}

    def entries(self) -> list[dict]:
        return list(self._entries.values())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(sorted(self._entries.values(), key=lambda e: (e["report_date"], e["url"])))
        os.replace(temp, self.path)
