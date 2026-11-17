"""Offline source excerpts plus adversarial layout/data checks."""

import re
from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from ivydata.parse.boxscore import GAME_FIELDS, TEAM_STAT_FIELDS, parse_boxscore

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://example.org/football/boxscore/1"


def fixture(name: str) -> str:
    return (FIXTURES / f"boxscore_{name}.html").read_text()


# Values transcribed from each source's team-statistics table, in contract order.
# Sacks are the opponent's defensive sacks, not the team's sacks made.
STATS = {
    'yale_2025_harvard': [
        [27,25,94,1,28,52,318,3,0,77,412,2,1,7,75,7,15,3,4,2,24,4,136,1578],
        [23,49,172,3,15,19,273,3,0,68,445,2,0,6,65,10,16,1,1,0,0,4,175,2022],
    ],
    'yale_2024_dartmouth': [
        [24,37,157,3,22,42,288,3,0,79,445,4,1,11,92,4,13,1,3,1,13,4,133,1646],
        [28,40,120,1,32,47,412,5,0,87,532,1,1,10,96,6,17,3,5,1,5,3,78,1954],
    ],
    'penn_2004_yale': [
        [27,49,221,2,21,35,276,0,1,84,497,0,0,3,22,10,18,0,1,2,18,6,152,2227],
        [12,36,164,0,12,21,149,1,0,57,313,1,1,5,45,4,13,0,1,1,9,8,279,1373],
    ],
    'cornell_2004_yale': [
        [8,22,35,0,15,34,146,1,0,56,181,1,0,3,16,1,14,1,4,3,25,9,313,1221],
        [19,50,125,1,19,32,174,0,1,82,299,1,0,2,10,9,20,0,1,2,16,5,190,2379],
    ],
    'brown_2004_yale': [
        [26,22,79,0,31,57,419,2,3,79,498,2,1,4,32,5,17,1,3,1,9,4,138,1399],
        [22,52,143,2,19,35,240,1,0,87,383,1,1,5,55,9,20,0,0,3,17,9,347,2146],
    ],
    'harvard_2004_yale': [
        [17,29,42,0,24,46,231,0,1,75,273,1,0,8,48,6,17,1,4,2,8,6,168,1724],
        [22,48,202,2,15,24,124,1,0,72,326,1,0,10,92,7,14,0,2,1,4,5,187,1876],
    ],
    'columbia_2004_yale': [
        [20,45,162,None,23,40,202,None,2,85,364,0,0,10,78,8,19,1,3,1,10,7,253,2081],
        [16,35,135,None,15,30,172,None,2,65,307,0,0,4,35,6,16,0,0,1,8,8,283,1519],
    ],
    'dartmouth_2004_yale': [
        [16,37,133,None,18,28,206,None,2,65,339,0,0,7,50,4,14,1,1,4,29,7,285,1688],
        [16,40,118,None,15,31,246,None,3,71,364,2,2,4,34,3,14,3,5,1,2,4,141,1912],
    ],
}  # fmt: skip


