import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_penn_reviewed_boxes_merge_with_cornell_and_keep_overtime():
    with (ROOT / "data/manifest/recovered/penn_reviewed_boxscores.csv").open() as stream:
        boxes = [r for r in csv.DictReader(stream) if r["kind"] == "boxscore"]
    with (ROOT / "data/processed/games.csv").open() as stream:
        games = list(csv.DictReader(stream))
    assert len(boxes) == 5 and all(r["status"] == "200" for r in boxes)
    for box in boxes:
        matches = [g for g in games if box["url"] in g["source_urls"].split("|")]
        assert len(matches) == 1 and matches[0]["stats_level"] == "full"
    combined = [g for g in games if g["game_id"] == "20071117-cornell-at-penn"]
    assert len(combined) == 1
    assert (
        "pennathletics.com/sports/football/stats/2007/cornell/boxscore/6967"
        in combined[0]["source_urls"]
    )
    assert (
        "cornellbigred.com/sports/football/stats/2007-08/university-of-pennsylvania/boxscore/3530"
        in combined[0]["source_urls"]
    )
    overtime = next(g for g in games if g["game_id"] == "20061104-penn-at-princeton")
    assert (overtime["home_pts"], overtime["away_pts"], overtime["num_ot"]) == ("31", "30", "2")
