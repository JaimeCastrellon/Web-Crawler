"""Command line: ``python -m ivydata <command>``."""

from __future__ import annotations

import argparse
import shutil

import httpx
import yaml

from ivydata.config import REPO_ROOT, Config, load_config
from ivydata.crawl.fetcher import Fetcher, RobotsDisallowed


def _capture_fixtures(config: Config, *, refresh: bool) -> int:
    directory = REPO_ROOT / "tests" / "fixtures"
    entries = yaml.safe_load((directory / "fixtures.yaml").read_text(encoding="utf-8"))
    fetcher = Fetcher(
        cache_dir=REPO_ROOT / "data" / "raw",
        user_agent=config.crawl.user_agent,
        min_delay_seconds=config.crawl.min_delay_seconds,
        timeout_seconds=config.crawl.timeout_seconds,
        max_retries=config.crawl.max_retries,
        refresh=refresh,
    )
    print(f"{'name':<40} {'status':<12} bytes")
    try:
        for name, url in entries.items():
            if not isinstance(name, str) or not name.replace("_", "").isalnum():
                raise ValueError(f"invalid fixture name: {name!r}")
            try:
                result = fetcher.get(url)
            except (RobotsDisallowed, httpx.HTTPError) as exc:
                print(f"{name:<40} {'ERROR':<12} -  {url}: {exc}")
                continue
            size = result.path.stat().st_size if result.path is not None else 0
            print(f"{name:<40} {result.status:<12} {size}")
            if result.status == 200 and result.path is not None:
                shutil.copyfile(result.path, directory / f"{name}.html")
            else:
                print(f"  not saved: {url} (HTTP {result.status})")
    finally:
        fetcher.close()
    return 0


def _seasons(arg: str | None) -> list[int] | None:
    if not arg:
        return None
    if "-" in arg:
        lo, hi = arg.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in arg.split(",")]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ivydata", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("config", help="print the loaded configuration summary")
    f = sub.add_parser("fixtures", help="save test fixture pages (needs internet)")
    f.add_argument("--refresh", action="store_true", help="re-fetch even if cached")

    c = sub.add_parser("crawl", help="fetch schedules and box scores (Task 2)")
    c.add_argument("--schools", help="comma-separated ids, default all")
    c.add_argument("--seasons", help="e.g. 2000-2026 or 2024,2025; default from splits.yaml")
    c.add_argument("--refresh", action="store_true", help="re-fetch even if cached")

    sub.add_parser("coverage", help="write data/reports/coverage_report.csv (Task 3)")
    sub.add_parser("build", help="parse + merge + write data/processed/ (Task 7)")
    sub.add_parser("validate", help="write data/reports/validation_report.md (Task 8)")

    args = p.parse_args(argv)
    config = load_config()

    if args.cmd == "fixtures":
        return _capture_fixtures(config, refresh=args.refresh)

    if args.cmd == "config":
        seasons = config.splits.seasons()
        print(
            f"{len(config.schools)} schools, seasons {seasons[0]}-{seasons[-1]} "
            f"({len(seasons)} seasons, skipping {sorted(config.splits.skip_seasons)})"
        )
        for s in config.schools:
            flag = "" if s.verified else "  (unverified)"
            print(f"  {s.id:<10} {s.base_url}{flag}")
        for name, (lo, hi) in config.splits.ranges.items():
            print(f"  split {name:<8} {lo}-{hi}")
        return 0

    if args.cmd == "crawl":
        from ivydata.crawl.discover import crawl

        schools = args.schools.split(",") if args.schools else None
        crawl(config, schools=schools, seasons=_seasons(args.seasons), refresh=args.refresh)
        return 0

    raise NotImplementedError(f"`{args.cmd}` is not implemented yet — see docs/TASKS.md")


if __name__ == "__main__":
    raise SystemExit(main())
