import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cornell_reviewed_boxes_are_used_and_keep_true_overtime_count():
    with (ROOT / "data/manifest/recovered/cornell_reviewed_boxscores.csv").open() as stream:
        boxes = [r for r in csv.DictReader(stream) if r["kind"] == "boxscore"]
    with (ROOT / "data/processed/games.csv").open() as stream:
        games = list(csv.DictReader(stream))
    assert len(boxes) == 5 and all(r["status"] == "200" for r in boxes)
    for box in boxes:
        matches = [g for g in games if box["url"] in g["source_urls"].split("|")]
        assert len(matches) == 1 and matches[0]["stats_level"] == "full"
    by_id = {g["game_id"]: g for g in games}
    assert by_id["20021026-cornell-at-brown"]["num_ot"] == "2"
    assert by_id["20091107-cornell-at-dartmouth"]["num_ot"] == "2"
    assert by_id["20070922-cornell-at-yale"]["home_team"] == "yale"
    assert by_id["20071117-cornell-at-penn"]["home_team"] == "penn"
