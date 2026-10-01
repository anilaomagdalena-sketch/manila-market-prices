from mmp.ledger import Ledger


def entry(url, date="2020-11-20", status="parsed"):
    return {"url": url, "kind": "price_monitoring", "revised": "0", "report_date": date,
            "status": status, "layout": "rowtable", "rows": "45", "sha256": "ab",
            "fetched_at": "2026-10-05T00:00:00Z", "error": ""}


def test_roundtrip_and_sorted(tmp_path):
    p = tmp_path / "sources.csv"
    led = Ledger(p)
    led.put(entry("https://x/b.pdf", "2021-01-02"))
    led.put(entry("https://x/a.pdf", "2020-11-20"))
    led.save()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "url,kind,revised,report_date,status,layout,rows,sha256,fetched_at,error"
    assert lines[1].startswith("https://x/a.pdf,") and lines[2].startswith("https://x/b.pdf,")
    again = Ledger(p)
    assert again.has("https://x/a.pdf") and not again.has("https://x/c.pdf")
    assert again.get("https://x/b.pdf")["report_date"] == "2021-01-02"


def test_put_overwrites_by_url(tmp_path):
    led = Ledger(tmp_path / "s.csv")
    led.put(entry("https://x/a.pdf", status="failed"))
    led.put(entry("https://x/a.pdf", status="parsed"))
    assert len(led.entries()) == 1 and led.get("https://x/a.pdf")["status"] == "parsed"


def test_save_is_atomic(tmp_path):
    p = tmp_path / "s.csv"
    led = Ledger(p)
    led.put(entry("https://x/a.pdf"))
    led.save()
    assert not list(tmp_path.glob("*.tmp"))
