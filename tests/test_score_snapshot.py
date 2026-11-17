"""Review invariants for the proposed full score snapshot, without network access."""

import csv
from pathlib import Path

import pandas as pd

from ivydata.config import load_config
from ivydata.validate.checks import run_checks

ROOT = Path(__file__).resolve().parents[1]


def test_integrated_score_snapshot_is_unique_consistent_and_split_from_config():
    games = pd.read_csv(ROOT / "data/processed/games.csv")
    teams = pd.read_csv(ROOT / "data/processed/team_game_stats.csv")
    assert len(games) == 1355 and len(teams) == 2710
    assert games.game_id.nunique() == len(games)
    assert 2020 not in set(games.season)
    assert not [i for i in run_checks(games, teams) if i.severity == "error"]
    config = load_config()
    assert all(row.split == config.splits.split_for(row.season) for row in games.itertuples())
    assert sum(games.stats_level == "full") >= 28
    future = games[games.date > "2026-11-16"]
    assert future.home_pts.isna().all() and future.away_pts.isna().all()
    last = teams[(teams.team == "harvard") & (teams.date == "2025-11-22")].iloc[0]
    assert (last.games_before, last.wins_before, last.losses_before) == (9, 9, 0)


def test_boxscore_provenance_only_lists_verified_downloads():
    verified = set()
    for path in [
        ROOT / "data/manifest/urls.csv",
        *sorted((ROOT / "data/manifest/recovered").glob("*.csv")),
    ]:
        with path.open() as stream:
            verified.update(
                r["url"]
                for r in csv.DictReader(stream)
                if r["kind"] == "boxscore" and r["status"] == "200"
            )
    with (ROOT / "data/processed/games.csv").open() as stream:
        cited = {
            u
            for row in csv.DictReader(stream)
            for u in row["source_urls"].split("|")
            if "/boxscore/" in u
        }
    assert cited and cited <= verified


def test_export_hashes_and_fallback_revisions_are_traceable():
    import hashlib

    with (ROOT / "data/manifest/score_sources.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 286
    for row in rows:
        assert (
            hashlib.sha256((ROOT / row["export_path"]).read_bytes()).hexdigest()
            == row["export_sha256"]
        )
        assert len(row["payload_sha256"]) == 64
        if row["kind"] == "wikipedia":
            assert row["revision_id"]
