from copy import deepcopy
from itertools import combinations

import pandas as pd
import pytest

from ivydata import cli
from ivydata.build import GAME_COLUMNS, PREGAME_FIELDS, TEAM_COLUMNS
from ivydata.validate.checks import (
    Issue,
    duplicate_game_ids,
    read_build_warnings,
    run_checks,
    write_report,
)


def frames(home="harvard", away="yale", game_id="20040901-yale-at-harvard"):
    game = dict.fromkeys(GAME_COLUMNS) | dict(
        game_id=game_id,
        season=2004,
        date="2004-09-01",
        home_team=home,
        away_team=away,
        neutral_site=False,
        home_pts=7,
        away_pts=3,
        home_q1=7,
        home_q2=0,
        home_q3=0,
        home_q4=0,
        away_q1=0,
        away_q2=3,
        away_q3=0,
        away_q4=0,
        num_ot=0,
        ivy_game=True,
        stats_level="score_only",
        split="train",
        sources_agree=True,
        source_urls="https://official.example/box|https://other.example/schedule",
    )
    teams = []
    for side, other in [("home", "away"), ("away", "home")]:
        teams.append(
            dict.fromkeys(TEAM_COLUMNS)
            | dict(
                game_id=game_id,
                season=2004,
                date=game["date"],
                team=game[f"{side}_team"],
                opponent=game[f"{other}_team"],
                is_home=side == "home",
                points=game[f"{side}_pts"],
                points_allowed=game[f"{other}_pts"],
                neutral_site=False,
                split="train",
                stats_level="score_only",
            )
            | dict.fromkeys(PREGAME_FIELDS, 0)
        )
    return pd.DataFrame([game], dtype=object), pd.DataFrame(teams, dtype=object)


def test_valid_partial_dataset_has_only_coverage_warnings():
    games, teams = frames()
    before = deepcopy((games, teams))
    issues = run_checks(games, teams)
    assert len(issues) == 8
    assert all(i.check == "ivy_game_count" and i.severity == "warning" for i in issues)
    pd.testing.assert_frame_equal(games, before[0])
    pd.testing.assert_frame_equal(teams, before[1])


def test_duplicate_ids_and_team_rows_are_errors():
    games, teams = frames()
    issues = run_checks(pd.concat([games, games]), pd.concat([teams, teams.iloc[[0]]]))
    assert any(i.check == "duplicate_game_id" and i.severity == "error" for i in issues)
    assert any(i.check == "duplicate_team_row" for i in issues)
    assert any(i.check == "team_pair" for i in issues)
    assert len(duplicate_game_ids(pd.concat([games, games]))) == 1


def test_source_disagreements_include_source_urls():
    games, teams = frames()
    games.loc[0, "sources_agree"] = "false"
    issue = next(i for i in run_checks(games, teams) if i.check == "source_disagreement")
    assert issue.game_id == games.loc[0, "game_id"]
    assert issue.url == "https://official.example/box"
    assert "https://other.example/schedule" in issue.message


def test_quarter_sum_includes_overtime_and_never_invents_missing_quarters():
    games, teams = frames()
    games.loc[0, "home_q1"] = 6
    assert any(i.check == "quarter_sum" for i in run_checks(games, teams))
    games.loc[0, "home_q1"] = 7
    games.loc[0, "num_ot"] = 2
    games.loc[0, "home_ot"] = 2
    games.loc[0, "home_pts"] = 9
    games.loc[0, "away_ot"] = 0
    assert not any(i.check in ("quarter_sum", "overtime") for i in run_checks(games, teams))
    games.loc[0, "away_ot"] = None
    assert any(i.check == "overtime" for i in run_checks(games, teams))
    games.loc[0, "home_q1"] = None
    games.loc[0, "home_pts"] = 99
    assert not any(
        i.check == "quarter_sum" and "home:" in i.message for i in run_checks(games, teams)
    )


@pytest.mark.parametrize(
    "column,value",
    [
        ("rush_att", -1),
        ("pass_att", "unknown"),
        ("punts", 1.5),
        ("time_of_possession_s", float("inf")),
        ("games_before", -1),
    ],
)
def test_impossible_stats_are_reported(column, value):
    games, teams = frames()
    teams.loc[0, column] = value
    assert any(
        i.check == "impossible_value" and column in i.message for i in run_checks(games, teams)
    )


def test_negative_yards_and_missing_values_are_allowed():
    games, teams = frames()
    for column in ("rush_yds", "pass_yds", "total_yds", "punt_yds"):
        teams.loc[0, column] = -17
    assert not any(i.check == "impossible_value" for i in run_checks(games, teams))


@pytest.mark.parametrize(
    "column,value",
    [("home_pts", -1), ("attendance", -1), ("num_ot", -1), ("neutral_site", "maybe")],
)
def test_impossible_game_values(column, value):
    games, teams = frames()
    games.loc[0, column] = value
    assert any(
        i.check == "impossible_value" and column in i.message for i in run_checks(games, teams)
    )


@pytest.mark.parametrize(
    "column,value,check",
    [
        ("opponent", "cornell", "team_context"),
        ("is_home", False, "team_context"),
        ("points", 99, "team_context"),
        ("game_id", "orphan", "orphan_team_row"),
    ],
)
def test_wrong_team_game_context(column, value, check):
    games, teams = frames()
    teams.loc[0, column] = value
    assert any(i.check == check for i in run_checks(games, teams))