@pytest.mark.parametrize(
    "name,date,away,home,stadium,city,attendance,away_q,home_q",
    [
        (
            "yale_2025_harvard",
            "2025-11-22",
            "Harvard",
            "Yale",
            "Yale Bowl",
            ", Connecticut",
            52497,
            [0, 14, 6, 8, 28],
            [10, 21, 7, 7, 45],
        ),
        (
            "yale_2024_dartmouth",
            "2024-10-12",
            "Dartmouth",
            "Yale",
            "Yale Bowl",
            "New Haven, Connecticut",
            4983,
            [0, 7, 9, 21, 7, 44],
            [2, 21, 7, 7, 6, 43],
        ),
        (
            "penn_2004_yale",
            "2004-10-23",
            "Penn",
            "YALE",
            "Yale Bowl",
            "New Haven, CT",
            17737,
            [7, 0, 10, 0, 17],
            [7, 0, 0, 0, 7],
        ),
        (
            "cornell_2004_yale",
            "2004-09-25",
            "Yale",
            "Cornell",
            "Schoellkopf Field",
            "Ithaca, N.Y.",
            11835,
            [0, 7, 0, 0, 7],
            [3, 6, 0, 10, 19],
        ),
        (
            "brown_2004_yale",
            "2004-11-06",
            "Yale",
            "Brown",
            "Brown Stadium",
            "Brown University",
            6212,
            [3, 14, 0, 0, 17],
            [7, 7, 3, 7, 24],
        ),
        (
            "harvard_2004_yale",
            "2004-11-20",
            "Yale",
            "Harvard",
            "Harvard Stadium",
            "Cambridge, Mass.",
            30308,
            [0, 3, 0, 0, 3],
            [7, 14, 14, 0, 35],
        ),
        (
            "columbia_2004_yale",
            "2004-10-30",
            "Columbia",
            "YALE",
            "Yale Bowl",
            "New Haven, CT",
            6141,
            [0, 14, 0, 0, 14],
            [7, 14, 0, 0, 21],
        ),
        (
            "dartmouth_2004_yale",
            "2004-10-09",
            "YALE",
            "Dartmouth College",
            "Memorial Field",
            "Hanover, N.H.",
            6109,
            [7, 3, 7, 7, 24],
            [7, 0, 7, 0, 14],
        ),
    ],
)
def test_exact_source_values(name, date, away, home, stadium, city, attendance, away_q, home_q):
    result = parse_boxscore(fixture(name), URL)
    expected = dict(
        date=date,
        away_raw=away,
        home_raw=home,
        stadium=stadium,
        city=city,
        attendance=attendance,
        num_ot=len(away_q) - 5,
    )
    for side, scores in [("away", away_q), ("home", home_q)]:
        expected.update({f"{side}_q{i + 1}": scores[i] for i in range(4)})
        expected[f"{side}_ot"] = sum(scores[4:-1]) if len(scores) > 5 else None
        expected[f"{side}_pts"] = scores[-1]
        assert sum(scores[:-1]) == scores[-1]
    assert result.game == expected
    assert set(result.game) == set(GAME_FIELDS)
    assert len(result.team_stats) == 2
    for i, team in enumerate(result.team_stats):
        assert team == dict(zip(TEAM_STAT_FIELDS, STATS[name][i], strict=True)) | {
            "team_raw": (away, home)[i],
            "is_home": bool(i),
        }
    assert result.warnings == []
    assert result == parse_boxscore(fixture(name), URL)


def test_no_header_records_leak():
    original = fixture("harvard_2004_yale")
    changed = original.replace("(5-5,3-4)", "(99-99,88-88)").replace("(10-0,7-0)", "(44-44,77-77)")
    assert original != changed
    assert parse_boxscore(original, URL) == parse_boxscore(changed, URL)
    assert parse_boxscore(
        "<div>Yale (99-99) Harvard (88-88)</div>" + original, URL
    ) == parse_boxscore(original, URL)


def test_missing_line_and_zero_remain_distinct():
    tree = LexborHTMLParser(fixture("penn_2004_yale"))
    tree.css_first("#rushing-tds").parent.decompose()
    result = parse_boxscore(tree.html, URL)
    assert all(t["rush_td"] is None for t in result.team_stats)
    assert result.team_stats[0]["pass_td"] == 0
    assert result.team_stats[0]["fumbles_lost"] == 0


@pytest.mark.parametrize("value,expected", [("-17", -17), ("0", 0), ("--", None), ("N/A", None)])
def test_negative_yards_and_missing_values(value, expected):
    tree = LexborHTMLParser(fixture("penn_2004_yale"))
    tree.css_first("#rushing-total").parent.css("td")[1].inner_html = value
    assert parse_boxscore(tree.html, URL).team_stats[0]["rush_yds"] == expected


def test_bad_stat_and_quarter_mismatch_warn_with_url_and_raw_value():
    tree = LexborHTMLParser(fixture("penn_2004_yale"))
    tree.css_first("#misc-poss-time").parent.css("td")[1].inner_html = "10:99"
    tree.css_first("table tbody tr td.emphasize").inner_html = "99"
    result = parse_boxscore(tree.html, URL)
    assert result.team_stats[0]["time_of_possession_s"] is None
    assert result.game["away_pts"] == 99
    assert any("10:99" in w for w in result.warnings)
    assert any("quarter sum" in w for w in result.warnings)
    assert all(URL in w for w in result.warnings)


