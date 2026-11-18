"""Pipeline orchestration: parse cache -> merge -> pre-game records -> splits -> CSVs.
Spec: docs/TASKS.md, Task 7.
"""

from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from datetime import date
from hashlib import sha1, sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import pandas as pd

from ivydata.config import Config
from ivydata.crawl.manifest import MANIFEST_COLUMNS
from ivydata.crawl.pages import challenge_provider
from ivydata.normalize.curated import load_reviewed_boxscores
from ivydata.normalize.merge import merge_games
from ivydata.normalize.reviews import apply_box_date_review, load_box_date_reviews
from ivydata.normalize.teams import is_ivy
from ivydata.parse.boxscore import TEAM_STAT_FIELDS, parse_boxscore
from ivydata.parse.schedule import parse_schedule

if TYPE_CHECKING:
    from ivydata.scores import ExportParse

logger = logging.getLogger(__name__)
PREGAME_FIELDS = [
    "games_before",
    "wins_before",
    "losses_before",
    "ties_before",
    "ivy_wins_before",
    "ivy_losses_before",
]
GAME_COLUMNS = [
    "game_id",
    "season",
    "date",
    "home_team",
    "away_team",
    "neutral_site",
    "stadium",
    "city",
    "home_pts",
    "away_pts",
    *[f"{s}_q{i}" for s in ("home", "away") for i in range(1, 5)],
    "home_ot",
    "away_ot",
    "num_ot",
    "ivy_game",
    "attendance",
    "stats_level",
    "split",
    "sources_agree",
    "source_urls",
]
TEAM_COLUMNS = [
    "game_id",
    "season",
    "date",
    "split",
    "stats_level",
    "team",
    "opponent",
    "is_home",
    "neutral_site",
    "points",
    "points_allowed",
    *PREGAME_FIELDS,
    *TEAM_STAT_FIELDS,
    "turnovers",
]
BOOL_COLUMNS = {"neutral_site", "ivy_game", "sources_agree", "is_home"}
WARNING_COLUMNS = ["source_url", "message"]


def _iso_day(value: str) -> date:
    day = date.fromisoformat(value)
    if day.isoformat() != value:
        raise ValueError(f"expected ISO date, got {value!r}")
    return day


def add_pregame_records(team_stats: pd.DataFrame) -> pd.DataFrame:
    """Add games_before, wins_before, losses_before, ties_before, ivy_wins_before,
    ivy_losses_before — counting ONLY the team's earlier games in the same season."""
    required = {"date", "game_id", "season", "team", "opponent", "points", "points_allowed"}
    if not required.issubset(team_stats.columns):
        raise ValueError(
            f"missing pre-game input columns: {sorted(required - set(team_stats.columns))}"
        )
    result = team_stats.copy()
    if result[list(required - {"points", "points_allowed"})].isna().any().any():
        raise ValueError("missing game/team/date identity in pre-game input")
    if result.duplicated(["game_id", "team"]).any():
        raise ValueError("duplicate game/team rows in pre-game input")
    for value in result["date"]:
        _iso_day(value)
    result = result.sort_values(["date", "game_id", "team"], kind="stable").reset_index(drop=True)
    records = {key: [] for key in PREGAME_FIELDS}
    counts: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0] * len(PREGAME_FIELDS))
    # Game times are not part of the schema. Batch each date so that another
    # result on the same day can never leak through an arbitrary game-id order.
    for _, day_rows in result.groupby("date", sort=True):
        for row in day_rows.itertuples(index=False):
            previous = counts[(row.season, row.team)]
            for key, value in zip(PREGAME_FIELDS, previous, strict=True):
                records[key].append(value if is_ivy(row.team) else None)
        for row in day_rows.itertuples(index=False):
            if not is_ivy(row.team) or pd.isna(row.points) or pd.isna(row.points_allowed):
                continue
            counter = counts[(row.season, row.team)]
            counter[0] += 1
            if row.points > row.points_allowed:
                counter[1] += 1
                counter[4] += is_ivy(row.team) and is_ivy(row.opponent)
            elif row.points < row.points_allowed:
                counter[2] += 1
                counter[5] += is_ivy(row.team) and is_ivy(row.opponent)
            else:
                counter[3] += 1
    for key, values in records.items():
        result[key] = pd.Series(values, dtype="Int64")
    return result


