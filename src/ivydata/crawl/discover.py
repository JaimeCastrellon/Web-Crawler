"""Find schedule pages and the box-score links on them. Spec: docs/TASKS.md, Task 2."""

from __future__ import annotations

import csv
import json
import logging
import re
from hashlib import sha1
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urldefrag, urljoin, urlsplit

import httpx
from selectolax.lexbor import LexborHTMLParser

from ivydata.config import REPO_ROOT, Config, School
from ivydata.crawl.fetcher import Fetcher, FetchResult, RobotsDisallowed
from ivydata.crawl.manifest import Manifest
from ivydata.crawl.pages import challenge_provider, declared_schedule_season, has_schedule_games

logger = logging.getLogger(__name__)
ERROR_COLUMNS = ["url", "school", "season", "kind", "error"]


def schedule_url_candidates(config: Config, school: School, season: int) -> list[str]:
    """Schedule-page URLs to try for (school, season), in order of preference.

    One URL per entry in ``school.season_slugs(season)``, formatted with
    ``config.schedule_pattern``.
    """
    return [
        config.schedule_pattern.format(base_url=school.base_url, season_slug=slug)
        for slug in school.season_slugs(season)
    ]


def find_boxscore_links(schedule_html: str, page_url: str, boxscore_regex: str) -> list[str]:
    """Absolute, de-duplicated football box-score URLs found on a schedule page,
    in page order."""
    pattern = re.compile(boxscore_regex)
    links: dict[str, None] = {}
    for anchor in LexborHTMLParser(schedule_html).css("a[href]"):
        url = urldefrag(urljoin(page_url, anchor.attributes["href"]))[0]
        parsed = urlsplit(url)
        if (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and pattern.fullmatch(parsed.path.rstrip("/"))
        ):
            links[url] = None
    return list(links)


def _record_robots(cache_dir: Path, url: str, manifest: Manifest, school: str, season: int) -> None:
    """Read robots provenance already written by Fetcher; never make an extra request."""
    parsed = httpx.URL(url)
    robots_url = str(parsed.copy_with(path="/robots.txt", query=None, fragment=None))
    stem = sha1(robots_url.encode()).hexdigest()
    sidecar = cache_dir / parsed.host / f"{stem}.json"
    body = sidecar.with_suffix(".html")
    if sidecar.exists() and body.exists():
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        manifest.record(
            FetchResult(
                robots_url,
                metadata["status"],
                body,
                metadata["sha256"],
                True,
                metadata["fetched_at"],
            ),
            school,
            season,
            "robots",
        )


def crawl(
    config: Config,
    schools: list[str] | None = None,
    seasons: list[int] | None = None,
    refresh: bool = False,
) -> None:
    """Fetch every schedule page and every box score it links to; update the manifest.

    Resumable: everything already in the cache is reused unless ``refresh``.
    """
    selected = set(schools) if schools is not None else {school.id for school in config.schools}
    unknown = selected - {school.id for school in config.schools}
    if unknown:
        raise ValueError(f"unknown schools: {', '.join(sorted(unknown))}")
    years = sorted(
        set(config.splits.seasons() if seasons is None else seasons) - config.splits.skip_seasons
    )
    cache_dir = REPO_ROOT / "data" / "raw"
    manifest = Manifest(REPO_ROOT / "data" / "manifest" / "urls.csv")
    error_path = REPO_ROOT / "data" / "reports" / "crawl_errors.csv"
    errors: dict[str, dict[str, str]] = {}
    if error_path.exists():
        with error_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ERROR_COLUMNS:
                raise ValueError(f"invalid crawl error columns: {error_path}")
            errors = {row["url"]: row for row in reader}

    def save_errors() -> None:
        error_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=error_path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                writer = csv.DictWriter(stream, fieldnames=ERROR_COLUMNS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(
                    sorted(
                        errors.values(),
                        key=lambda row: (
                            row["school"],
                            int(row["season"]),
                            row["kind"],
                            row["url"],
                        ),
                    )
                )
            temporary.replace(error_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def failed(url: str, school: str, season: int, kind: str, error: str) -> None:
        logger.warning("%s: %s", url, error)
        errors[url] = dict(zip(ERROR_COLUMNS, (url, school, str(season), kind, error), strict=True))
        save_errors()

    fetcher = Fetcher(
        cache_dir=cache_dir,
        user_agent=config.crawl.user_agent,
        min_delay_seconds=config.crawl.min_delay_seconds,
        timeout_seconds=config.crawl.timeout_seconds,
        max_retries=config.crawl.max_retries,
        refresh=refresh,
    )

    def capture(url: str, school: str, season: int, kind: str, slug: str) -> FetchResult | None:
        try:
            result = fetcher.get(url)
        except (httpx.HTTPError, RobotsDisallowed) as exc:
            failed(url, school, season, kind, f"{type(exc).__name__}: {exc}")
            return None
        finally:
            _record_robots(cache_dir, url, manifest, school, season)
            manifest.save()
        manifest.record(result, school, season, kind, slug)
        manifest.save()
        if result.status != 200:
            failed(url, school, season, kind, f"HTTP {result.status}")
            return None
        provider = challenge_provider(result.text())
        if provider:
            failed(url, school, season, kind, f"{provider} bot challenge")
            return None
        if url in errors:
            del errors[url]
            save_errors()
        return result

    try:
        for school in config.schools:
            if school.id not in selected:
                continue
            for season in years:
                candidates = schedule_url_candidates(config, school, season)
                for slug, url in zip(school.season_slugs(season), candidates, strict=True):
                    result = capture(url, school.id, season, "schedule", slug)
                    if result is None:
                        continue
                    html = result.text()
                    declared = declared_schedule_season(html)
                    if declared is not None and declared != season:
                        failed(
                            url,
                            school.id,
                            season,
                            "schedule",
                            f"page declares season {declared}, expected {season}",
                        )
                        continue
                    if not has_schedule_games(html):
                        failed(url, school.id, season, "schedule", "no recognizable schedule games")
                        continue
                    links = find_boxscore_links(html, url, config.boxscore_regex)
                    print(f"{school.id} {season}: {len(links)} box-score links from {url}")
                    for link in links:
                        capture(link, school.id, season, "boxscore", slug)
                    break
                else:
                    logger.warning("No usable schedule for %s %s", school.id, season)
    finally:
        fetcher.close()
        manifest.save()
        save_errors()
