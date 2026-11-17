"""Recover game box scores linked from the Ivy League's season statistics pages."""

from __future__ import annotations

import csv
import logging
import re
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qs, urldefrag, urljoin, urlsplit

import httpx
from selectolax.lexbor import LexborHTMLParser

from ivydata.config import REPO_ROOT, Config
from ivydata.crawl.discover import ERROR_COLUMNS, _record_robots
from ivydata.crawl.fetcher import Fetcher, RobotsDisallowed
from ivydata.crawl.manifest import Manifest
from ivydata.crawl.pages import challenge_provider
from ivydata.normalize.teams import canonical_team_id
from ivydata.parse.boxscore import TEAM_STAT_FIELDS, parse_boxscore

logger = logging.getLogger(__name__)
BASE = "https://ivyleague.com"


def find_league_boxscore_links(html: str, page_url: str, season: int) -> list[str]:
    """Read only game links, rejecting wrong-season/empty statistics indexes.

    Season leaders and cumulative statistics are never extracted. Query ids are
    opaque: deduplicate their decoded values without changing the returned URL.
    """
    doc = LexborHTMLParser(html)
    title = doc.css_first("title")
    if title is None or not re.search(
        rf"\b{season}\s+Football\s*-\s*Overall Statistics\b", title.text(), re.I
    ):
        raise ValueError(f"not a {season} football overall-statistics index: {page_url}")
    links: dict[tuple[str, str], str] = {}
    for anchor in doc.css("table a[href]"):
        url = urldefrag(urljoin(page_url, anchor.attributes["href"]))[0]
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        ids = query.get("id", [])
        if (
            parsed.scheme == "https"
            and parsed.netloc == "ivyleague.com"
            and parsed.path == "/boxscore.aspx"
            and query.get("path") == ["football"]
            and len(ids) == 1
            and ids[0].strip()
        ):
            links.setdefault((ids[0], "football"), url)
    if not links:
        raise ValueError(f"no football box-score links in {season} index: {page_url}")
    return list(links.values())


def crawl_league(config: Config, seasons: list[int], refresh: bool = False) -> None:
    """Fetch explicit seasons through Fetcher, preserving provenance and failures.

    The league is a source, not a ninth team. Box manifest rows use an Ivy team
    actually playing that game; index/robots rows use the source label ``league``.
    """
    years = sorted(set(seasons) - config.splits.skip_seasons, reverse=True)
    if set(years) - set(config.splits.seasons()):
        raise ValueError("league seasons must fall within configured splits")
    directory = REPO_ROOT / "data"
    manifest = Manifest(directory / "manifest/recovered/ivy_league_boxscores.csv")
    error_path = directory / "reports/league_recovery_errors.csv"
    errors: dict[str, dict[str, str]] = {}
    if error_path.exists():
        with error_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ERROR_COLUMNS:
                raise ValueError(f"invalid league recovery error columns: {error_path}")
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"invalid league recovery error row: {error_path}")
                errors[row["url"]] = row

    def save_errors() -> None:
        error_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=error_path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=ERROR_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(errors[url] for url in sorted(errors))
        temporary.replace(error_path)

    def failed(url: str, season: int, kind: str, error: str) -> None:
        logger.warning("%s: %s", url, error)
        errors[url] = dict(
            zip(ERROR_COLUMNS, (url, "league", str(season), kind, error), strict=True)
        )
        save_errors()

    fetcher = Fetcher(
        cache_dir=directory / "raw",
        user_agent=config.crawl.user_agent,
        min_delay_seconds=config.crawl.min_delay_seconds,
        timeout_seconds=config.crawl.timeout_seconds,
        max_retries=config.crawl.max_retries,
        refresh=refresh,
    )
    schools = {s.id for s in config.schools}
    try:
        for season in years:
            index_url = f"{BASE}/stats.aspx?path=football&year={season}"
            try:
                index = fetcher.get(index_url)
                manifest.record(index, "league", season, "league_index", str(season))
                manifest.save()
                if index.status != 200:
                    raise ValueError(f"unusable statistics index (HTTP {index.status})")
                links = find_league_boxscore_links(index.text(), index_url, season)
                errors.pop(index_url, None)
                save_errors()
            except (RobotsDisallowed, httpx.HTTPError, ValueError) as exc:
                failed(index_url, season, "league_index", str(exc))
                continue
            finally:
                _record_robots(directory / "raw", index_url, manifest, "league", season)
                manifest.save()
            print(f"Ivy League {season}: {len(links)} distinct game links", flush=True)
            for number, url in enumerate(links, 1):
                try:
                    result = fetcher.get(url)
                    errors[url] = dict(
                        zip(
                            ERROR_COLUMNS,
                            (
                                url,
                                "league",
                                str(season),
                                "boxscore",
                                "box-score validation pending",
                            ),
                            strict=True,
                        )
                    )
                    save_errors()
                    manifest.record(result, "league", season, "league_rejected", str(season))
                    manifest.save()
                    if result.status != 200 or challenge_provider(result.text()):
                        raise ValueError(f"unusable box score (HTTP {result.status})")
                    box = parse_boxscore(result.text(), url)
                    day = date.fromisoformat(box.game["date"] or "")
                    teams = {
                        canonical_team_id(box.game[k] or "", config.team_aliases)
                        for k in ("home_raw", "away_raw")
                    }
                    ivy = sorted(teams & schools)
                    if day.year - (day.month <= 3) != season or len(teams) != 2 or not ivy:
                        raise ValueError("box-score season/teams do not match league selection")
                    if any(box.game[k] is None for k in ("home_pts", "away_pts")) or not all(
                        any(team[k] is not None for k in TEAM_STAT_FIELDS)
                        for team in box.team_stats
                    ):
                        raise ValueError("box score lacks finals or statistics for both teams")
                    manifest.record(result, ivy[0], season, "boxscore", str(season))
                    manifest.save()
                    errors.pop(url, None)
                    save_errors()
                    print(f"  {number}/{len(links)}: {day} {' / '.join(sorted(teams))}", flush=True)
                except (RobotsDisallowed, httpx.HTTPError, ValueError) as exc:
                    failed(url, season, "boxscore", str(exc))
    finally:
        fetcher.close()
        manifest.save()
        save_errors()
