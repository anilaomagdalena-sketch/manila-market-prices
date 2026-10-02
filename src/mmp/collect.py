"""Fetch and parse new DA price reports without fetching known URLs again."""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
from functools import wraps
import hashlib
import os
from pathlib import Path
import time
from typing import Callable

import requests

from .ledger import Ledger
from .links import START_DATE, Link, extract_links
from .names import NameMap
from .parsers.pdf import ParseResult, parse_pdf
from .store import DailyStore, MarketStore, RejectedLog, UnmappedLog


INDEX_URL = "https://www.da.gov.ph/price-monitoring/"
MIN_LINKS = 1000
USER_AGENT = "manila-market-prices/1.0 (+https://github.com/anilaomagdalena-sketch/manila-market-prices)"


class FetchError(Exception):
    pass


@dataclass
class Stats:
    new: int = 0
    parsed: int = 0
    failed: int = 0
    skipped: int = 0
    fetch_errors: int = 0


def http_fetch(url: str) -> bytes:
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise FetchError(str(last_error))


def _priority(entry: dict) -> int:
    return (2 if entry["kind"] == "price_monitoring" else 0) + (1 if str(entry["revised"]) in ("1", "True", "true") else 0)


def _entry(link: Link, now: datetime, **changes) -> dict:
    result = dict(url=link.url, kind=link.kind, revised="1" if link.revised else "0",
                  report_date=link.report_date.isoformat() if link.report_date else "",
                  status="", layout="", rows="", sha256="", fetched_at="", error="")
    result.update(changes)
    return result


def _candidate_key(link: Link):
    return (link.report_date is None, link.report_date or START_DATE,
            0 if link.kind == "price_monitoring" else 1, link.revised, link.url)


def _representative(row: dict) -> float | None:
    for key in ("prevailing", "average"):
        if row.get(key) is not None:
            return float(row[key])
    if row.get("low") is not None and row.get("high") is not None:
        return (float(row["low"]) + float(row["high"])) / 2
    return None


def _load_pdf(link: Link, old: dict | None, cache_dir: Path | None, fetch, *, cache_only=False) -> tuple[bytes, bool]:
    cached_sha = old.get("sha256") if old else ""
    if cache_dir and not cached_sha:
        cached_sha = _cache_index(cache_dir).get(link.url, "")
    if cache_dir and cached_sha:
        cached = cache_dir / f"{cached_sha[:16]}.pdf"
        if cached.exists():
            return cached.read_bytes(), True
    if cache_only:
        raise FetchError("cached PDF is unavailable")
    data = fetch(link.url)
    if not data.startswith(b"%PDF"):
        raise FetchError("response is not a PDF")
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(data).hexdigest()
        (cache_dir / f"{digest[:16]}.pdf").write_bytes(data)
        _remember_cache(cache_dir, link.url, digest)
    return data, False


def _cache_index(cache_dir: Path) -> dict[str, str]:
    path = cache_dir / "url-sha.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["url"]: row["sha256"] for row in csv.DictReader(handle)}


def _remember_cache(cache_dir: Path, url: str, digest: str) -> None:
    entries = _cache_index(cache_dir)
    entries[url] = digest
    path = cache_dir / "url-sha.csv"
    temp = cache_dir / "url-sha.tmp"
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("url", "sha256"), lineterminator="\n")
        writer.writeheader()
        writer.writerows({"url": key, "sha256": value} for key, value in sorted(entries.items()))
    os.replace(temp, path)


def _single_collector(function):
    @wraps(function)
    def locked(data_dir: Path, **kwargs):
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        with (data_dir / ".collect.lock").open("a+") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise FetchError("collector already running") from error
            try:
                return function(data_dir, **kwargs)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    return locked


