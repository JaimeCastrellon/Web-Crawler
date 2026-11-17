import csv
from pathlib import Path

import httpx
import pytest

from ivydata import cli
from ivydata.config import load_config
from ivydata.crawl import league
from ivydata.crawl.fetcher import FetchResult, RobotsDisallowed
from ivydata.crawl.pages import challenge_provider, has_boxscore_content
from ivydata.normalize.teams import canonical_team_id
from ivydata.parse.boxscore import parse_boxscore

FIXTURES = Path(__file__).parent / "fixtures"
INDEX = (FIXTURES / "league_statistics_2025.html").read_text()
BOX = (FIXTURES / "boxscore_league_2025_brown_cornell.html").read_text()
INDEX_URL = "https://ivyleague.com/stats.aspx?path=football&year=2025"


def test_saved_index_deduplicates_results_and_never_extracts_leaders():
    links = league.find_league_boxscore_links(INDEX, INDEX_URL, 2025)
    assert len(links) == 2 and all("boxscore.aspx?id=" in u for u in links)
    extra = """<table><tr><td>
    <a href="/boxscore.aspx?id=bad&path=basketball">wrong sport</a>
    <a href="https://elsewhere.example/boxscore.aspx?id=bad&path=football">host</a>
    <a href="/boxscore.aspx?path=football">missing id</a>
    <a href="/boxscore.aspx?id=bad&path=football&path=basketball">ambiguous</a>
    <a href="/teamstats.aspx?path=football&year=2025">season totals</a>
    </td></tr></table>"""
    assert league.find_league_boxscore_links(INDEX + extra, INDEX_URL, 2025) == links
    duplicate = (
        '<table><tr><td><a href="/boxscore.aspx?id=a%2Bb&path=football#stats">x</a>'
        '<a href="/boxscore.aspx?path=football&id=a%2bb">x</a></td></tr></table>'
    )
    assert len(league.find_league_boxscore_links(INDEX + duplicate, INDEX_URL, 2025)) == 3


@pytest.mark.parametrize("html", [INDEX.replace("2025 Football", "2026 Football"), "blocked"])
def test_wrong_season_or_challenge_index_fails_explicitly(html):
    with pytest.raises(ValueError, match="not a 2025"):
        league.find_league_boxscore_links(html, INDEX_URL, 2025)
    with pytest.raises(ValueError, match="no football box-score links"):
        league.find_league_boxscore_links(
            "<title>2025 Football - Overall Statistics</title>", INDEX_URL, 2025
        )


def test_conference_box_without_school_wrapper_has_exact_game_stats():
    box = parse_boxscore(BOX, "https://ivyleague.com/boxscore.aspx?id=fixture&path=football")
    assert not box.warnings
    assert (box.game["date"], box.game["home_raw"], box.game["away_raw"]) == (
        "2025-10-25",
        "Cornell",
        "Brown",
    )
    assert (box.game["home_pts"], box.game["away_pts"], box.game["num_ot"]) == (30, 24, 2)
    assert (box.game["home_ot"], box.game["away_ot"]) == (13, 7)
    brown, cornell = box.team_stats
    assert (brown["pass_yds"], cornell["pass_yds"]) == (471, 346)
    assert (brown["time_of_possession_s"], cornell["time_of_possession_s"]) == (1662, 1938)
    assert (brown["sacks_allowed"], cornell["sacks_allowed"]) == (3, 3)
    assert not any("record" in key or "wins" in key for key in box.game)
    script = '<script src="/_Incapsula_Resource?monitor"></script>'
    assert has_boxscore_content(BOX) and challenge_provider(script + BOX) is None
    assert challenge_provider(script) == "Incapsula"
    assert not has_boxscore_content("<table><caption>Team Statistics</caption></table>")


@pytest.fixture
def fake_league(tmp_path, monkeypatch):
    monkeypatch.setattr(league, "REPO_ROOT", tmp_path)
    links = league.find_league_boxscore_links(INDEX, INDEX_URL, 2025)
    responses = {INDEX_URL: (200, INDEX), links[0]: (200, BOX), links[1]: (200, BOX)}
    instances = []

    class FakeFetcher:
        def __init__(self, **options):
            self.options = options
            self.calls = []
            self.closed = False
            instances.append(self)

        def get(self, url):
            self.calls.append(url)
            response = responses[url]
            if isinstance(response, Exception):
                raise response
            status, text = response
            path = tmp_path / f"response-{len(self.calls)}.html"
            path.write_text(text)
            return FetchResult(url, status, path, "a" * 64, False, "2026-11-17T19:00:00Z")

        def close(self):
            self.closed = True

    monkeypatch.setattr(league, "Fetcher", FakeFetcher)
    return tmp_path, links, responses, instances


