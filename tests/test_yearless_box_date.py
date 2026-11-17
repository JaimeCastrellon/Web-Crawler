from pathlib import Path

import pytest

from ivydata.parse.boxscore import parse_boxscore

FIXTURE = Path(__file__).parent / "fixtures/boxscore_cornell_2016_colgate_yearless.html"
URL = "https://cornellbigred.com/sports/football/stats/2016-17/colgate-university/boxscore/20110"


def test_yearless_numeric_date_uses_matching_full_game_title_date():
    box = parse_boxscore(FIXTURE.read_text(), URL)
    assert not box.warnings
    assert box.game["date"] == "2016-10-01"
    assert (box.game["away_raw"], box.game["home_raw"]) == ("Cornell", "Colgate")
    assert (box.game["away_pts"], box.game["home_pts"]) == (39, 38)
    assert box.game["away_q3"] == 21 and box.game["attendance"] == 8010


@pytest.mark.parametrize("case", ["no_title", "different_day", "conflicting_titles"])
def test_yearless_date_is_not_guessed_when_own_title_is_missing_or_ambiguous(case):
    html = FIXTURE.read_text()
    if case == "no_title":
        html = html.replace("Football vs Colgate University on 10/1/2016", "Cornell box score")
    elif case == "different_day":
        html = html.replace("on 10/1/2016", "on 10/2/2016")
    else:
        html = html.replace(
            "</head>", '<meta name="og:title" content="Football Box Score on 10/1/2017"></head>'
        )
    box = parse_boxscore(html, URL)
    assert box.game["date"] is None
    assert any("invalid date" in warning for warning in box.warnings)


def test_explicit_metadata_date_keeps_precedence_over_title():
    html = FIXTURE.read_text().replace("<dd>10/1</dd>", "<dd>10/1/2016</dd>")
    html = html.replace("on 10/1/2016", "on 10/1/2017")
    assert parse_boxscore(html, URL).game["date"] == "2016-10-01"
