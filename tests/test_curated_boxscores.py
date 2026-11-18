"""Reviewed PDF facts remain explicit, bounded and tied to unchanged source evidence."""

import copy
import csv
import json
from hashlib import sha1, sha256
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from ivydata.config import load_config
from ivydata.normalize.curated import load_reviewed_boxscores
from ivydata.parse.boxscore import GAME_FIELDS, TEAM_STAT_FIELDS

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def proof(tmp_path):
    entry = json.loads((ROOT / "data/manifest/reviewed_boxscores.json").read_text())[0]
    body = b"%PDF-1.7\nmock cached source for proof-integrity tests, not a PDF parser test\n"
    entry["source_sha256"] = sha256(body).hexdigest()
    raw = tmp_path / "raw"
    path = raw / urlsplit(entry["url"]).hostname / f"{sha1(entry['url'].encode()).hexdigest()}.html"
    path.parent.mkdir(parents=True)
    path.write_bytes(body)
    metadata = {
        "url": entry["url"],
        "status": 200,
        "sha256": entry["source_sha256"],
        "fetched_at": entry["source_fetched_at"],
    }
    path.with_suffix(".json").write_text(json.dumps(metadata))
    return entry, raw, path, tmp_path / "reviewed.json"


def test_reviewed_game_has_exact_known_values_and_unknown_fields_stay_missing(proof):
    entry, raw, _, path = proof
    path.write_text(json.dumps([entry]))
    (box,) = load_reviewed_boxscores(path, raw, load_config())
    assert set(box.game) == set(GAME_FIELDS)
    assert box.game["date"] == "2014-09-19"
    assert (box.game["home_pts"], box.game["away_pts"]) == (41, 18)
    away, home = box.team_stats
    assert away["team_raw"] == "Holy Cross" and away["is_home"] is False
    assert home["team_raw"] == "Harvard" and home["is_home"] is True
    assert (away["pass_yds"], home["pass_yds"]) == (233, 227)
    assert (away["time_of_possession_s"], home["time_of_possession_s"]) == (1884, 1716)
    assert home["rush_att"] is None and home["punt_yds"] is None
    assert set(home) == set(TEAM_STAT_FIELDS) | {"team_raw", "is_home"}
    assert not box.warnings


@pytest.mark.parametrize("damage", ["body", "missing", "url", "sha256", "fetched_at", "status"])
def test_changed_or_unavailable_evidence_cannot_reuse_reviewed_values(proof, damage):
    entry, raw, body, path = proof
    path.write_text(json.dumps([entry]))
    if damage == "body":
        body.write_bytes(b"changed cached source")
    elif damage == "missing":
        body.unlink()
    else:
        sidecar = body.with_suffix(".json")
        metadata = json.loads(sidecar.read_text())
        metadata[damage] = 404 if damage == "status" else "changed"
        sidecar.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="PDF evidence"):
        load_reviewed_boxscores(path, raw, load_config())


@pytest.mark.parametrize(
    "damage",
    [
        "game_record",
        "team_record",
        "date",
        "season",
        "final",
        "quarters",
        "same_team",
        "team_name",
        "orientation",
        "missing_stats",
        "negative_attempt",
        "fraction",
        "boolean_integer",
        "bounds",
        "page",
        "region",
        "method",
        "http",
    ],
)
def test_invalid_or_leaking_reviewed_claims_fail_explicitly(proof, damage):
    entry, raw, _, path = proof
    if damage == "game_record":
        entry["game"]["wins_before"] = 9
    elif damage == "team_record":
        entry["team_stats"][0]["record"] = "9-1"
    elif damage == "date":
        entry["game"]["date"] = "2015-09-19"
    elif damage == "season":
        entry["season"] = 2020
    elif damage == "final":
        entry["game"]["home_pts"] = None
    elif damage == "quarters":
        entry["game"]["home_q1"] = 100
    elif damage == "same_team":
        entry["game"]["away_raw"] = "Harvard"
    elif damage == "team_name":
        entry["team_stats"][0]["team_raw"] = "Princeton"
    elif damage == "orientation":
        entry["team_stats"][0]["is_home"] = True
    elif damage == "missing_stats":
        entry["team_stats"][0] = {"team_raw": "Holy Cross", "is_home": False}
    elif damage == "negative_attempt":
        entry["team_stats"][0]["rush_att"] = -1
    elif damage == "fraction":
        entry["team_stats"][0]["pass_att"] = 41.5
    elif damage == "boolean_integer":
        entry["team_stats"][0]["pass_att"] = True
    elif damage == "bounds":
        entry["team_stats"][0]["pass_cmp"] = 42
    elif damage == "page":
        entry["evidence_page"] = 0
    elif damage == "region":
        entry["evidence_region"] = ""
    elif damage == "method":
        entry["review_method"] = "unreviewed"
    else:
        entry["url"] = entry["url"].replace("https://", "http://")
    path.write_text(json.dumps([entry]))
    with pytest.raises(ValueError, match="reviewed box score"):
        load_reviewed_boxscores(path, raw, load_config())


