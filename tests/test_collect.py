import datetime as dt
import fcntl
from pathlib import Path

import pytest

from mmp import collect
from mmp.ledger import Ledger
from mmp.parsers.pdf import ParseResult
from mmp.store import DailyStore, MarketStore

BASE = "https://www.da.gov.ph/wp-content/uploads"
COMMODITIES = Path(__file__).parent.parent / "data" / "commodities.csv"
PDF = b"%PDF-1.4 "


def nrow(name, **kw):
    base = {"raw_name": name, "spec": "", "unit": "kg", "low": None, "high": None,
            "prevailing": None, "average": None}
    base.update(kw)
    return base


class World:
    """偽のDAサイト。URLごとに、返すバイト列と解析結果を決めておく。"""

    def __init__(self, tmp_path):
        self.data_dir = tmp_path / "data"
        self.data_dir.mkdir()
        (self.data_dir / "commodities.csv").write_bytes(COMMODITIES.read_bytes())
        self.files: dict[str, bytes] = {}
        self.listed: list[str] = []
        self.results: dict[bytes, ParseResult] = {}
        self.fetched: list[str] = []
        self.padding = 1000   # MIN_LINKS を満たすための、対象外リンクの数

    def add(self, name, rows=None, market_rows=None, body_date=None, raw=None, parse_error=None, missing=False):
        """missing=True は、一覧には載っているが取得すると404になるPDF。"""
        url = f"{BASE}/2099/01/{name}.pdf"
        data = raw if raw is not None else PDF + name.encode()
        self.listed.append(url)
        if not missing:
            self.files[url] = data
        self.results[data] = parse_error or ParseResult(
            report_date=body_date, layouts=["rowtable"], rows=rows or [], market_rows=market_rows or [])
        return url

    def publish(self, url):
        """missing=True で足したPDFを、取得できるようにする。"""
        name = url.rsplit("/", 1)[1][:-4]
        self.files[url] = PDF + name.encode()

    def index(self) -> bytes:
        hrefs = [f'<a href="{u}">x</a>' for u in self.listed]
        hrefs += [f'<a href="{BASE}/2018/02/Price-Watch-February-{i}-2018.pdf">x</a>' for i in range(self.padding)]
        return "\n".join(hrefs).encode()

    def fetch(self, url):
        self.fetched.append(url)
        if url == collect.INDEX_URL:
            return self.index()
        if url not in self.files:
            raise collect.FetchError("404")
        return self.files[url]

    def parse(self, data):
        r = self.results[data]
        if isinstance(r, Exception):
            raise r
        return r

    def run(self, **kw):
        return collect.run(self.data_dir, fetch=self.fetch, parse=self.parse, delay=0, **kw)

    def ledger(self):
        return Ledger(self.data_dir / "sources.csv")

    def daily(self):
        return DailyStore(self.data_dir / "daily.csv").rows()


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_parses_new_pdf_and_never_fetches_it_again(world):
    url = world.add("Price-Monitoring-November-20-2020",
                    rows=[nrow("Tomato", low=140.0, high=200.0, prevailing=180.0), nrow("Premium", prevailing=45.0)])
    stats = world.run()
    assert (stats.parsed, stats.failed) == (1, 0)
    assert [(r["date"], r["commodity_id"], r["prevailing"]) for r in world.daily()] == [("2020-11-20", "tomato", "180")]
    assert world.ledger().get(url)["status"] == "parsed"
    assert "Premium" in (world.data_dir / "unmapped.csv").read_text(encoding="utf-8")
    world.fetched.clear()
    stats = world.run()
    assert world.fetched == [collect.INDEX_URL] and stats.new == 0


def test_lookalike_and_old_reports_are_skipped_without_fetching(world):
    cig = world.add("Daily-Cigarette-Price-Monitoring-August-28-2026")
    weekly = world.add("Weekly-Average-Prices-July-27-August-2-2026")
    old = world.add("Price-Monitoring-October-30-2020")
    world.run()
    assert set(world.fetched) == {collect.INDEX_URL}
    led = world.ledger()
    assert led.get(cig)["status"] == led.get(weekly)["status"] == led.get(old)["status"] == "skipped"
    assert led.get(old)["error"] == "before_start_date"
    assert led.get(f"{BASE}/2018/02/Price-Watch-February-1-2018.pdf")["error"] == "not_a_price_report"


