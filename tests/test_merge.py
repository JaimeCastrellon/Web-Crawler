from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from random import Random

import pytest

from ivydata.config import load_config
from ivydata.normalize.merge import make_game_id, merge_games
from ivydata.parse.boxscore import GAME_FIELDS, TEAM_STAT_FIELDS, ParsedBoxscore, parse_boxscore
from ivydata.parse.schedule import ScheduleRow, parse_schedule

ALIASES = load_config().team_aliases
FIXTURES = Path(__file__).parent / "fixtures"


def schedule(**changes):
    row = ScheduleRow(
        "yale",
        2004,
        "2004-11-20",
        "Harvard University",
        "away",
        "Harvard Stadium",
        "L",
        3,
        35,
        None,
        "https://yale.test/schedule",
    )
    return replace(row, **changes)


def box(**changes):
    game = dict.fromkeys(GAME_FIELDS) | dict(
        date="2004-11-20", home_raw="HARV", away_raw="YAL", home_pts=35, away_pts=3
    )
    game.update(changes)
    stats = [
        dict.fromkeys(TEAM_STAT_FIELDS)
        | dict(team_raw=game[f"{s}_raw"], is_home=s == "home", rush_yds=100 + i)
        for i, s in enumerate(("away", "home"))
    ]
    return ParsedBoxscore("https://harvard.test/box", game, stats)


def test_two_ivy_copies_merge_and_schedule_cannot_overwrite_stats():
    a = box()
    b = deepcopy(a)
    b.page_url = "https://yale.test/box"
    b.game["home_raw"] = "Harvard University"
    b.game["away_raw"] = "Yale University"
    b.team_stats[0]["team_raw"] = "Yale University"
    b.team_stats[1]["team_raw"] = "Harvard University"
    rows = [
        schedule(),
        schedule(
            school="harvard",
            opponent_raw="Yale",
            location="home",
            points=35,
            opponent_points=3,
            page_url="https://harvard.test/schedule",
        ),
    ]
    before = deepcopy((a, b, rows))
    result = merge_games([a, b], rows, ALIASES)
    assert len(result.games) == 1 and len(result.team_stats) == 2
    game = result.games[0]
    assert game["game_id"] == "20041120-yale-at-harvard"
    assert game["sources_agree"] is True and game["ivy_game"] is True
    assert game["stats_level"] == "full"
    assert game["source_urls"] == "|".join(
        sorted([a.page_url, b.page_url, *[r.page_url for r in rows]])
    )
    assert [(r["team"], r["rush_yds"], r["points"], r["is_home"]) for r in result.team_stats] == [
        ("harvard", 101, 35, True),
        ("yale", 100, 3, False),
    ]
    assert result.conflicts == []
    assert (a, b, rows) == before


def test_disagreement_keeps_boxscore_and_reports_url_values():
    result = merge_games([box()], [schedule(points=7, date="2004-11-19")], ALIASES)
    assert result.games[0]["date"] == "2004-11-20"
    assert result.games[0]["away_pts"] == 3
    assert result.games[0]["sources_agree"] is False
    assert any(
        "conflicting date" in c and "https://yale.test/schedule" in c for c in result.conflicts
    )
    assert any("away_pts" in c and "=7" in c and "=3" in c for c in result.conflicts)


def test_stats_conflicts_reported_without_changing_score_date_agreement():
    a = box()
    b = deepcopy(a)
    b.page_url = "https://second.test/box"
    b.team_stats[0]["rush_yds"] = 99
    result = merge_games([a, b], [], ALIASES)
    assert result.games[0]["sources_agree"] is True
    assert any("yale.rush_yds" in c and "99" in c and "100" in c for c in result.conflicts)


def test_complementary_boxscore_stats_fill_missing_without_zero_invention():
    a = box()
    b = deepcopy(a)
    b.page_url = "https://second.test/box"
    a.team_stats[0]["pass_int"] = 0
    b.team_stats[1]["fumbles_lost"] = 1
    result = merge_games([a, b], [], ALIASES)
    yale = next(t for t in result.team_stats if t["team"] == "yale")
    harvard = next(t for t in result.team_stats if t["team"] == "harvard")
    assert yale["pass_int"] == 0 and yale["fumbles_lost"] is None
    assert harvard["pass_int"] is None and harvard["fumbles_lost"] == 1


def test_non_ivy_and_repeated_single_source():
    row = schedule(opponent_raw="Holy Cross", points=0, opponent_points=7)
    result = merge_games([], [row, row], ALIASES)
    assert len(result.games) == 1
    assert result.games[0]["ivy_game"] is False
    assert result.games[0]["sources_agree"] is None
    assert result.games[0]["stats_level"] == "score_only"
    assert result.games[0]["away_pts"] == 0
    assert all(t[k] is None for t in result.team_stats for k in TEAM_STAT_FIELDS)