@_single_collector
def run(data_dir: Path, *, fetch: Callable[[str], bytes] = http_fetch,
        parse: Callable[[bytes], ParseResult] = parse_pdf, max_new: int | None = None,
        retry_failed: bool = False, delay: float = 3.0, cache_dir: Path | None = None,
        checkpoint_every: int = 25, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        reparse_from: str | None = None, reparse_to: str | None = None) -> Stats:
    data_dir = Path(data_dir)
    cache_dir = Path(cache_dir) if cache_dir is not None else None
    try:
        links = extract_links(fetch(INDEX_URL).decode("utf-8", errors="replace"))
    except FetchError:
        raise
    except Exception as error:
        raise FetchError(str(error)) from error
    if len(links) < MIN_LINKS:
        raise FetchError("index looks broken")

    ledger = Ledger(data_dir / "sources.csv")
    daily = DailyStore(data_dir / "daily.csv")
    markets = MarketStore(data_dir / "market_daily.csv")
    unmapped = UnmappedLog(data_dir / "unmapped.csv")
    rejected = RejectedLog(data_dir / "rejected.csv")
    names = NameMap(data_dir / "commodities.csv")
    stats = Stats()

    def checkpoint():
        daily.save()
        markets.save()
        unmapped.save()
        rejected.save()
        ledger.save()

    candidates = []
    reparse = reparse_from is not None or reparse_to is not None
    for link in links:
        old = ledger.get(link.url)
        if reparse:
            if old and old["status"] == "parsed" and old["sha256"] and old["report_date"] and (reparse_from is None or old["report_date"] >= reparse_from) and (reparse_to is None or old["report_date"] <= reparse_to):
                candidates.append(link)
            continue
        if old and not (retry_failed and old["status"] == "failed"):
            continue
        if link.kind == "skip" or (link.report_date and link.report_date < START_DATE):
            reason = "not_a_price_report" if link.kind == "skip" else "before_start_date"
            ledger.put(_entry(link, now(), status="skipped", error=reason))
            stats.skipped += 1
        else:
            candidates.append(link)
    candidates.sort(key=_candidate_key)

    for link in candidates:
        if max_new is not None and stats.new >= max_new:
            break
        date = link.report_date.isoformat() if link.report_date else ""
        if link.kind == "daily_price_index" and date and any(
            e["report_date"] == date and e["kind"] == "price_monitoring" and e["status"] == "parsed"
            for e in ledger.entries()
        ):
            ledger.put(_entry(link, now(), status="skipped", error="pm_exists"))
            stats.skipped += 1
            continue
        old = ledger.get(link.url)
        try:
            data, cached = _load_pdf(link, old, cache_dir, fetch, cache_only=reparse)
        except FetchError:
            stats.fetch_errors += 1
            continue
        stats.new += 1
        digest = hashlib.sha256(data).hexdigest()
        metadata = dict(sha256=digest, fetched_at=now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
        try:
            result = parse(data)
        except Exception as error:
            message = f"{type(error).__name__}: {str(error).splitlines()[0]}"
            ledger.put(_entry(link, now(), status="failed", error=message, **metadata))
            stats.failed += 1
        else:
            report_date = link.report_date or result.report_date
            if report_date is None:
                ledger.put(_entry(link, now(), status="failed", error="no_date", **metadata))
                stats.failed += 1
            elif report_date < START_DATE:
                ledger.put(_entry(link, now(), status="skipped", report_date=report_date.isoformat(), error="before_start_date", **metadata))
                stats.skipped += 1
            elif not result.rows:
                ledger.put(_entry(link, now(), status="failed", report_date=report_date.isoformat(), error="no_rows", **metadata))
                stats.failed += 1
            else:
                date = report_date.isoformat()
                mismatch = f"date_mismatch body={result.report_date}" if link.report_date and result.report_date and link.report_date != result.report_date else ""
                _store_result(link, result, date, names, daily, markets, unmapped, rejected, ledger,
                              metadata, mismatch, now(), reparse=reparse)
                if ledger.get(link.url)["status"] == "parsed":
                    stats.parsed += 1
                else:
                    stats.skipped += 1
        if stats.new % checkpoint_every == 0:
            checkpoint()
        if not cached and delay:
            time.sleep(delay)

    if reparse:
        unmapped.retire_mapped(names.lookup, reparse_from, reparse_to)
    checkpoint()
    return stats


def _store_result(link, result, date, names, daily, markets, unmapped, rejected, ledger, metadata,
                  mismatch, current_time, *, reparse=False):
    existing = next((row for row in daily.rows() if row["date"] == date), None)
    previous = ledger.get(existing["source_url"]) if existing else None
    if previous and _priority(previous) > _priority(_entry(link, current_time)):
        ledger.put(_entry(link, current_time, report_date=date, status="superseded", error=mismatch, **metadata))
        return

    if reparse:
        rejected.remove_source(link.url)
    rows = []
    seen = set()
    for row in result.rows:
        cid = names.lookup(row["raw_name"], row.get("spec", ""))
        if cid is None:
            if not reparse:
                unmapped.add(row["raw_name"], date, link.url)
            continue
        if cid in seen:
            continue
        seen.add(cid)
        value = _representative(row)
        previous_value = daily.last_price(cid, before=date)
        if value is not None and (value <= 0 or (previous_value is not None and
                                (value > previous_value * 5 or value < previous_value / 5))):
            reason = "non_positive" if value <= 0 else "jump"
            rejected.add(date, cid, value, previous_value, reason, link.url)
            continue
        rows.append(dict(commodity_id=cid, spec=row.get("spec", ""), unit=row.get("unit", ""),
                         low=row.get("low"), high=row.get("high"), prevailing=row.get("prevailing"),
                         average=row.get("average"), source_url=link.url))

    market_rows = []
    market_seen = set()
    for row in result.market_rows:
        if not row["market"].startswith("Cartimar"):
            continue
        cid = names.lookup(row["raw_name"])
        if cid is None or cid in market_seen:
            continue
        market_seen.add(cid)
        market_rows.append(dict(market="Cartimar", commodity_id=cid, low=row["low"],
                                high=row["high"], price=row["price"], source_url=link.url))

    daily.replace_date(date, rows)
    markets.replace_date(date, market_rows)
    if previous:
        ledger.put({**previous, "status": "superseded"})
    layout = "+".join(sorted(set(result.layouts) - {"skip"}))
    ledger.put(_entry(link, current_time, report_date=date, status="parsed", layout=layout,
                      rows=str(len(rows)), error=mismatch, **metadata))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--max-new", type=int)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/pdf"))
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--reparse-from")
    parser.add_argument("--reparse-to")
    args = parser.parse_args(argv)
    try:
        stats = run(args.data_dir, max_new=args.max_new, retry_failed=args.retry_failed,
                    cache_dir=args.cache_dir, delay=args.delay,
                    reparse_from=args.reparse_from, reparse_to=args.reparse_to)
    except FetchError as error:
        print(f"FetchError: {error}")
        return 1
    print(f"new={stats.new} parsed={stats.parsed} failed={stats.failed} skipped={stats.skipped} fetch_errors={stats.fetch_errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