def test_index_with_too_few_links_raises(world):
    world.padding = 3
    world.add("Price-Monitoring-November-20-2020", rows=[nrow("Tomato", prevailing=180.0)])
    with pytest.raises(collect.FetchError):
        world.run()
    assert world.daily() == []


def test_fetch_error_is_not_recorded_so_it_is_retried(world):
    url = world.add("Price-Monitoring-November-20-2020", rows=[nrow("Tomato", prevailing=180.0)], missing=True)
    stats = world.run()
    assert stats.fetch_errors == 1 and not world.ledger().has(url)
    world.publish(url)
    assert world.run().parsed == 1


def test_html_error_page_with_200_is_treated_as_fetch_error(world):
    url = world.add("Price-Monitoring-November-20-2020", raw=b"<html>Not found</html>")
    stats = world.run()
    assert stats.fetch_errors == 1 and not world.ledger().has(url)


def test_image_only_pdf_becomes_failed_and_is_not_refetched(world):
    url = world.add("Price-Monitoring-May-1-2025", rows=[])
    assert world.run().failed == 1
    e = world.ledger().get(url)
    assert (e["status"], e["error"]) == ("failed", "no_rows")
    world.fetched.clear()
    world.run()
    assert url not in world.fetched
    world.results[world.files[url]] = ParseResult(None, ["summary"], [nrow("Tomato Kamatis", low=30.0, high=90.0)], [])
    assert world.run(retry_failed=True).parsed == 1


def test_parser_exception_becomes_failed(world):
    url = world.add("Price-Monitoring-May-2-2025", parse_error=ValueError("boom\ntrace"))
    world.run()
    e = world.ledger().get(url)
    assert e["status"] == "failed" and e["error"] == "ValueError: boom"


def test_date_from_body_when_file_name_has_none(world):
    url = world.add("Price-Monitoring-latest", rows=[nrow("Tomato", prevailing=50.0)], body_date=dt.date(2022, 1, 3))
    world.run()
    assert world.daily()[0]["date"] == "2022-01-03"
    assert world.ledger().get(url)["report_date"] == "2022-01-03"


def test_no_date_anywhere_is_failed(world):
    url = world.add("Price-Monitoring-latest", rows=[nrow("Tomato", prevailing=50.0)])
    world.run()
    assert world.ledger().get(url)["error"] == "no_date" and world.daily() == []


def test_date_mismatch_keeps_file_name_date_and_notes_it(world):
    url = world.add("Price-Monitoring-June-1-2021", rows=[nrow("Tomato", prevailing=40.0)], body_date=dt.date(2021, 5, 31))
    world.run()
    assert world.daily()[0]["date"] == "2021-06-01"
    e = world.ledger().get(url)
    assert e["status"] == "parsed" and e["error"] == "date_mismatch body=2021-05-31"


def test_revised_replaces_original_regardless_of_order(world):
    orig = world.add("Price-Monitoring-May-3-2023", rows=[nrow("Tomato", prevailing=40.0), nrow("Tilapia", prevailing=120.0)])
    rev = world.add("Revised-Price-Monitoring-May-3-2023", rows=[nrow("Tomato", prevailing=45.0)])
    world.run()
    assert [(r["commodity_id"], r["prevailing"]) for r in world.daily()] == [("tomato", "45")]
    led = world.ledger()
    assert led.get(orig)["status"] == "superseded" and led.get(rev)["status"] == "parsed"


def test_original_arriving_after_revised_does_not_overwrite(world):
    world.add("Revised-Price-Monitoring-May-3-2023", rows=[nrow("Tomato", prevailing=45.0)])
    world.run()
    orig = world.add("Price-Monitoring-May-3-2023", rows=[nrow("Tomato", prevailing=40.0)])
    world.run()
    assert world.daily()[0]["prevailing"] == "45"
    assert world.ledger().get(orig)["status"] == "superseded"


def test_dpi_is_not_fetched_when_price_monitoring_exists(world):
    world.add("Price-Monitoring-June-2-2025", rows=[nrow("Tomato (Kamatis)", low=30.0, high=90.0, prevailing=60.0)])
    dpi = world.add("Daily-Price-Index-June-2-2025", rows=[nrow("Tomato", prevailing=61.0)])
    world.run()
    assert dpi not in world.fetched
    e = world.ledger().get(dpi)
    assert (e["status"], e["error"]) == ("skipped", "pm_exists")
    assert world.daily()[0]["prevailing"] == "60"


