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
    assert any("conflicting away_pts" in c for c in summary["conflicts"])

    g = games["20261121-harvard-vs-yale"]
    assert g["neutral_site"] == "true" and g["home_pts"] == "" and g["num_ot"] == ""
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
        ("away", 35, 34, None),
        ("home", 17, 24, 1),
        ("home", 21, 13, None),
    ]


def test_build_is_independent_of_wall_clock(tmp_path, monkeypatch):
    from datetime import date

    import ivydata.scores as scores

    class NoToday(date):
        @classmethod
        def today(cls):
            raise AssertionError("build must not consult wall clock")

    monkeypatch.setattr(scores, "date", NoToday)
    path = tmp_path / "export.json"
    path.write_text(json.dumps(_export()))
    build_scores([path], None, tmp_path, CFG)
    before = {str(p): p.read_bytes() for p in (tmp_path / "data/processed").rglob("*.csv")}
    build_scores([path], None, tmp_path, CFG)
    assert before == {str(p): p.read_bytes() for p in (tmp_path / "data/processed").rglob("*.csv")}


def test_canonical_schema_neutral_flags_and_actual_provenance(tmp_path):
    from ivydata.build import GAME_COLUMNS, TEAM_COLUMNS

    path = tmp_path / "export.json"
    path.write_text(json.dumps(_export()))
    build_scores([path], None, tmp_path, CFG)
    with (tmp_path / "data/processed/games.csv").open() as stream:
        games = list(csv.DictReader(stream))
    with (tmp_path / "data/processed/team_game_stats.csv").open() as stream:
        teams = list(csv.DictReader(stream))
    assert list(games[0]) == GAME_COLUMNS and list(teams[0]) == TEAM_COLUMNS
    neutral = next(g for g in games if g["neutral_site"] == "true")
    rows = [t for t in teams if t["game_id"] == neutral["game_id"]]
    assert sum(t["is_home"] == "true" for t in rows) == 1
    assert next(t for t in rows if t["team"] == neutral["home_team"])["is_home"] == "true"
    assert not any("/b/1" in g["source_urls"] for g in games)


def test_default_build_imports_saved_exports(tmp_path):
    from ivydata.build import build

    path = tmp_path / "data/sources/ivy_official_yale.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(_export()))
    build(tmp_path / "data/raw", tmp_path / "data/processed", CFG)
    with (tmp_path / "data/processed/games.csv").open() as stream:
        assert len(list(csv.DictReader(stream))) == 4


def test_official_source_beats_wikipedia_even_when_url_sorts_later(tmp_path):
    from ivydata.normalize.merge import merge_games
    from ivydata.scores import load_score_exports

    off = _export()
    off["schools"] = {"yale": off["schools"]["yale"]}
    off["schools"]["yale"]["pages"] = off["schools"]["yale"]["pages"][:1]
    official = tmp_path / "official.json"
    official.write_text(json.dumps(off))
    wiki = tmp_path / "wiki.json"
    wiki.write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "school": "yale",
                        "season": 2024,
                        "url": "https://en.wikipedia.org/wiki/2024_Yale_Bulldogs_football_team",
                        "exists": True,
                        "entries": [
                            {
                                "date": "October 12",
                                "opponent": "Dartmouth",
                                "w/l": "L",
                                "score": "1–44",
                            }
                        ],
                    }
                ]
            }
        )
    )
    result = merge_games([], load_score_exports([official, wiki], CFG).rows, CFG.team_aliases)
    game = next(g for g in result.games if "dartmouth" in g["game_id"])
    assert game["home_pts"] == 43 and game["sources_agree"] is False


