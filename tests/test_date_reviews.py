import copy
import csv
import json
from hashlib import sha1, sha256
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from ivydata.build import build
from ivydata.config import load_config
from ivydata.crawl.fetcher import FetchResult
from ivydata.crawl.manifest import Manifest
from ivydata.normalize.merge import merge_games
from ivydata.normalize.reviews import (
    DATE_REVIEW_COLUMNS,
    apply_box_date_review,
    load_box_date_reviews,
)
from ivydata.parse.boxscore import parse_boxscore
from ivydata.parse.schedule import parse_schedule

FIXTURES = Path(__file__).parent / "fixtures"
BOX_URL = "https://ivyleague.com/boxscore.aspx?id=review&path=football"
EVIDENCE_URL = "https://gocrimson.com/sports/football/schedule/2018"
STAMP = "2026-11-17T20:00:00+00:00"


def cached(raw: Path, url: str, text: str) -> FetchResult:
    path = raw / urlsplit(url).hostname / f"{sha1(url.encode()).hexdigest()}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    digest = sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "url": url,
                "status": 200,
                "sha256": digest,
                "fetched_at": STAMP,
            }
        )
    )
    return FetchResult(url, 200, path, digest, True, STAMP)


def ledger(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=DATE_REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def review_case(tmp_path):
    raw = tmp_path / "data/raw"
    evidence = cached(
        raw, EVIDENCE_URL, (FIXTURES / "schedule_harvard_2018_san_diego.html").read_text()
    )
    result = cached(
        raw, BOX_URL, (FIXTURES / "boxscore_league_2018_san_diego_date.html").read_text()
    )
    box = parse_boxscore(result.text(), BOX_URL)
    row = dict(
        zip(
            DATE_REVIEW_COLUMNS,
            [
                BOX_URL,
                "2018-09-14",
                "2018-09-15",
                "harvard",
                EVIDENCE_URL,
                evidence.sha256,
                STAMP,
            ],
            strict=True,
        )
    )
    return raw, row, box, evidence, result


def test_review_corrects_only_date_and_preserves_raw_disagreement(review_case):
    raw, row, box, evidence, _ = review_case
    before = copy.deepcopy(box)
    notice = apply_box_date_review(box, row, raw, load_config())
    assert box.game == {**before.game, "date": "2018-09-15"}
    assert box.team_stats == before.team_stats and box._original_date == "2018-09-14"
    assert EVIDENCE_URL in notice and "original disagreement retained" in notice
    schedules = parse_schedule(evidence.text(), "harvard", 2018, EVIDENCE_URL).rows
    merged = merge_games([box], schedules, load_config().team_aliases)
    game = merged.games[0]
    assert game["game_id"] == "20180915-san-diego-at-harvard"
    assert game["date"] == "2018-09-15" and game["sources_agree"] is False
    assert any(
        "2018-09-14" in message and "conflicting date" in message for message in merged.conflicts
    )


@pytest.mark.parametrize("change", ["original", "distance", "checksum", "host", "score", "team"])
def test_unproven_reviews_fail_without_changing_game(review_case, change):
    raw, row, box, _, _ = review_case
    if change == "original":
        row["original_date"] = "2018-09-13"
    elif change == "distance":
        row["date"] = "2018-09-17"
    elif change == "checksum":
        row["evidence_sha256"] = "0" * 64
    elif change == "host":
        row["evidence_url"] = "https://elsewhere.example/schedule/2018"
    elif change == "score":
        box.game["home_pts"] = 35
    else:
        box.game["away_raw"] = "Brown"
    before = copy.deepcopy(box.game)
    with pytest.raises(ValueError):
        apply_box_date_review(box, row, raw, load_config())
    assert box.game == before


def test_date_review_loader_rejects_malformed_or_duplicate_rows(tmp_path, review_case):
    path = tmp_path / "review.csv"
    assert load_box_date_reviews(path) == {}
    _, row, _, _, _ = review_case
    ledger(path, [row])
    assert load_box_date_reviews(path) == {BOX_URL: row}
    ledger(path, [row, row])
    with pytest.raises(ValueError, match="duplicate"):
        load_box_date_reviews(path)
    path.write_text("url,date\nwrong,2018-09-15\n")
    with pytest.raises(ValueError, match="columns"):
        load_box_date_reviews(path)


def test_build_uses_review_proof_and_preserves_outputs_when_proof_is_damaged(review_case):
    raw, row, _, evidence, result = review_case
    manifest = Manifest(raw.parent / "manifest/urls.csv")
    manifest.record(evidence, "harvard", 2018, "schedule", "2018")
    manifest.record(result, "harvard", 2018, "boxscore", "2018")
    manifest.save()
    ledger(raw.parent / "manifest/reviewed_box_dates.csv", [row])
    out = raw.parent / "processed"
    build(raw, out, load_config())
    with (out / "games.csv").open() as stream:
        games = list(csv.DictReader(stream))
    assert len(games) == 1 and games[0]["date"] == "2018-09-15"
    assert "reviewed box-score date" in (raw.parent / "reports/build_warnings.csv").read_text()
    before = {p.name: p.read_bytes() for p in out.glob("*.csv")}
    evidence.path.write_text("damaged")
    with pytest.raises(ValueError, match="checksum"):
        build(raw, out, load_config())
    assert before == {p.name: p.read_bytes() for p in out.glob("*.csv")}
