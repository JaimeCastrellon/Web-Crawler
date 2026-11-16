from dataclasses import asdict
from pathlib import Path

import pytest

from ivydata.parse.schedule import parse_schedule

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = "https://yalebulldogs.com/sports/football/schedule/2004"


def game(date="Sep 18 (Sat)", opponent="Dayton", score="W, 24-17", location="away", extra=""):
    return f"""<li class="sidearm-schedule-game sidearm-schedule-{location}-game">
      <div class="sidearm-schedule-game-opponent-date">{date}</div>
      <div class="sidearm-schedule-game-opponent-name">{opponent}</div>
      <div class="sidearm-schedule-game-result">{score}</div>{extra}</li>"""


def test_2004_fixture_exact_games():
    parsed = parse_schedule((FIXTURES / "schedule_yale_2004.html").read_text(), "yale", 2004, PAGE)
    assert parsed.warnings == []
    assert [
        (row.date, row.opponent_raw, row.location, row.result, row.points, row.opponent_points)
        for row in parsed.rows
    ] == [
        ("2004-09-18", "Dayton", "away", "W", 24, 17),
        ("2004-09-25", "Cornell", "away", "L", 7, 19),
        ("2004-10-02", "Colgate", "home", "W", 31, 28),
        ("2004-10-09", "Dartmouth", "away", "W", 24, 14),
        ("2004-10-16", "Lehigh", "home", "L", 24, 30),
        ("2004-10-23", "Penn", "home", "L", 7, 17),
        ("2004-10-30", "Columbia", "home", "W", 21, 14),
        ("2004-11-06", "Brown", "away", "L", 17, 24),
        ("2004-11-13", "Princeton", "home", "W", 21, 9),
        ("2004-11-20", "Harvard", "away", "L", 3, 35),
    ]
    assert parsed.rows[1].boxscore_url is None
    assert parsed.rows[5].boxscore_url == (
        "https://yalebulldogs.com/sports/football/stats/2004/penn/boxscore/10166"
    )
    assert all(
        row.school == "yale" and row.season == 2004 and row.page_url == PAGE for row in parsed.rows
    )


def test_2025_fixture_and_pure_determinism():
    html = (FIXTURES / "schedule_yale_2025.html").read_text()
    page = PAGE.replace("2004", "2025")
    parsed = parse_schedule(html, "yale", 2025, page)
    assert parsed == parse_schedule(html, "yale", 2025, page)
    assert not parsed.warnings and len(parsed.rows) == 12
    first, last = parsed.rows[0], parsed.rows[-1]
    assert (first.date, first.opponent_raw, first.points, first.opponent_points) == (
        "2025-09-20",
        "Holy Cross",
        28,
        10,
    )
    assert first.venue == "New Haven, Conn. Yale Bowl, Class of 1954 Field"
    assert (last.date, last.location, last.points, last.opponent_points) == (
        "2025-12-06",
        "away",
        13,
        21,
    )


def test_modern_cards_keep_zero_score_and_ranked_raw_name():
    html = (FIXTURES / "schedule_brown_2025_excerpt.html").read_text()
    parsed = parse_schedule(
        html, "brown", 2025, "https://brownbears.com/sports/football/schedule/2025"
    )
    assert not parsed.warnings and len(parsed.rows) == 2
    home, away = parsed.rows
    assert (home.date, home.opponent_raw, home.location, home.points, home.opponent_points) == (
        "2025-09-20",
        "Georgetown",
        "home",
        46,
        0,
    )
    assert (away.date, away.opponent_raw, away.location, away.points, away.opponent_points) == (
        "2025-09-27",
        "(RV) Harvard",
        "away",
        7,
        41,
    )


@pytest.mark.parametrize(
    "year,name,points,allowed",
    [
        (2018, "schedule_harvard_2018_fenway", 45, 27),
        (2026, "schedule_harvard_2026_upcoming", None, None),
    ],
)
def test_fenway_neutral_and_future_fixture(year, name, points, allowed):
    html = (FIXTURES / f"{name}.html").read_text()
    parsed = parse_schedule(
        html, "harvard", year, f"https://gocrimson.com/sports/football/schedule/{year}"
    )
    assert not parsed.warnings and len(parsed.rows) == 1
    row = parsed.rows[0]
    assert row.location == "neutral" and "Fenway Park" in row.venue
    assert (row.points, row.opponent_points) == (points, allowed)
    if year == 2026:
        assert row.date == "2026-11-21" and row.result is None and row.boxscore_url is None