def test_multiple_overtimes_including_scoreless_period():
    html = """<dl><dt>Date:</dt><dd>11/1/2024</dd></dl>
    <table><caption>Team Score By Quarter</caption><tbody>
    <tr><td>Away</td><td>7</td><td>0</td><td>0</td><td>0</td><td>0</td><td>2</td><td>9</td></tr>
    <tr><td>Home</td><td>0</td><td>0</td><td>0</td><td>7</td><td>0</td><td>0</td><td>7</td></tr>
    </tbody></table>"""
    result = parse_boxscore(html, URL)
    assert result.game["num_ot"] == 2
    assert result.game["away_ot"] == 2
    assert result.game["home_ot"] == 0
    assert result.game["date"] == "2024-11-01"
    assert any("team statistics" in w for w in result.warnings)


def test_reversed_legacy_stat_columns():
    tree = LexborHTMLParser(fixture("penn_2004_yale"))
    table = tree.css_first(".overall-stats")
    for row in table.css("tr"):
        cells = row.css("th,td")
        if len(cells) == 3:
            row.inner_html = cells[0].html + cells[2].html + cells[1].html
    assert parse_boxscore(tree.html, URL) == parse_boxscore(fixture("penn_2004_yale"), URL)


@pytest.mark.parametrize(
    "html", ["", "<html>Access denied</html>", "<pre>unrecognized archive</pre>"]
)
def test_unknown_page_returns_schema_and_url_warnings(html):
    result = parse_boxscore(html, URL)
    assert result.game == dict.fromkeys(GAME_FIELDS)
    assert all(t["first_downs"] is None for t in result.team_stats)
    assert len(result.warnings) == 3
    assert all(URL in w for w in result.warnings)


def test_malformed_recognized_stat_row_is_reported():
    tree = LexborHTMLParser(fixture("penn_2004_yale"))
    row = tree.css_first("#rushing-total").parent
    row.css("td")[-1].decompose()
    result = parse_boxscore(tree.html, URL)
    assert all(t["rush_yds"] is None for t in result.team_stats)
    assert any(URL in w and "malformed" in w and "Total" in w for w in result.warnings)
    pre = re.sub(r"(NET YARDS RUSHING[^\n]*?42) +202", r"\1", fixture("harvard_2004_yale"))
    assert pre != fixture("harvard_2004_yale")
    assert any("malformed" in w for w in parse_boxscore(pre, URL).warnings)


def test_modern_away_game_uses_explicit_home_team_state():
    html = fixture("brown_2004_rhode_island_away")
    result = parse_boxscore(html, URL)
    assert result.game["home_raw"] == "RHODE ISLAND"
    assert result.game["away_raw"] == "Brown"
    assert result.game["home_pts"] == 13 and result.game["away_pts"] == 20
    assert result.game["home_q1"] == 7 and result.game["away_q4"] == 3
    assert result.team_stats[0]["team_raw"] == "Brown" and result.team_stats[0]["is_home"] is False
    assert (
        result.team_stats[1]["team_raw"] == "RHODE ISLAND"
        and result.team_stats[1]["is_home"] is True
    )
    assert [
        (t["rush_yds"], t["pass_yds"], t["sacks_allowed"], t["sack_yds_lost"])
        for t in result.team_stats
    ] == [(182, 121, 0, 0), (221, 36, 3, 18)]
    assert result.warnings == []
    # Records are not present in the reduced state; adding them changes nothing.
    changed = html.replace('"name": 4', '"name": 4, "record": 1')
    assert changed != html
    assert parse_boxscore(changed, URL) == result


def test_invalid_modern_state_reports_url_instead_of_crashing():
    html = fixture("brown_2004_rhode_island_away").replace('"homeTeam": 2', '"homeTeam": 9999')
    assert any(URL in w and "home/away state" in w for w in parse_boxscore(html, URL).warnings)