def test_dpi_fills_in_when_price_monitoring_failed(world):
    world.add("Price-Monitoring-May-1-2025", rows=[])
    world.add("Daily-Price-Index-May-1-2025", rows=[nrow("Tomato", spec="15-18 pcs/kg", prevailing=61.0)])
    world.run()
    assert [(r["date"], r["prevailing"]) for r in world.daily()] == [("2025-05-01", "61")]


def test_price_monitoring_arriving_later_replaces_dpi(world):
    dpi = world.add("Daily-Price-Index-June-3-2025", rows=[nrow("Tomato", prevailing=61.0)])
    world.run()
    world.add("Price-Monitoring-June-3-2025", rows=[nrow("Tomato (Kamatis)", prevailing=60.0)])
    world.run()
    assert world.daily()[0]["prevailing"] == "60"
    assert world.ledger().get(dpi)["status"] == "superseded"


def test_same_commodity_twice_in_one_pdf_keeps_first(world):
    world.add("Price-Monitoring-March-1-2024", rows=[nrow("Papaya", low=50.0, high=80.0), nrow("Papaya", low=10.0, high=20.0)])
    world.run()
    assert [(r["low"], r["high"]) for r in world.daily()] == [("50", "80")]


def test_jump_and_non_positive_values_are_rejected(world):
    world.add("Price-Monitoring-November-20-2020", rows=[nrow("Tomato", prevailing=100.0)])
    world.add("Price-Monitoring-November-23-2020",
              rows=[nrow("Tomato", prevailing=1000.0), nrow("Tilapia", prevailing=0.0), nrow("Bangus", prevailing=160.0)])
    world.run()
    assert [(r["date"], r["commodity_id"]) for r in world.daily()] == [
        ("2020-11-20", "tomato"), ("2020-11-23", "bangus")]
    rejected = (world.data_dir / "rejected.csv").read_text(encoding="utf-8")
    assert "2020-11-23,tomato,1000,100,jump" in rejected and "2020-11-23,tilapia,0,,non_positive" in rejected


def test_only_cartimar_market_rows_are_stored(world):
    world.add("Price-Monitoring-August-28-2026",
              rows=[nrow("Tomato (Kamatis)", prevailing=120.0)],
              market_rows=[{"market": "Cartimar Market", "raw_name": "Tomato", "low": 110.0, "high": 110.0, "price": 110.0},
                           {"market": "Pasay City Market", "raw_name": "Tomato", "low": 90.0, "high": 90.0, "price": 90.0},
                           {"market": "Cartimar Market", "raw_name": "*Egg (Medium)", "low": 8.5, "high": 8.5, "price": 8.5}])
    world.run()
    rows = MarketStore(world.data_dir / "market_daily.csv").rows()
    assert [(r["market"], r["commodity_id"], r["price"]) for r in rows] == [("Cartimar", "tomato", "110")]


def test_max_new_stops_early_and_next_run_continues_oldest_first(world):
    for day in (20, 23, 24):
        world.add(f"Price-Monitoring-November-{day}-2020", rows=[nrow("Tomato", prevailing=100.0 + day)])
    assert world.run(max_new=2).parsed == 2
    assert [r["date"] for r in world.daily()] == ["2020-11-20", "2020-11-23"]
    assert world.run(max_new=2).parsed == 1
    assert [r["date"] for r in world.daily()] == ["2020-11-20", "2020-11-23", "2020-11-24"]


def test_crash_midway_leaves_consistent_state_and_resumes(world):
    for day in (20, 23, 24):
        world.add(f"Price-Monitoring-November-{day}-2020", rows=[nrow("Tomato", prevailing=100.0 + day)])
    real_fetch = world.fetch

    def flaky(url):
        if "November-24" in url:
            raise KeyboardInterrupt
        return real_fetch(url)

    with pytest.raises(KeyboardInterrupt):
        collect.run(world.data_dir, fetch=flaky, parse=world.parse, delay=0, checkpoint_every=1)
    led = world.ledger()
    parsed_urls = {e["url"] for e in led.entries() if e["status"] == "parsed"}
    in_data = {r["source_url"] for r in world.daily()}
    assert parsed_urls <= in_data                     # 台帳にあるものは必ずデータにある
    assert len(parsed_urls) == 2
    assert world.run().parsed == 1
    assert len(world.daily()) == 3


def test_cache_is_used_on_retry(world, tmp_path):
    url = world.add("Price-Monitoring-May-1-2025", rows=[])
    cache = tmp_path / "cache"
    world.run(cache_dir=cache)
    assert len(list(cache.glob("*.pdf"))) == 1
    world.fetched.clear()
    world.results[world.files[url]] = ParseResult(None, ["summary"], [nrow("Tomato Kamatis", low=30.0, high=90.0)], [])
    assert world.run(retry_failed=True, cache_dir=cache).parsed == 1
    assert url not in world.fetched


