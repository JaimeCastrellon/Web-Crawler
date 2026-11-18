"""Official opponent copies must join one existing Ivy game, without network access."""

import csv
import re
from pathlib import Path

import pytest

from ivydata.normalize.teams import IVY_TEAMS

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted((ROOT / "data/manifest/recovered").glob("*_opponent.csv"))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_opponent_box_scores_match_one_game_with_both_teams(path):
    opponent = path.stem.removesuffix("_opponent").replace("_", "-")
    with path.open() as stream:
        manifest = list(csv.DictReader(stream))
    with (ROOT / "data/processed/games.csv").open() as stream:
        games = list(csv.DictReader(stream))
    with (ROOT / "data/reports/recovery" / f"{path.stem}_attempts.csv").open() as stream:
        attempts = list(csv.DictReader(stream))
    with (ROOT / "data/reports/recovery_errors" / path.name).open() as stream:
        errors = list(csv.DictReader(stream))
    boxes = [r for r in manifest if r["kind"] == "boxscore"]
    assert boxes
    assert len({r["url"] for r in manifest}) == len(manifest)
    assert {r["url"] for r in boxes} == {
        r["url"] for r in attempts if r["disposition"] == "accepted"
    }
    for box in boxes:
        assert box["status"] == "200" and re.fullmatch(r"[a-f0-9]{64}", box["sha256"])
        matches = [g for g in games if box["url"] in g["source_urls"].split("|")]
        assert len(matches) == 1
        game = matches[0]
        assert game["stats_level"] == "full" and game["season"] == box["season"]
        assert 2006 <= int(game["season"]) <= 2026
        assert {game["home_team"], game["away_team"]} == {opponent, box["school"]}
        assert box["school"] in IVY_TEAMS
    for attempt in attempts:
        if not attempt["status"]:
            assert not attempt["sha256"] and not attempt["fetched_at"]
        if attempt["notes"]:
            assert any(e["url"] == attempt["requested_url"] for e in errors)
