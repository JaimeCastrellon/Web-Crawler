from pathlib import Path

from ivydata.parse.boxscore import parse_boxscore

FIXTURE = Path(__file__).parent / "fixtures/boxscore_columbia_2007_princeton_breaks.html"
URL = "https://gocolumbialions.com/news/2007/9/29/1252035.aspx"


def test_archived_html_breaks_and_narrow_conversion_columns_preserve_exact_values():
    html = FIXTURE.read_text()
    result = parse_boxscore(html, URL)
    assert not result.warnings
    assert (result.game["date"], result.game["away_raw"], result.game["home_raw"]) == (
        "2007-09-29",
        "Columbia",
        "Princeton",
    )
    assert (result.game["away_pts"], result.game["home_pts"], result.game["attendance"]) == (
        32,
        42,
        7926,
    )
    columbia, princeton = result.team_stats
    assert (columbia["first_downs"], princeton["first_downs"]) == (21, 29)
    assert (columbia["pass_cmp"], columbia["pass_att"], columbia["pass_int"]) == (23, 43, 2)
    assert (columbia["third_down_conv"], columbia["third_down_att"]) == (6, 13)
    assert (princeton["third_down_conv"], princeton["third_down_att"]) == (11, 15)
    assert (columbia["sacks_allowed"], columbia["sack_yds_lost"]) == (0, 0)
    assert (princeton["sacks_allowed"], princeton["sack_yds_lost"]) == (2, 19)
    assert (columbia["time_of_possession_s"], princeton["time_of_possession_s"]) == (1633, 1967)
    assert not any("record" in key or "wins" in key for key in result.game)
    missing = parse_boxscore(html.replace("Attendance: 7926", "Attendance:"), URL)
    assert missing.game["attendance"] is None and not missing.warnings
