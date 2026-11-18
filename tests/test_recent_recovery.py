"""The 2014–2016 recovery preserves accepted and unsuccessful source provenance."""

import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted((ROOT / "data/manifest/recovered").glob("*_2014_2016.csv"))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_recent_recovery_has_traceable_games_and_honest_attempts(path):
    with path.open() as stream:
        manifest = list(csv.DictReader(stream))
    with (ROOT / "data/processed/games.csv").open() as stream:
        games = list(csv.DictReader(stream))
    with (ROOT / "data/reports/recovery" / f"{path.stem}_attempts.csv").open() as stream:
        attempts = list(csv.DictReader(stream))
    with (ROOT / "data/reports/recovery_errors" / path.name).open() as stream:
        errors = list(csv.DictReader(stream))

    assert manifest and attempts
    assert len({r["url"] for r in manifest}) == len(manifest)
    assert len({r["requested_url"] for r in attempts}) == len(attempts)
    assert all(2014 <= int(r["season"]) <= 2016 for r in manifest + attempts + errors)
    assert all(
        r["status"] == "200" and re.fullmatch(r"[a-f0-9]{64}", r["sha256"]) for r in manifest
    )
    boxes = [r for r in manifest if r["kind"] == "boxscore"]
    assert boxes or errors, "unsuccessful source recovery must explain the gap"
    assert {r["url"] for r in boxes} == {
        r["url"] for r in attempts if r["disposition"] == "accepted"
    }
    for box in boxes:
        matches = [g for g in games if box["url"] in g["source_urls"].split("|")]
        assert len(matches) == 1 and matches[0]["stats_level"] == "full"
        assert matches[0]["season"] == box["season"]
        assert box["school"] in (matches[0]["home_team"], matches[0]["away_team"])
    for attempt in attempts:
        assert attempt["url"].startswith(("https://", "http://"))
        if not attempt["status"]:
            assert not attempt["sha256"] and not attempt["fetched_at"]
        if attempt["notes"]:
            assert any(e["url"] == attempt["requested_url"] for e in errors)
    assert all(e["error"] and e["url"].startswith(("https://", "http://")) for e in errors)
