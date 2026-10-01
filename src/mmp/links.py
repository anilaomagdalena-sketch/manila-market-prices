"""Classify PDF links from the DA price monitoring index."""

from dataclasses import dataclass
import datetime as dt
import re
from urllib.parse import urlsplit


START_DATE = dt.date(2020, 11, 1)


@dataclass(frozen=True)
class Link:
    url: str
    kind: str
    revised: bool
    report_date: dt.date | None


_MONTHS = {
    name: month
    for month, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        1,
    )
}
_DATE = re.compile(r"([A-Za-z]{3,})-(\d{1,2})-(\d{4})(?=\D|$)")
_HREF = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)


def classify(url: str) -> Link:
    url = re.sub(r"^http://", "https://", url, flags=re.IGNORECASE)
    filename = urlsplit(url).path.rsplit("/", 1)[-1]
    lower = filename.lower()
    revised = lower.startswith(("revised-", "updated-")) or "-revised" in lower or "-final-version" in lower

    if re.match(r"^(?:revised-|updated-)?price-monitoring-", lower) and not lower.startswith("price-monitoring-report-"):
        kind = "price_monitoring"
    elif re.match(r"^(?:revised-)?daily-price-index-", lower):
        kind = "daily_price_index"
    else:
        kind = "skip"

    report_date = None
    for match in _DATE.finditer(filename):
        month = _MONTHS.get(match.group(1)[:3].lower())
        if month is None:
            continue
        try:
            report_date = dt.date(int(match.group(3)), month, int(match.group(2)))
        except ValueError:
            continue
        break
    return Link(url, kind, revised, report_date)


def extract_links(html: str) -> list[Link]:
    links = []
    seen = set()
    for url in _HREF.findall(html):
        link = classify(url)
        if link.url not in seen:
            seen.add(link.url)
            links.append(link)
    return links