@pytest.mark.parametrize(
    "response,reason",
    [
        ((503, "unavailable"), "HTTP 503"),
        ((200, "blocked"), "Invalid isoformat"),
        ((200, BOX.replace("10/25/2025", "10/25/2024")), "season/teams"),
        (
            (
                200,
                BOX.replace("Team Statistics", "Other Statistics").replace("First Downs", "Other"),
            ),
            "lacks finals",
        ),
        (RobotsDisallowed("robots denied"), "robots denied"),
        (httpx.ConnectError("connection lost"), "connection lost"),
    ],
)
def test_recovery_records_failures_continues_and_clears_them_on_resume(
    fake_league, response, reason
):
    root, links, responses, instances = fake_league
    responses[links[0]] = response
    league.crawl_league(load_config(), [2020, 2025])
    path = root / "data/reports/league_recovery_errors.csv"
    errors = list(csv.DictReader(path.open()))
    assert len(errors) == 1 and errors[0]["url"] == links[0] and reason in errors[0]["error"]
    manifest = root / "data/manifest/recovered/ivy_league_boxscores.csv"
    boxes = [r for r in csv.DictReader(manifest.open()) if r["kind"] == "boxscore"]
    assert len(boxes) == 1 and boxes[0]["url"] == links[1] and boxes[0]["school"] == "brown"
    assert instances[-1].closed and instances[-1].calls == [INDEX_URL, *links]
    assert instances[-1].options["min_delay_seconds"] >= 3
    responses[links[0]] = (200, BOX)
    league.crawl_league(load_config(), [2025])
    assert list(csv.DictReader(path.open())) == []
    assert len([r for r in csv.DictReader(manifest.open()) if r["kind"] == "boxscore"]) == 2


def test_cli_explicit_selection_and_bad_index(fake_league):
    root, _, responses, instances = fake_league
    responses[INDEX_URL] = (200, INDEX.replace("2025 Football", "2026 Football"))
    assert cli.main(["league-boxscores", "--seasons", "2025", "--refresh"]) == 0
    assert instances[-1].calls == [INDEX_URL] and instances[-1].options["refresh"]
    assert "not a 2025" in (root / "data/reports/league_recovery_errors.csv").read_text()
    with pytest.raises(ValueError, match="configured splits"):
        league.crawl_league(load_config(), [1999])


def test_interrupted_box_validation_is_visible_until_resumed(fake_league, monkeypatch):
    root, links, _, instances = fake_league
    original = league.parse_boxscore

    def interrupted(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(league, "parse_boxscore", interrupted)
    with pytest.raises(KeyboardInterrupt):
        league.crawl_league(load_config(), [2025])
    errors = list(csv.DictReader((root / "data/reports/league_recovery_errors.csv").open()))
    assert errors[0]["url"] == links[0] and "validation pending" in errors[0]["error"]
    assert instances[-1].closed
    monkeypatch.setattr(league, "parse_boxscore", original)
    league.crawl_league(load_config(), [2025])
    assert list(csv.DictReader((root / "data/reports/league_recovery_errors.csv").open())) == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("UAlbany", "albany"),
        ("Central Conn. St.", "central-connecticut-state"),
        ("Youngstown St.", "youngstown-state"),
        ("Montana St.", "montana-state"),
    ],
)
def test_league_abbreviations_preserve_existing_game_identities(raw, expected):
    assert canonical_team_id(raw, load_config().team_aliases) == expected


def test_committed_league_boxes_cover_both_test_seasons_without_duplicate_games():
    root = Path(__file__).resolve().parents[1]
    with (root / "data/manifest/recovered/ivy_league_boxscores.csv").open() as stream:
        boxes = [r for r in csv.DictReader(stream) if r["kind"] == "boxscore"]
    assert len(boxes) == 107 and all(r["status"] == "200" for r in boxes)
    with (root / "data/processed/games.csv").open() as stream:
        games = list(csv.DictReader(stream))
    assert len(games) == 1355 and len({g["game_id"] for g in games}) == 1355
    matched = set()
    for box in boxes:
        matches = [g for g in games if box["url"] in g["source_urls"].split("|")]
        assert len(matches) == 1 and matches[0]["stats_level"] == "full"
        matched.add(matches[0]["game_id"])
    assert len(matched) == 107
    for year, count in [("2024", 52), ("2025", 55)]:
        season = [g for g in games if g["season"] == year]
        assert len(season) == count and all(g["stats_level"] == "full" for g in season)