def test_duplicate_excerpts_are_rejected_and_absent_ledger_is_optional(proof):
    entry, raw, _, path = proof
    assert load_reviewed_boxscores(path, raw, load_config()) == []
    path.write_text(json.dumps([entry, copy.deepcopy(entry)]))
    with pytest.raises(ValueError, match="duplicate"):
        load_reviewed_boxscores(path, raw, load_config())


def test_committed_pdf_review_is_traceable_to_one_completed_game():
    with (ROOT / "data/processed/games.csv").open() as stream:
        games = list(csv.DictReader(stream))
    verified = {}
    for path in (ROOT / "data/manifest/recovered").glob("*.csv"):
        with path.open() as stream:
            verified.update({r["url"]: r for r in csv.DictReader(stream)})
    for entry in json.loads((ROOT / "data/manifest/reviewed_boxscores.json").read_text()):
        source = verified[entry["url"]]
        assert source["kind"] == "reviewed_boxscore" and source["status"] == "200"
        assert source["sha256"] == entry["source_sha256"]
        assert source["fetched_at"] == entry["source_fetched_at"]
        matches = [g for g in games if entry["url"] in g["source_urls"].split("|")]
        assert len(matches) == 1 and matches[0]["stats_level"] == "full"
        assert matches[0]["date"] == entry["game"]["date"]


def test_reviewed_game_uses_normal_build_records_and_stale_proof_preserves_outputs(proof):
    from ivydata.build import build
    from ivydata.crawl.manifest import Manifest

    entry, raw, body, _ = proof
    manifest_dir = raw.parent / "manifest"
    Manifest(manifest_dir / "urls.csv").save()
    (manifest_dir / "reviewed_boxscores.json").write_text(json.dumps([entry]))
    out = raw.parent / "processed"
    build(raw, out, load_config())
    with (out / "games.csv").open() as stream:
        (game,) = list(csv.DictReader(stream))
    with (out / "team_game_stats.csv").open() as stream:
        stats = {r["team"]: r for r in csv.DictReader(stream)}
    assert game["game_id"] == "20140919-holy-cross-at-harvard"
    assert game["stats_level"] == "full" and game["source_urls"] == entry["url"]
    assert stats["harvard"]["games_before"] == "0"
    assert stats["holy-cross"]["games_before"] == ""
    assert stats["harvard"]["turnovers"] == "2"
    assert stats["holy-cross"]["turnovers"] == "3"
    before = {p: p.read_bytes() for p in out.rglob("*.csv")}
    build(raw, out, load_config())
    assert before == {p: p.read_bytes() for p in before}
    body.write_bytes(b"changed proof")
    with pytest.raises(ValueError, match="PDF evidence"):
        build(raw, out, load_config())
    assert before == {p: p.read_bytes() for p in before}
    warnings = (raw.parent / "reports/build_warnings.csv").read_text()
    assert entry["url"] in warnings and "PDF evidence rejected" in warnings
