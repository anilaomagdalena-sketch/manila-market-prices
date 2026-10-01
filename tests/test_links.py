import datetime as dt
from pathlib import Path

import pytest

from mmp.links import classify, extract_links

BASE = "https://www.da.gov.ph/wp-content/uploads"


@pytest.mark.parametrize("path, kind, revised, date", [
    ("2020/11/Price-Monitoring-November-20-2020.pdf", "price_monitoring", False, dt.date(2020, 11, 20)),
    # アップロード月（2025/01）と報告月（2024年12月）がずれている
    ("2025/01/Price-Monitoring-December-24-2024.pdf", "price_monitoring", False, dt.date(2024, 12, 24)),
    # 月名の綴り違い
    ("2020/11/Price-Monitoring-Novermber-11-2020.pdf", "price_monitoring", False, dt.date(2020, 11, 11)),
    # 後ろに付く訂正の印
    ("2021/09/Price-Monitoring-September-1-2021-Final-Version.pdf", "price_monitoring", True, dt.date(2021, 9, 1)),
    ("2021/09/Price-Monitoring-September-10-2021-Revised.pdf", "price_monitoring", True, dt.date(2021, 9, 10)),
    ("2023/05/Revised-Price-Monitoring-May-3-2023.pdf", "price_monitoring", True, dt.date(2023, 5, 3)),
    ("2025/06/Daily-Price-Index-June-1-2025.pdf", "daily_price_index", False, dt.date(2025, 6, 1)),
    ("2026/01/Revised-Daily-Price-Index-January-5-2026.pdf", "daily_price_index", True, dt.date(2026, 1, 5)),
    # 取り違えてはいけないもの
    ("2026/09/Daily-Cigarette-Price-Monitoring-August-28-2026.pdf", "skip", False, dt.date(2026, 8, 28)),
    ("2026/08/Weekly-Average-Prices-July-27-August-2-2026.pdf", "skip", False, None),
    ("2019/03/Retail-Price-Monitoring-March-4-2019.pdf", "skip", False, dt.date(2019, 3, 4)),
    ("2020/04/Price-Monitoring-Report-April-2-2020.pdf", "skip", False, dt.date(2020, 4, 2)),
    ("2018/02/Price-Watch-February-6-2018.pdf", "skip", False, dt.date(2018, 2, 6)),
])
def test_classify(path, kind, revised, date):
    link = classify(f"{BASE}/{path}")
    assert (link.kind, link.revised) == (kind, revised)
    if kind != "skip":
        assert link.report_date == date


def test_classify_normalizes_http():
    link = classify("http://www.da.gov.ph/wp-content/uploads/2020/12/Price-Monitoring-December-1-2020.pdf")
    assert link.url.startswith("https://")


def test_classify_unreadable_date_is_none():
    assert classify(f"{BASE}/2022/01/Price-Monitoring-latest.pdf").report_date is None


def test_extract_links_dedupes_and_keeps_only_pdfs():
    html = (Path(__file__).parent / "fixtures" / "index_sample.html").read_text()
    links = extract_links(html)
    assert len(links) == 5
    assert [l.kind for l in links] == ["price_monitoring", "skip", "daily_price_index", "skip", "skip"]
    assert links[4].url.startswith("https://")
