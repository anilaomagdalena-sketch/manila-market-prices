"""首都圏まとめページ（図版レイアウトと、LOW/HIGH/PREVAILING/AVERAGEの表）を読む。"""
from __future__ import annotations

from .geometry import (DASHES, FOOTNOTE_RE, NA_WORDS, Word, group_lines, is_num, label_left_of,
                       label_words, to_float, value_groups)

HEADER_FIELDS = {"LOW": "low", "HIGH": "high", "PREVAILING": "prevailing", "AVERAGE": "average"}


def parse_summary_page(words: list[Word]) -> list[dict]:
    headers = [w for w in words if w.text in HEADER_FIELDS]
    if len({w.text for w in headers}) >= 3:
        return _parse_header_table(words, headers)
    has_today = any(w.text == "Today" for w in words)
    return _parse_infographic(words, has_today)


def _parse_infographic(words: list[Word], has_today: bool) -> list[dict]:
    labels = label_words(words)
    rows = []
    for g in value_groups(words, max_gap=2.2):
        name = label_left_of(g, labels)
        if not name:
            continue
        nums = [to_float(w.text) for w in g.nums]
        row = {"raw_name": name, "spec": "", "unit": "", "low": None, "high": None,
               "prevailing": None, "average": None}
        if g.has_dash and len(nums) == 2:
            row["low"], row["high"] = min(nums), max(nums)
        elif has_today or len(nums) == 1:
            row["prevailing"] = nums[0]
        else:
            continue
        rows.append(row)
    return rows


def _parse_header_table(words: list[Word], headers: list[Word]) -> list[dict]:
    """LOW/HIGH/PREVAILING/AVERAGEの見出しがある表。1行に2つの表が横に並ぶことがある。

    行を「ラベルの単語の並び＋数値の並び」の区切りに分け、
    各数値は、真上にある見出しのうちx座標がいちばん近いものの列とみなす。
    """
    header_names = set(HEADER_FIELDS) | {"COMMODITIES", "COMMODITY"}
    rows = []
    for line in group_lines(words):
        segments: list[tuple[list[Word], list[Word]]] = []
        labels: list[Word] = []
        nums: list[Word] = []
        for w in line:
            if is_num(w.text):
                nums.append(w)
            elif w.text in DASHES or w.text in NA_WORDS or FOOTNOTE_RE.match(w.text):
                continue
            else:
                if nums:
                    segments.append((labels, nums))
                    labels, nums = [], []
                if w.text not in header_names:
                    labels.append(w)
        if nums:
            segments.append((labels, nums))
        for labels, nums in segments:
            # 数値のすぐ左に続く単語だけをラベルにする（遠くにある分類名は入れない）
            picked: list[Word] = []
            right_edge = nums[0].x0
            for w in reversed(labels):
                limit = 32.0 if not picked else 1.5
                if right_edge - w.x1 > w.h * limit:
                    break
                picked.insert(0, w)
                right_edge = w.x0
            if not picked:
                continue
            row = {"raw_name": " ".join(w.text for w in picked), "spec": "", "unit": "",
                   "low": None, "high": None, "prevailing": None, "average": None}
            for n in nums:
                near = [h for h in headers if h.bottom <= n.top + 1 and abs(h.cx - n.cx) < n.h * 7.5]
                if not near:
                    continue
                nearest_y = max(h.bottom for h in near)
                band = [h for h in near if abs(h.bottom - nearest_y) < n.h * 0.4]
                head = min(band, key=lambda h: abs(h.cx - n.cx))
                row[HEADER_FIELDS[head.text]] = to_float(n.text)
            if any(row[k] is not None for k in ("low", "high", "prevailing", "average")):
                rows.append(row)
    return rows
