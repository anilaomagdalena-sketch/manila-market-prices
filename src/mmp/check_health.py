"""Check the freshness and parsing success of collected reports."""

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

from .ledger import Ledger


def check(entries: list[dict], today: date, *, since: str | None = None) -> list[str]:
    problems = []
    latest = max((row["report_date"] for row in entries if row["status"] == "parsed" and row["report_date"]), default="")
    if not latest or latest < (today - timedelta(days=14)).isoformat():
        problems.append(f"no parsed report in the last 14 days (latest: {latest or 'none'})")
    if since is not None:
        recent = [row for row in entries if row["fetched_at"] >= since and row["status"] in ("parsed", "failed")]
        failed = sum(row["status"] == "failed" for row in recent)
        if len(recent) >= 2 and failed * 2 >= len(recent):
            problems.append(f"{failed} of {len(recent)} newly fetched reports failed to parse")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--since")
    args = parser.parse_args(argv)
    problems = check(Ledger(args.data_dir / "sources.csv").entries(), datetime.now().date(), since=args.since)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