def assign_splits(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Add the ``split`` column from config.splits."""
    if "season" not in df or df["season"].isna().any():
        raise ValueError("split assignment requires nonmissing seasons")
    result = df.copy()
    for season in result["season"]:
        if isinstance(season, bool) or int(season) != season:
            raise ValueError(f"invalid season: {season!r}")
    result = result[~result["season"].isin(config.splits.skip_seasons)].copy()
    labels = {}
    for season in result["season"].unique():
        if not config.splits.first_season <= season <= config.splits.last_season:
            raise ValueError(f"season {season} is outside configured range")
        matching = [name for name, (lo, hi) in config.splits.ranges.items() if lo <= season <= hi]
        if len(matching) != 1:
            raise ValueError(f"season {season} must belong to exactly one split")
        labels[season] = matching[0]
    result["split"] = result["season"].map(labels)
    return result


def _manifest_rows(raw_dir: Path, config: Config) -> list[dict[str, str]]:
    directory = raw_dir.parent / "manifest"
    paths = [directory / "urls.csv", *sorted((directory / "recovered").glob("*.csv"))]
    if not any(path.exists() for path in paths):
        raise FileNotFoundError(f"no URL manifests found in {directory}")
    rows = {}
    allowed = set(config.splits.seasons())
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != MANIFEST_COLUMNS:
                raise ValueError(f"invalid manifest columns: {path}")
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"invalid manifest row: {path}")
                if int(row["season"]) not in allowed or row["kind"] not in ("schedule", "boxscore"):
                    continue
                config.school(row["school"])
                url = row["url"]
                if urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).hostname:
                    raise ValueError(f"invalid manifest URL: {url!r}")
                identity = ("kind", "season", "status", "sha256")
                if row["kind"] == "schedule":
                    identity += ("school",)
                if url in rows and any(row[key] != rows[url][key] for key in identity):
                    raise ValueError(f"conflicting manifest entries for {url}")
                rows[url] = row
    return [rows[key] for key in sorted(rows)]


def _csv_text(frame: pd.DataFrame, columns: list[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in frame.reindex(columns=columns).to_dict(orient="records"):
        writer.writerow(
            {
                key: ""
                if pd.isna(value)
                else ("true" if value else "false")
                if key in BOOL_COLUMNS
                else value
                for key, value in row.items()
            }
        )
    return stream.getvalue()


def _publish(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def build(raw_dir: Path, out_dir: Path, config: Config) -> None:
    """Write games.csv, team_game_stats.csv and train/ test/ current/ subfolders.
    Deterministic: same raw cache -> byte-identical output."""
    from ivydata.scores import default_export_paths, load_score_exports

    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    parsed = load_score_exports(default_export_paths(raw_dir.parent / "sources"), config)
    _build(raw_dir, out_dir, config, parsed)


def _build(raw_dir: Path, out_dir: Path, config: Config, exported: ExportParse) -> dict:
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    if raw_dir.resolve() == out_dir.resolve() or raw_dir.resolve() in out_dir.resolve().parents:
        raise ValueError("output directory must be outside the raw cache")
    if any(
        not name or Path(name).name != name or name in (".", "..") for name in config.splits.ranges
    ):
        raise ValueError("split names must be single directory names")
    manifest_dir = raw_dir.parent / "manifest"
    has_manifest = (manifest_dir / "urls.csv").exists() or any(
        (manifest_dir / "recovered").glob("*.csv")
    )
    rows = _manifest_rows(raw_dir, config) if has_manifest or not exported.rows else []
    date_reviews = load_box_date_reviews(raw_dir.parent / "manifest/reviewed_box_dates.csv")
    warnings: list[dict[str, str]] = []
    cache_errors = []
    boxes, schedules = [], list(exported.rows)
    reviewed_error = None

    def warn(url: str, message: str) -> None:
        logger.warning("%s: %s", url, message)
        warnings.append({"source_url": url, "message": message})

    try:
        boxes = load_reviewed_boxscores(manifest_dir / "reviewed_boxscores.json", raw_dir, config)
    except (ValueError, OSError) as exc:
        reviewed_error = exc
        warn("", f"reviewed PDF evidence rejected: {exc}")

    for message in exported.warnings:
        warn("", message)
    recovery_errors = [
        raw_dir.parent / "reports/league_recovery_errors.csv",
        *sorted((raw_dir.parent / "reports/recovery_errors").glob("*.csv")),
    ]
    for error_path in recovery_errors:
        if not error_path.exists():
            continue
        with error_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["url", "school", "season", "kind", "error"]:
                raise ValueError(f"invalid recovery error columns: {error_path}")
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"invalid recovery error row: {error_path}")
                if int(row["season"]) in config.splits.seasons():
                    source = "Ivy League" if row["school"] == "league" else row["school"]
                    warn(row["url"], f"{source} recovery: {row['error']}")
    for row in rows:
        url = row["url"]
        if row["status"] != "200":
            warn(url, f"HTTP {row['status']}; cached failure excluded")
            continue
        path = raw_dir / urlsplit(url).hostname / f"{sha1(url.encode()).hexdigest()}.html"
        try:
            content = path.read_bytes()
        except OSError as exc:
            message = f"cached body unavailable ({type(exc).__name__}); crawl it before building"
            warn(url, message)
            cache_errors.append(url)
            continue
        if sha256(content).hexdigest() != row["sha256"]:
            warn(url, "cache checksum mismatch; explicit refresh/recovery required")
            cache_errors.append(url)
            continue
        html = content.decode("utf-8", errors="replace")
        provider = challenge_provider(html)
        if provider or content.startswith(b"%PDF"):
            warn(
                url,
                f"{provider} bot challenge" if provider else "PDF box scores are not yet supported",
            )
            continue
        if row["kind"] == "schedule":
            parsed = parse_schedule(html, row["school"], int(row["season"]), url)
            schedules.extend(parsed.rows)
            for message in parsed.warnings:
                warn(url, message)
        else:
            box = parse_boxscore(html, url)
            if url in date_reviews:
                warn(url, apply_box_date_review(box, date_reviews[url], raw_dir, config))
            day = box.game["date"]
            if day is not None and _iso_day(day).year - (_iso_day(day).month <= 3) != int(
                row["season"]
            ):
                warn(url, f"box-score date {day} conflicts with manifest season {row['season']}")
                continue
            boxes.append(box)
    merged = merge_games(boxes, schedules, config.team_aliases)
    for message in merged.conflicts:
        warn("", message)
    report = (
        pd.DataFrame(warnings, columns=WARNING_COLUMNS)
        .drop_duplicates()
        .sort_values(WARNING_COLUMNS)
    )
    _publish(raw_dir.parent / "reports/build_warnings.csv", _csv_text(report, WARNING_COLUMNS))
    if reviewed_error is not None:
        raise ValueError(
            f"{reviewed_error}; processed files were not replaced; see build_warnings.csv"
        ) from reviewed_error
    if cache_errors:
        raise ValueError(
            f"{len(cache_errors)} missing/corrupt successful cache entries; "
            "processed files were not replaced; see build_warnings.csv"
        )
    if (rows or exported.rows or boxes) and not merged.games:
        raise ValueError(
            "no usable games in selected sources; processed files were not replaced; "
            "see build_warnings.csv"
        )
    games = assign_splits(
        pd.DataFrame(merged.games, columns=[k for k in GAME_COLUMNS if k != "split"], dtype=object),
        config,
    )
    teams = pd.DataFrame(
        merged.team_stats,
        columns=[k for k in TEAM_COLUMNS if k not in (*PREGAME_FIELDS, "split", "turnovers")],
        dtype=object,
    )
    teams = assign_splits(add_pregame_records(teams), config)
    teams["turnovers"] = [
        int(a) + int(b) if pd.notna(a) and pd.notna(b) else None
        for a, b in zip(teams["pass_int"], teams["fumbles_lost"], strict=True)
    ]
    # Render every table before publication. Missing integer statistics must not
    # be coerced into floating-point CSV values such as "1.0".
    for column in [*TEAM_STAT_FIELDS, "turnovers", *PREGAME_FIELDS]:
        teams[column] = teams[column].astype("Int64")
    games = games.sort_values(["date", "game_id"], kind="stable")
    teams = teams.sort_values(["date", "game_id", "team"], kind="stable")
    rendered = {
        out_dir / "games.csv": _csv_text(games, GAME_COLUMNS),
        out_dir / "team_game_stats.csv": _csv_text(teams, TEAM_COLUMNS),
    }
    for name in sorted(config.splits.ranges):
        rendered[out_dir / name / "games.csv"] = _csv_text(
            games[games["split"] == name], GAME_COLUMNS
        )
        rendered[out_dir / name / "team_game_stats.csv"] = _csv_text(
            teams[teams["split"] == name], TEAM_COLUMNS
        )
    for path, text in rendered.items():
        _publish(path, text)

    if exported.pages:
        from ivydata.scores import SOURCE_COLUMNS

        provenance = pd.DataFrame(exported.pages, columns=SOURCE_COLUMNS).sort_values(
            ["school", "season", "kind", "url"], kind="stable"
        )
        _publish(
            raw_dir.parent / "manifest/score_sources.csv", _csv_text(provenance, SOURCE_COLUMNS)
        )
    if exported.pages:
        discovered = sorted(
            {
                r.boxscore_url
                for r in exported.rows
                if r.boxscore_url and urlsplit(r.boxscore_url).scheme in ("http", "https")
            }
        )
        _publish(raw_dir.parent / "manifest/boxscore_urls.txt", "\n".join(discovered) + "\n")
        coverage = []
        for school in sorted(config.schools, key=lambda s: s.id):
            for year in config.splits.seasons():
                selected = games[
                    (games["season"] == year)
                    & ((games["home_team"] == school.id) | (games["away_team"] == school.id))
                ]
                sources = {
                    p["kind"]
                    for p in exported.pages
                    if p["school"] == school.id
                    and int(p["season"]) == year
                    and p["status"] == 200
                    and p["games_found"] > 0
                }
                if any(
                    r["kind"] == "schedule"
                    and r["school"] == school.id
                    and int(r["season"]) == year
                    for r in rows
                ):
                    sources.add("cached_schedule")
                coverage.append(
                    {
                        "school": school.id,
                        "season": year,
                        "schedule_sources": "|".join(sorted(sources)),
                        "games_in_dataset": len(selected),
                        "games_with_scores": int(selected["home_pts"].notna().sum()),
                        "games_with_stats": int((selected["stats_level"] == "full").sum()),
                        "source_disagreements": int(selected["sources_agree"].eq(False).sum()),
                    }
                )
        columns = [
            "school",
            "season",
            "schedule_sources",
            "games_in_dataset",
            "games_with_scores",
            "games_with_stats",
            "source_disagreements",
        ]
        _publish(
            raw_dir.parent / "reports/score_coverage.csv",
            _csv_text(pd.DataFrame(coverage), columns),
        )
    return {
        "games": games.to_dict(orient="records"),
        "team_rows": teams.to_dict(orient="records"),
        "conflicts": merged.conflicts,
        "warnings": [r["message"] for r in warnings],
    }
