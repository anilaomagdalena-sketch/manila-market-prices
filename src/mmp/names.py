"""PDFに出てくる品目名を、commodities.csv の commodity_id に対応づける。"""
from __future__ import annotations

import csv
import re
from pathlib import Path

_MARKS = re.compile(r"[*ᵃᵇᶜᵈᵉ]+")
_SUFFIX = re.compile(r"\s*(\(per kg\)|per piece|,\s*local)$", re.I)
_PREFIX = re.compile(r"^(?:\(per kg\)\s+|[A-Z]{3,}\s+)+(?=[A-Z(])")


def normalize(name: str) -> str:
    """表記ゆれを吸収する。

    注記記号、前に付いた分類名（VEGETABLES など全部大文字の語）や (per kg)、
    後ろの (per kg)・per piece・", Local"、連続空白、大文字小文字の違いを落とす。
    """
    s = _MARKS.sub("", name).strip()
    s = _PREFIX.sub("", s)
    s = _SUFFIX.sub("", s)
    return re.sub(r"\s+", " ", s).strip().lower()


class NameMap:
    def __init__(self, path: Path):
        self.alias_to_id: dict[str, str] = {}
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                for alias in row["aliases"].split("|"):
                    key = normalize(alias)
                    if key in self.alias_to_id and self.alias_to_id[key] != row["commodity_id"]:
                        raise ValueError(f"alias {alias!r} is used by two commodities")
                    self.alias_to_id[key] = row["commodity_id"]

    def lookup(self, raw_name: str, spec: str = "") -> str | None:
        """「名前 [規格]」→ 名前 → 末尾の脚注文字(a〜f)を1つ落とした名前、の順に探す。"""
        key = normalize(raw_name)
        candidates = [f"{key} [{normalize(spec)}]"] if spec else []
        candidates.append(key)
        if re.search(r"[a-z)][a-f]$", key):
            candidates.append(key[:-1])
        for c in candidates:
            if c in self.alias_to_id:
                return self.alias_to_id[c]
        return None
