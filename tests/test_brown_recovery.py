"""Offline checks of the Brown source's committed provenance and derived games."""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_brown_recovery_provenance_and_game_matches():
    manifest = read(ROOT / "data/manifest/recovered/brown_2004_2025.csv")
    boxes = [r for r in manifest if r["kind"] == "boxscore"]
    schedules = [r for r in manifest if r["kind"] == "schedule"]
    assert len(boxes) == 20 and len(schedules) == 2
    assert {r["season"] for r in schedules} == {"2004", "2025"}
    assert len({r["url"] for r in manifest}) == len(manifest)
    assert all(r["status"] == "200" and re.fullmatch("[a-f0-9]{64}", r["sha256"]) for r in manifest)
    assert sum(r["kind"] == "robots" for r in manifest) == 1
    games = read(ROOT / "data/processed/games.csv")
    for box in boxes:
        matching = [g for g in games if box["url"] in g["source_urls"].split("|")]
        assert len(matching) == 1
        assert matching[0]["season"] == box["season"] and matching[0]["stats_level"] == "full"
        assert "brown" in (matching[0]["home_team"], matching[0]["away_team"])


def test_brown_complete_seasons_and_chronology():
    rows = read(ROOT / "data/processed/team_game_stats.csv")
    brown = [r for r in rows if r["team"] == "brown"]
    for year in ("2004", "2025"):
        season = sorted((r for r in brown if r["season"] == year), key=lambda r: r["date"])
        assert len(season) == 10
        assert [int(r["games_before"]) for r in season] == list(range(10))
    last = next(r for r in brown if r["date"] == "2025-11-22")
    assert (last["wins_before"], last["losses_before"]) == ("4", "5")
    assert (last["ivy_wins_before"], last["ivy_losses_before"]) == ("1", "5")