def test_reparse_range_uses_cached_pdf_without_refetching(world, tmp_path):
    url = world.add("Price-Monitoring-November-20-2020", rows=[nrow("Tomato", prevailing=100.0)])
    cache = tmp_path / "cache"
    assert world.run(cache_dir=cache).parsed == 1
    world.results[world.files[url]] = ParseResult(None, ["rowtable"], [nrow("Tomato", prevailing=110.0)], [])
    world.fetched.clear()
    assert world.run(cache_dir=cache, reparse_from="2020-11-20", reparse_to="2020-11-20").parsed == 1
    assert world.fetched == [collect.INDEX_URL]
    assert world.daily()[0]["prevailing"] == "110"


def test_reparse_range_only_selects_parsed_reports(world, tmp_path):
    parsed_url = world.add("Price-Monitoring-May-1-2025", rows=[nrow("Tomato", prevailing=100.0)])
    failed_url = world.add("Price-Monitoring-May-2-2025", rows=[])
    cache = tmp_path / "cache"
    assert world.run(cache_dir=cache).new == 2
    assert world.ledger().get(failed_url)["status"] == "failed"

    world.fetched.clear()
    stats = world.run(cache_dir=cache, reparse_from="2025-05-01", reparse_to="2025-05-02")

    assert (stats.new, stats.parsed, stats.failed) == (1, 1, 0)
    assert world.fetched == [collect.INDEX_URL]
    assert world.ledger().get(parsed_url)["status"] == "parsed"
    assert world.ledger().get(failed_url)["status"] == "failed"


def test_interrupt_after_download_recovers_from_cache_without_refetch(world, tmp_path):
    url = world.add("Price-Monitoring-March-21-2024", rows=[nrow("Tomato", prevailing=110.0)])
    cache = tmp_path / "cache"
    original_parse = world.parse

    def interrupted_parse(data):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        collect.run(world.data_dir, fetch=world.fetch, parse=interrupted_parse,
                    cache_dir=cache, delay=0)
    assert not world.ledger().has(url)
    world.fetched.clear()
    stats = collect.run(world.data_dir, fetch=world.fetch, parse=original_parse,
                        cache_dir=cache, delay=0)
    assert stats.parsed == 1
    assert world.fetched == [collect.INDEX_URL]


def test_second_collector_stops_before_fetching_index(world):
    lock_path = world.data_dir / ".collect.lock"
    with lock_path.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(collect.FetchError, match="collector already running"):
            world.run()
        assert world.fetched == []


def test_reparse_picks_up_new_aliases_without_refetching(world, tmp_path):
    url = world.add("Price-Monitoring-June-1-2026", rows=[nrow("Tomato", prevailing=60.0), nrow("Dragon Fruit", prevailing=200.0)])
    cache = tmp_path / "cache"
    world.run(cache_dir=cache)
    assert [r["commodity_id"] for r in world.daily()] == ["tomato"]
    csv_path = world.data_dir / "commodities.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8")
                        + "dragon_fruit,fruit,ドラゴンフルーツ,,Dragon fruit,Dragon Fruit,,1,480\n", encoding="utf-8")
    world.fetched.clear()
    world.run(cache_dir=cache, reparse_from="2026-06-01", reparse_to="2026-06-01")
    assert url not in world.fetched
    assert [r["commodity_id"] for r in world.daily()] == ["dragon_fruit", "tomato"]


def test_reparse_retires_newly_mapped_name_without_double_counting_others(world, tmp_path):
    world.add("Price-Monitoring-June-1-2026", rows=[nrow("Dragon Fruit", prevailing=200.0),
                                                   nrow("Premium", prevailing=50.0)])
    cache = tmp_path / "cache"
    world.run(cache_dir=cache)
    csv_path = world.data_dir / "commodities.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8")
                        + "dragon_fruit,fruit,ドラゴンフルーツ,,Dragon fruit,Dragon Fruit,,1,480\n", encoding="utf-8")
    world.run(cache_dir=cache, reparse_from="2026-06-01", reparse_to="2026-06-01")
    rows = (world.data_dir / "unmapped.csv").read_text(encoding="utf-8")
    assert "Dragon Fruit" not in rows
    assert "Premium,2026-06-01,2026-06-01,1," in rows
