import csv
import json

from ivydata.config import load_config
from ivydata.normalize.teams import canonical_team_id
from ivydata.scores import (
    build_scores,
    make_game_id,
    parse_game_date,
    parse_location,
    parse_result,
)

CFG = load_config()


def test_parse_result():
    assert parse_result("W, 28-10") == ("W", 28, 10, 0, None)
    assert parse_result("L, 43-44 OT") == ("L", 43, 44, 1, None)
    assert parse_result("W, 50-47 3OT") == ("W", 50, 47, 3, None)
    assert parse_result("T, 7-7") == ("T", 7, 7, 0, None)
    assert parse_result("") == (None, None, None, 0, None)
    assert parse_result("Canceled") == (None, None, None, 0, "Canceled")


def test_parse_date():
    assert parse_game_date("Oct 12 (Sat) Noon ESPN+", 2024) == "2024-10-12"
    assert parse_game_date("Sept 20 (Sat)", 2025) == "2025-09-20"
    assert parse_game_date("Jan 3 (Sat)", 2025) == "2026-01-03"
    assert parse_game_date("TBA", 2025) is None


def test_location():
    assert parse_location("sidearm-schedule-game sidearm-schedule-home-game W", "vs") == "home"
    assert parse_location("sidearm-schedule-game sidearm-schedule-away-game L", "at") == "away"
    assert parse_location("sidearm-schedule-game sidearm-schedule-neutral-game", "vs") == "neutral"


def test_team_ids():
    al = CFG.team_aliases
    assert canonical_team_id("#8 Harvard", al) == "harvard"
    assert canonical_team_id("Yale University", al) == "yale"
    assert canonical_team_id("Holy Cross", al) == "holy-cross"
    assert canonical_team_id("No. 11 Colgate", al) == "colgate"


def test_game_id():
    assert make_game_id("2024-10-12", "yale", "dartmouth", False) == "20241012-dartmouth-at-yale"
    assert make_game_id("2026-11-21", "yale", "harvard", True) == "20261121-harvard-vs-yale"


def _row(cls, date, vs, opp, res, box=""):
    return {"cls": cls, "gid": "", "date": date, "vs": vs, "opp": opp, "loc": "",
            "res": res, "conf": "", "box": box}  # fmt: skip


def _export():
    home, away, neu = (
        "sidearm-schedule-home-game",
        "sidearm-schedule-away-game",
        ("sidearm-schedule-neutral-game"),
    )
    yale_2024 = [
        _row(home, "Oct 12 (Sat)", "vs", "Dartmouth", "L, 43-44 OT", "/b/1"),
        _row(away, "Oct 19 (Sat)", "at", "Holy Cross", "W, 38-31"),
        _row(away, "Nov 23 (Sat)", "at", "Harvard", "W, 34-29"),
    ]
    dart_2024 = [
        _row(away, "Oct 12 (Sat)", "at", "Yale", "W, 44-43 OT"),
    ]
    harv_2024 = [_row(home, "Nov 23 (Sat)", "vs", "Yale", "L, 29-35")]  # deliberate mismatch
    yale_2026 = [_row(neu, "Nov 21 (Sat)", "vs", "Harvard", "")]
    harv_2026 = [_row(neu, "Nov 21 (Sat)", "vs", "Yale", "")]

    def pages(*seasons):
        return [{"season": s, "slug": str(s), "url": f"/sports/football/schedule/{s}",
                 "status": 200, "fetched_at": "t", "rows": r} for s, r in seasons]  # fmt: skip

    return {
        "schools": {
            "yale": {"pages": pages((2024, yale_2024), (2026, yale_2026))},
            "dartmouth": {"pages": pages((2024, dart_2024))},
            "harvard": {"pages": pages((2024, harv_2024), (2026, harv_2026))},
        }
    }


def test_build_scores(tmp_path):
    exp = tmp_path / "export.json"
    exp.write_text(json.dumps(_export()))
    summary = build_scores([exp], None, tmp_path, CFG)

    with (tmp_path / "data/processed/games.csv").open() as f:
        games = {g["game_id"]: g for g in csv.DictReader(f)}
    assert len(games) == 4  # Dartmouth game and Harvard games merged across sources

    g = games["20241012-dartmouth-at-yale"]
    assert (g["home_pts"], g["away_pts"], g["num_ot"], g["sources_agree"]) == (
        "43",
        "44",
        "1",
        "true",
    )
    assert g["ivy_game"] == "true" and g["split"] == "test"

    g = games["20241123-yale-at-harvard"]
    assert g["sources_agree"] == "false"
    assert any("score mismatch" in c for c in summary["conflicts"])

    g = games["20261121-harvard-vs-yale"]
    assert g["neutral_site"] == "true" and g["home_pts"] == "" and g["status"] == "scheduled"
    assert g["split"] == "current"

    with (tmp_path / "data/processed/team_game_stats.csv").open() as f:
        yale = [r for r in csv.DictReader(f) if r["team"] == "yale" and r["season"] == "2024"]
    assert [r["wins_before"] for r in yale] == ["0", "0", "1"]
    assert [r["losses_before"] for r in yale] == ["0", "1", "1"]
    assert [r["ivy_losses_before"] for r in yale] == ["0", "1", "1"]
    assert (tmp_path / "data/processed/test/games.csv").exists()


def test_wikipedia_rows():
    from ivydata.scores import clean_wikitext, rows_from_wikipedia

    assert clean_wikitext("{{tooltip|November 3|Friday}}") == "November 3"
    assert clean_wikitext("#18 [[2010 Penn Quakers football team|Penn]]<ncg>") == "#18 Penn"
    exp = {
        "pages": [
            {
                "school": "harvard", "season": 2004, "url": "https://en.wikipedia.org/wiki/x",
                "exists": True, "entries": [
                    {"date": "September 25", "w/l": "w", "away": "y",
                     "opponent": "[[2004 Brown Bears football team|Brown]]", "score": "35–34"},
                    {"date": "October 23", "w/l": "l",
                     "opponent": "[[X|Penn]]", "score": "17–24 OT"},
                    {"_format": "positional",
                     "_raw": "October 1 |  |  | [[2007 Penn Quakers football team|Penn]] | "
                             "Memorial Field | Hanover, NH |  | W 21 13 | 5,929 | "},
                ],
            }
        ]
    }  # fmt: skip
    rows = rows_from_wikipedia(exp).rows
    assert [(r.location, r.points, r.opponent_points, r.num_ot) for r in rows] == [
        ("away", 35, 34, 0),
        ("home", 17, 24, 1),
        ("home", 21, 13, 0),
    ]
