"""Find schedule pages and the box-score links on them. Spec: docs/TASKS.md, Task 2."""

from __future__ import annotations

from ivydata.config import Config, School


def schedule_url_candidates(config: Config, school: School, season: int) -> list[str]:
    """Schedule-page URLs to try for (school, season), in order of preference.

    One URL per entry in ``school.season_slugs(season)``, formatted with
    ``config.schedule_pattern``.
    """
    raise NotImplementedError("Task 2")


def find_boxscore_links(schedule_html: str, page_url: str, boxscore_regex: str) -> list[str]:
    """Absolute, de-duplicated football box-score URLs found on a schedule page,
    in page order."""
    raise NotImplementedError("Task 2")


def crawl(
    config: Config,
    schools: list[str] | None = None,
    seasons: list[int] | None = None,
    refresh: bool = False,
) -> None:
    """Fetch every schedule page and every box score it links to; update the manifest.

    Resumable: everything already in the cache is reused unless ``refresh``.
    """
    raise NotImplementedError("Task 2")