def test_missing_and_malformed_identities_are_reported_without_crashing():
    games, teams = frames()
    games.loc[0, "home_team"] = pd.NA
    assert any(i.check == "missing_identity" for i in run_checks(games, teams))
    games, teams = frames()
    games.loc[0, "date"] = "2004-02-30"
    assert any(i.check == "game_date" for i in run_checks(games, teams))
    games, teams = frames()
    games.loc[0, "ivy_game"] = False
    assert any(i.check == "ivy_flag" for i in run_checks(games, teams))
    games, teams = frames()
    games.loc[0, "home_team"] = "yale"
    assert any(i.check == "team_pair" for i in run_checks(games, teams))


@pytest.mark.parametrize(
    "numerator,denominator",
    [
        ("pass_cmp", "pass_att"),
        ("pass_int", "pass_att"),
        ("third_down_conv", "third_down_att"),
        ("fourth_down_conv", "fourth_down_att"),
        ("fumbles_lost", "fumbles"),
    ],
)
def test_stat_bounds(numerator, denominator):
    games, teams = frames()
    teams.loc[0, numerator] = 2
    teams.loc[0, denominator] = 1
    assert any(
        i.check == "stat_bounds" and numerator in i.message for i in run_checks(games, teams)
    )


def test_turnover_total():
    games, teams = frames()
    teams.loc[0, ["pass_int", "fumbles_lost", "turnovers"]] = [1, 2, 4]
    assert any(i.check == "turnovers" for i in run_checks(games, teams))
    teams.loc[0, "turnovers"] = 3
    assert not any(i.check == "turnovers" for i in run_checks(games, teams))


def test_full_ivy_round_robin_and_current_seasons():
    schools = ["brown", "columbia", "cornell", "dartmouth", "harvard", "penn", "princeton", "yale"]
    pairs = [
        frames(home, away, f"20040901-{away}-at-{home}") for home, away in combinations(schools, 2)
    ]
    games = pd.concat([a for a, b in pairs], ignore_index=True)
    teams = pd.concat([b for a, b in pairs], ignore_index=True)
    assert run_checks(games, teams) == []
    games, teams = frames()
    games["split"] = "current"
    teams["split"] = "current"
    assert not any(i.check == "ivy_game_count" for i in run_checks(games, teams))


def test_schema_errors_do_not_crash_other_checks():
    games, teams = frames()
    assert any(i.check == "schema" for i in run_checks(games.drop(columns="season"), teams))
    assert duplicate_game_ids(pd.DataFrame()) == [
        Issue("error", "schema", None, "games.csv is missing game_id")
    ]


def test_saved_build_warnings_keep_url_and_reject_broken_csv(tmp_path):
    path = tmp_path / "build_warnings.csv"
    assert read_build_warnings(path) == []
    path.write_text("source_url,message\nhttps://example.test/raw,unrecognized stats\n")
    issue = read_build_warnings(path)[0]
    assert issue.url == "https://example.test/raw" and issue.check == "build_warning"
    path.write_text("wrong,columns\n")
    with pytest.raises(ValueError, match="columns"):
        read_build_warnings(path)
    path.write_text("source_url,message\nhttps://example.test/raw\n")
    with pytest.raises(ValueError, match="row"):
        read_build_warnings(path)


def test_report_counts_issues_urls_escaping_and_determinism(tmp_path):
    games, teams = frames()
    path = tmp_path / "report.md"
    issues = [
        Issue("warning", "parse_warning", None, "<script> bad | row", "https://example.test/raw"),
        Issue("error", "quarter_sum", "game1", "7 != 8"),
    ]
    write_report(issues, games, str(path))
    before = path.read_bytes()
    text = path.read_text()
    assert "| 2004 | train | 1 | 0 | 1 |" in text
    assert "&lt;script&gt;" in text and "<script>" not in text
    assert "https://example.test/raw" in text and "Errors: 1. Warnings: 1." in text
    write_report(issues[::-1], games, str(path))
    assert path.read_bytes() == before
    write_report([], games, str(path))
    assert "No issues found" in path.read_text()


def test_validate_cli_and_ci_duplicate_guard(tmp_path, capsys):
    games, teams = frames()
    directory = tmp_path / "processed"
    directory.mkdir()
    games.to_csv(directory / "games.csv", index=False)
    teams.to_csv(directory / "team_game_stats.csv", index=False)
    assert cli.main(["validate", "--data-dir", str(directory)]) == 0
    report = tmp_path / "reports/validation_report.md"
    assert report.exists() and "0 errors" in capsys.readouterr().out
    pd.concat([games, games]).to_csv(directory / "games.csv", index=False)
    before = report.read_bytes()
    assert cli.main(["validate", "--data-dir", str(directory), "--duplicates-only"]) == 1
    assert "duplicate_game_id" in capsys.readouterr().out
    assert report.read_bytes() == before
    assert cli.main(["validate", "--data-dir", str(tmp_path / "absent"), "--duplicates-only"]) == 0
    assert cli.main(["validate", "--data-dir", str(directory)]) == 1