def test_reviewed_two_day_date_fix_requires_official_evidence(tmp_path):
    from ivydata.normalize.merge import merge_games
    from ivydata.scores import load_score_exports

    target = "https://en.wikipedia.org/wiki/2001_Dartmouth_Big_Green_football_team"
    wiki = tmp_path / "wiki.json"
    wiki.write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "school": "dartmouth",
                        "season": 2001,
                        "url": target,
                        "exists": True,
                        "entries": [
                            {
                                "date": "September 27",
                                "opponent": "Penn",
                                "w/l": "L",
                                "score": "14–27",
                            }
                        ],
                    }
                ]
            }
        )
    )
    parsed = load_score_exports([wiki], CFG)
    assert parsed.rows[0].date == "2001-09-27" and parsed.warnings == []
    off = tmp_path / "official.json"
    off.write_text(
        json.dumps(
            {
                "schools": {
                    "penn": {
                        "pages": [
                            {
                                "season": 2001,
                                "slug": "2001",
                                "url": "/sports/football/schedule/2001",
                                "status": 200,
                                "rows": [
                                    _row(
                                        "sidearm-schedule-away-game",
                                        "Sep 29",
                                        "at",
                                        "Dartmouth",
                                        "W, 27-14",
                                    )
                                ],
                            }
                        ]
                    }
                }
            }
        )
    )
    parsed = load_score_exports([wiki, off], CFG)
    corrected = next(r for r in parsed.rows if r.school == "dartmouth")
    assert corrected.date == "2001-09-29" and corrected.original_date == "2001-09-27"
    assert any(target in w and "reviewed date correction" in w for w in parsed.warnings)
    result = merge_games([], parsed.rows, CFG.team_aliases)
    assert len(result.games) == 1 and result.games[0]["sources_agree"] is False
    assert any("2001-09-27" in c for c in result.conflicts)


def test_failed_exports_are_not_parsed():
    from ivydata.scores import rows_from_export, rows_from_wikipedia

    exp = _export()
    page = exp["schools"]["yale"]["pages"][0]
    page["status"] = 500
    parsed = rows_from_export(exp, CFG)
    assert not any(r.school == "yale" and r.season == 2024 for r in parsed.rows)
    assert any("HTTP 500" in w for w in parsed.warnings)
    parsed = rows_from_wikipedia(
        {
            "pages": [
                {
                    "school": "yale",
                    "season": 2004,
                    "url": "https://example/x",
                    "exists": False,
                    "entries": [{"date": "September 1"}],
                }
            ]
        }
    )
    assert parsed.rows == [] and parsed.warnings


def test_export_import_preserves_verified_cached_boxscore_stats(tmp_path):
    from hashlib import sha1, sha256
    from pathlib import Path

    from ivydata.build import build
    from ivydata.crawl.fetcher import FetchResult
    from ivydata.crawl.manifest import Manifest

    raw = tmp_path / "data/raw"
    url = "https://yalebulldogs.com/sports/football/stats/2024/dartmouth/boxscore/18407"
    content = (Path(__file__).parent / "fixtures/boxscore_yale_2024_dartmouth.html").read_bytes()
    body = raw / "yalebulldogs.com" / f"{sha1(url.encode()).hexdigest()}.html"
    body.parent.mkdir(parents=True)
    body.write_bytes(content)
    manifest = Manifest(tmp_path / "data/manifest/urls.csv")
    manifest.record(
        FetchResult(url, 200, body, sha256(content).hexdigest(), True, "2026-11-16"),
        "yale",
        2024,
        "boxscore",
        "2024",
    )
    manifest.save()
    source = tmp_path / "data/sources/ivy_official_yale.json"
    source.parent.mkdir()
    source.write_text(json.dumps(_export()))
    build(raw, tmp_path / "data/processed", CFG)
    with (tmp_path / "data/processed/games.csv").open() as stream:
        game = next(g for g in csv.DictReader(stream) if "dartmouth" in g["game_id"])
    assert game["stats_level"] == "full" and game["home_pts"] == "43" and game["num_ot"] == "1"
    with (tmp_path / "data/processed/team_game_stats.csv").open() as stream:
        team = next(
            t
            for t in csv.DictReader(stream)
            if t["game_id"] == game["game_id"] and t["team"] == "yale"
        )
    assert team["pass_yds"] == "412" and team["sacks_allowed"] == "1"
    assert url in game["source_urls"] and "/b/1" not in game["source_urls"]