@pytest.mark.parametrize(
    "date,extra,expected",
    [
        ("September 18th, 2004", "", "2004-09-18"),
        ("9/18/2004", "", "2004-09-18"),
        ("Jan 3 (Mon)", "", "2005-01-03"),
        ("", '<time datetime="2004-09-18T13:00:00-04:00"></time>', "2004-09-18"),
    ],
)
def test_date_formats_and_postseason_year(date, extra, expected):
    parsed = parse_schedule(game(date=date, extra=extra), "yale", 2004, PAGE)
    assert not parsed.warnings and parsed.rows[0].date == expected


@pytest.mark.parametrize(
    "date,opponent,score,location,reason",
    [
        ("Nov 31", "Dayton", "W, 24-17", "away", "day"),
        ("TBA", "Dayton", "W, 24-17", "away", "date"),
        ("Sep 18, 2026", "Dayton", "W, 24-17", "away", "season"),
        ("Sep 18", "", "W, 24-17", "away", "opponent"),
        ("Sep 18", "Dayton", "Unknown result", "away", "result"),
        ("Sep 18", "Dayton", "W, 24-17", "unknown", "designation"),
    ],
)
def test_bad_rows_keep_url_raw_text_warning_and_later_valid_rows(
    date, opponent, score, location, reason
):
    html = game(date, opponent, score, location) + game()
    parsed = parse_schedule(html, "yale", 2004, PAGE)
    assert len(parsed.rows) == 1 and len(parsed.warnings) == 1
    assert PAGE in parsed.warnings[0] and "raw=" in parsed.warnings[0]
    assert reason in parsed.warnings[0] and (opponent or score) in parsed.warnings[0]


@pytest.mark.parametrize(
    "score,expected",
    [
        ("", (None, None, None)),
        ("Canceled", (None, None, None)),
        ("Postponed", (None, None, None)),
        ("T, 0-0", ("T", 0, 0)),
        ("W, 17-14(2OT)", ("W", 17, 14)),
        ("17–10", ("W", 17, 10)),
    ],
)
def test_result_variants_and_missing_values(score, expected):
    parsed = parse_schedule(game(score=score), "yale", 2004, PAGE)
    assert not parsed.warnings
    row = parsed.rows[0]
    assert (row.result, row.points, row.opponent_points) == expected


def test_boxscore_fallback_and_conflicting_results_remain_visible():
    html = game(score="W, 7-17", extra='<a href="/documents/2004/stats.pdf">Final Stats</a>')
    parsed = parse_schedule(html, "yale", 2004, PAGE)
    assert len(parsed.rows) == 1 and "contradicts" in parsed.warnings[0]
    assert parsed.rows[0].boxscore_url == "https://yalebulldogs.com/documents/2004/stats.pdf"
    assert parsed.rows[0].result == "W" and parsed.rows[0].points == 7


def test_header_records_are_not_extracted_and_unknown_pages_warn():
    html = "<header>Yale (9-1, 6-1 Ivy)</header>" + game()
    parsed = parse_schedule(html, "yale", 2004, PAGE)
    assert set(asdict(parsed.rows[0])) == {
        "school",
        "season",
        "date",
        "opponent_raw",
        "location",
        "venue",
        "result",
        "points",
        "opponent_points",
        "boxscore_url",
        "page_url",
    }
    assert not parsed.warnings
    bad = parse_schedule("<html><body>Unsupported page layout</body></html>", "yale", 2004, PAGE)
    assert not bad.rows and PAGE in bad.warnings[0] and "Unsupported page layout" in bad.warnings[0]


def test_silent_redirect_to_current_season_does_not_relabel_games():
    html = "<title>2026 Football Schedule - Yale University</title>" + game()
    parsed = parse_schedule(html, "yale", 2004, PAGE)
    assert not parsed.rows
    assert "page declares season 2026, expected 2004" in parsed.warnings[0]
    assert PAGE in parsed.warnings[0]


def test_multiple_boxscore_sources_keep_first_and_warn_with_all_urls():
    urls = [
        f"https://yalebulldogs.com/sports/football/stats/2004/dayton/boxscore/{i}" for i in (1, 2)
    ]
    html = game(extra="".join(f'<a href="{url}">Box Score</a>' for url in urls))
    parsed = parse_schedule(html, "yale", 2004, PAGE)
    assert parsed.rows[0].boxscore_url == urls[0]
    assert all(url in parsed.warnings[0] for url in urls)