def test_neutral_id_independent_of_team_perspective():
    yale = schedule(location="neutral", venue="Fenway Park")
    harvard = schedule(
        school="harvard",
        opponent_raw="Yale",
        location="neutral",
        points=35,
        opponent_points=3,
        page_url="https://harvard.test/schedule",
        venue="Fenway Park",
    )
    result = merge_games([], [yale, harvard], ALIASES)
    assert result.games[0]["game_id"] == "20041120-harvard-vs-yale"
    assert result.games[0]["home_team"] == "yale"
    assert result.games[0]["home_pts"] == 3
    assert result.games[0]["neutral_site"] is True
    assert result.conflicts == []
    # With a box score, retain its designated home team and correctly orient its scores.
    b = box(stadium="Fenway Park")
    game = merge_games([b], [yale, harvard], ALIASES).games[0]
    assert game["home_team"] == "harvard" and game["home_pts"] == 35
    assert game["game_id"] == result.games[0]["game_id"]


def test_home_away_contradiction_aligns_scores_by_team_and_flags_conflict():
    result = merge_games([box()], [schedule(location="home")], ALIASES)
    assert result.games[0]["home_pts"] == 35 and result.games[0]["away_pts"] == 3
    assert result.games[0]["sources_agree"] is False
    assert any("home_team" in c for c in result.conflicts)
    assert not any("conflicting home_pts" in c for c in result.conflicts)


def test_separate_games_and_date_chain_are_not_collapsed():
    rows = [
        schedule(date=f"2004-11-{d}", page_url=f"https://yale.test/{d}") for d in (18, 19, 20, 27)
    ]
    result = merge_games([], rows, ALIASES)
    assert len(result.games) == 3
    assert any("ambiguous date chain" in c for c in result.conflicts)


def test_unplayed_current_game_preserves_missing_finals():
    row = schedule(
        season=2026,
        date="2026-11-21",
        result=None,
        points=None,
        opponent_points=None,
        location="neutral",
        venue="Fenway Park",
    )
    result = merge_games([], [row], ALIASES)
    assert result.games[0]["home_pts"] is None and result.games[0]["away_pts"] is None
    assert all(t["points"] is None for t in result.team_stats)


def test_invalid_identity_and_parser_warnings_survive_with_urls():
    a = box(date=None)
    a.warnings = ["https://harvard.test/box: bad game date"]
    result = merge_games([a], [schedule(opponent_raw="Yale"), schedule()], ALIASES)
    assert len(result.games) == 1
    assert any("https://harvard.test/box: bad game date" == c for c in result.conflicts)
    assert any(
        "unusable box score" in c and "https://harvard.test/box" in c for c in result.conflicts
    )
    assert any(
        "unusable schedule row" in c and "https://yale.test/schedule" in c for c in result.conflicts
    )


def test_input_order_independent_even_with_conflicting_boxes():
    a = box()
    b = box(home_pts=34)
    b.page_url = "https://other.test/box"
    rows = [
        schedule(),
        schedule(date="2004-11-19"),
        schedule(opponent_raw="Colgate", date="2004-10-02"),
    ]
    expected = merge_games([a, b], rows, ALIASES)
    rng = Random(8)
    for _ in range(15):
        boxes = [a, b]
        rng.shuffle(boxes)
        rng.shuffle(rows)
        assert merge_games(boxes, rows, ALIASES) == expected


def test_recovered_2004_boxscores_join_the_ten_game_yale_schedule():
    rows = parse_schedule(
        (FIXTURES / "schedule_yale_2004.html").read_text(),
        "yale",
        2004,
        "https://yalebulldogs.com/sports/football/schedule/2004",
    ).rows
    boxes = [
        parse_boxscore(
            (FIXTURES / f"boxscore_{s}_2004_yale.html").read_text(), f"https://{s}.test/box"
        )
        for s in ("cornell", "penn", "brown", "columbia", "harvard", "dartmouth")
    ]
    result = merge_games(boxes, rows, ALIASES)
    assert len(result.games) == 10 and len(result.team_stats) == 20
    assert sum(g["stats_level"] == "full" for g in result.games) == 6
    assert result.conflicts == []
    assert len({g["game_id"] for g in result.games}) == 10


@pytest.mark.parametrize(
    "day,home,away,neutral,expected",
    [
        ("2004-11-20", "harvard", "yale", False, "20041120-yale-at-harvard"),
        ("2018-11-17", "yale", "harvard", True, "20181117-harvard-vs-yale"),
    ],
)
def test_game_id(day, home, away, neutral, expected):
    assert make_game_id(day, home, away, neutral) == expected


@pytest.mark.parametrize(
    "day,home,away",
    [
        ("bad", "yale", "harvard"),
        ("20240230", "yale", "harvard"),
        ("2004-11-20", "Yale", "harvard"),
        ("2004-11-20", "yale", "yale"),
        ("2004-11-20", "", "harvard"),
    ],
)
def test_invalid_game_id(day, home, away):
    with pytest.raises(ValueError):
        make_game_id(day, home, away, False)


def test_bad_statistics_identity_does_not_discard_valid_game():
    b = box()
    b.team_stats[0]["team_raw"] = ""
    result = merge_games([b], [], ALIASES)
    assert len(result.games) == 1 and len(result.team_stats) == 2
    assert any("unusable statistics team" in c and b.page_url in c for c in result.conflicts)
    assert next(t for t in result.team_stats if t["team"] == "yale")["rush_yds"] is None


def test_empty_inputs():
    result = merge_games([], [], ALIASES)
    assert result.games == result.team_stats == result.conflicts == []
