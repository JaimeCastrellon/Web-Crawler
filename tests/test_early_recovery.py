"""Committed early-source provenance must map to real, deduplicated dataset games."""

import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted((ROOT / "data/manifest/recovered").glob("*_2006_2008.csv"))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_early_source_recovery_is_traceable_without_network_or_raw_cache(path):
    with path.open() as stream:
        manifest = list(csv.DictReader(stream))
    assert manifest and len({r["url"] for r in manifest}) == len(manifest)
    assert all(2006 <= int(r["season"]) <= 2008 for r in manifest)
    assert all(
        r["status"] == "200" and re.fullmatch(r"[a-f0-9]{64}", r["sha256"]) for r in manifest
    )
    with (ROOT / "data/processed/games.csv").open() as stream:
        games = list(csv.DictReader(stream))
    boxes = [r for r in manifest if r["kind"] == "boxscore"]
    for box in boxes:
        matches = [g for g in games if box["url"] in g["source_urls"].split("|")]
        assert len(matches) == 1 and matches[0]["stats_level"] == "full"
        assert matches[0]["season"] == box["season"]
        assert box["school"] in (matches[0]["home_team"], matches[0]["away_team"])
    with (ROOT / "data/reports/recovery_errors" / path.name).open() as stream:
        errors = list(csv.DictReader(stream))
    assert boxes or errors, "a source without recovered boxes must explain its gaps"
    for error in errors:
        assert error["url"].startswith("https://") and error["error"]
        assert 2006 <= int(error["season"]) <= 2008
