import datetime as dt

from mmp.check_health import check

TODAY = dt.date(2026, 10, 5)


def e(date, status="parsed", fetched="2026-10-05T00:10:00Z"):
    return {"url": f"https://x/{date}-{status}.pdf", "kind": "price_monitoring", "revised": "0",
            "report_date": date, "status": status, "layout": "", "rows": "0", "sha256": "",
            "fetched_at": fetched, "error": ""}


def test_half_of_new_reports_failing_is_unhealthy():
    assert check([e("2026-10-02"), e("2026-10-01", "failed")], TODAY, since="2026-10-05T00:00:00Z") == [
        "1 of 2 newly fetched reports failed to parse"]


def test_stale_when_latest_parsed_is_older_than_14_days():
    assert check([e("2026-09-20"), e("2026-10-02", "failed")], TODAY) == [
        "no parsed report in the last 14 days (latest: 2026-09-20)"]
    assert check([e("2026-09-21")], TODAY) == []


def test_stale_when_nothing_parsed():
    assert check([e("2026-10-02", "skipped")], TODAY) == ["no parsed report in the last 14 days (latest: none)"]


def test_half_or_more_new_failures():
    entries = [e("2026-10-02"), e("2026-10-01", "failed"), e("2026-09-30", "failed"),
               e("2026-09-01", "failed", fetched="2026-09-07T00:00:00Z")]
    assert check(entries, TODAY, since="2026-10-05T00:00:00Z") == ["2 of 3 newly fetched reports failed to parse"]


def test_single_new_failure_is_not_enough():
    assert check([e("2026-10-02", fetched="2026-09-28T00:00:00Z"), e("2026-10-03", "failed")],
                 TODAY, since="2026-10-05T00:00:00Z") == []
