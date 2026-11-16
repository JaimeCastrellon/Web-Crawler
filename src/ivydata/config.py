"""Load and validate the YAML files in config/."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


@dataclass(frozen=True)
class School:
    id: str
    name: str
    base_url: str
    season_slug_patterns: tuple[str, ...]
    verified: bool = False

    def season_slugs(self, season: int) -> list[str]:
        """Candidate season slugs for this school, in the order to try them."""
        next_yy = f"{(season + 1) % 100:02d}"
        return [p.format(year=season, next_yy=next_yy) for p in self.season_slug_patterns]


@dataclass(frozen=True)
class CrawlSettings:
    user_agent: str
    min_delay_seconds: float
    timeout_seconds: float
    max_retries: int


@dataclass(frozen=True)
class Splits:
    first_season: int
    last_season: int
    skip_seasons: frozenset[int]
    ranges: dict[str, tuple[int, int]] = field(default_factory=dict)

    def seasons(self) -> list[int]:
        return [
            s for s in range(self.first_season, self.last_season + 1) if s not in self.skip_seasons
        ]

    def split_for(self, season: int) -> str:
        for name, (lo, hi) in self.ranges.items():
            if lo <= season <= hi:
                return name
        raise ValueError(f"season {season} is not in any split")


@dataclass(frozen=True)
class Config:
    crawl: CrawlSettings
    schedule_pattern: str
    boxscore_regex: str
    schools: tuple[School, ...]
    splits: Splits
    team_aliases: dict[str, str]  # lowercased raw name -> canonical id

    def school(self, school_id: str) -> School:
        for s in self.schools:
            if s.id == school_id:
                return s
        raise KeyError(school_id)


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(config_dir: Path = CONFIG_DIR) -> Config:
    src = _read(config_dir / "sources.yaml")
    spl = _read(config_dir / "splits.yaml")
    aliases_raw = _read(config_dir / "team_aliases.yaml")

    default_patterns = tuple(src["default_season_slug_patterns"])
    schools = tuple(
        School(
            id=s["id"],
            name=s["name"],
            base_url=s["base_url"].rstrip("/"),
            season_slug_patterns=tuple(s.get("season_slug_patterns", default_patterns)),
            verified=bool(s.get("verified", False)),
        )
        for s in src["schools"]
    )

    c = src["crawl"]
    crawl = CrawlSettings(
        user_agent=c["user_agent"],
        min_delay_seconds=float(c["min_delay_seconds"]),
        timeout_seconds=float(c["timeout_seconds"]),
        max_retries=int(c["max_retries"]),
    )
    if crawl.min_delay_seconds < 3.0:
        raise ValueError("crawl.min_delay_seconds must be >= 3.0 (see AGENTS.md)")

    splits = Splits(
        first_season=int(spl["first_season"]),
        last_season=int(spl["last_season"]),
        skip_seasons=frozenset(spl.get("skip_seasons", [])),
        ranges={k: (int(v["from"]), int(v["to"])) for k, v in spl["splits"].items()},
    )

    aliases: dict[str, str] = {}
    for canonical, names in aliases_raw.items():
        aliases[canonical.lower()] = canonical
        for n in names:
            key = str(n).strip().lower()
            if key in aliases and aliases[key] != canonical:
                raise ValueError(f"alias {n!r} maps to both {aliases[key]} and {canonical}")
            aliases[key] = canonical

    return Config(
        crawl=crawl,
        schedule_pattern=src["url_patterns"]["schedule"],
        boxscore_regex=src["url_patterns"]["boxscore_regex"],
        schools=schools,
        splits=splits,
        team_aliases=aliases,
    )
