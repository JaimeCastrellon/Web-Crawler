from dataclasses import replace
from hashlib import sha1, sha256
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from ivydata import cli
from ivydata.config import Splits, load_config
from ivydata.crawl import coverage
from ivydata.crawl.discover import find_boxscore_links
from ivydata.crawl.fetcher import FetchResult
from ivydata.crawl.manifest import Manifest

BOX_HTML = '<article class="box-score"><table><tr><td>Yale 24</td></tr></table></article>'


def game(box=None, score="W, 24-17", modern=False):
    link = f'<a href="{box}">Box score</a>' if box else ""
    if modern:
        return (
            '<div class="s-game-card">Sep 18 vs Yale'
            f'<span data-test-id="s-game-card-standard__header-game-team-score">{score}</span>'
            f"{link}</div>"
        )
    return (
        '<li class="sidearm-schedule-game">Sep 18 vs Yale'
        f'<div class="sidearm-schedule-game-result">{score}</div>{link}</li>'
    )


@pytest.fixture
def audit(tmp_path, monkeypatch):
    config = load_config()
    config = replace(
        config,
        schools=tuple(
            school for school in config.schools if school.id in {"brown", "cornell", "penn", "yale"}
        ),
        splits=Splits(2004, 2004, frozenset(), {"train": (2004, 2004)}),
    )
    monkeypatch.setattr(coverage, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(coverage, "load_config", lambda: config)
    monkeypatch.setattr(cli, "load_config", lambda: config)
    manifest = Manifest(tmp_path / "data/manifest/urls.csv")

    def record(school, url, html, kind="schedule", slug="2004", status=200):
        path = (
            tmp_path
            / "data/raw"
            / urlsplit(url).hostname
            / f"{sha1(url.encode()).hexdigest()}.html"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
        manifest.record(
            FetchResult(
                url,
                status,
                path,
                sha256(path.read_bytes()).hexdigest(),
                True,
                "2026-11-16T20:00:00+00:00",
            ),
            school,
            2004,
            kind,
            slug,
        )
        manifest.save()
        return path

    return tmp_path, config, record


@pytest.mark.parametrize(
    "games,boxes,scores,expected",
    [
        (10, 10, 10, "full"),
        (10, 10, 0, "full"),
        (10, 1, 10, "partial"),
        (10, 0, 10, "score_only"),
        (10, 0, 1, "score_only"),
        (0, 0, 0, "missing"),
        (10, 0, 0, "missing"),
    ],
)
def test_coverage_levels(games, boxes, scores, expected):
    assert coverage.coverage_level(games, boxes, scores) == expected


@pytest.mark.parametrize("different_hash", [False, True])
def test_shared_robots_allows_context_changes_but_not_conflicting_content(audit, different_hash):
    root, _, record = audit
    url = "https://brownbears.com/robots.txt"
    body = record("brown", url, "User-agent: *\nAllow: /\n", kind="robots")
    recovery = Manifest(root / "data/manifest/recovered/other_context.csv")
    digest = "0" * 64 if different_hash else sha256(body.read_bytes()).hexdigest()
    recovery.record(
        FetchResult(url, 200, body, digest, True, "2026-11-17T20:00:00Z"),
        "penn",
        2008,
        "robots",
    )
    recovery.save()
    if different_hash:
        with pytest.raises(ValueError, match="conflicting manifest"):
            coverage.build_coverage_report()
    else:
        assert len(coverage.build_coverage_report()) == 4


@pytest.mark.parametrize("counts", [(-1, 0, 0), (1, -1, 0), (1, 0, -1), (1, 2, 0), (1, 0, 2)])
def test_invalid_counts_fail(counts):
    with pytest.raises(ValueError):
        coverage.coverage_level(*counts)


def test_report_all_levels_grid_and_byte_identical_rerun(audit, capsys):
    root, config, record = audit
    for school, available in [("brown", 2), ("cornell", 1), ("penn", 0)]:
        base = config.school(school).base_url
        boxes = [f"{base}/sports/football/stats/2004/yale/boxscore/{i}" for i in [1, 2]]
        html = "".join(game(box) for box in boxes) if school != "penn" else game() * 2
        record(school, base + "/sports/football/schedule/2004", html)
        for box in boxes[:available]:
            record(school, box, BOX_HTML, kind="boxscore")
        if school == "cornell":
            record(school, boxes[1], "missing", kind="boxscore", status=404)
    report = coverage.build_coverage_report()
    assert list(report.columns) == coverage.REPORT_COLUMNS
    assert list(report["school"]) == ["brown", "cornell", "penn", "yale"]
    assert list(report["level"]) == ["full", "partial", "score_only", "missing"]
    assert list(report["games_on_schedule"]) == [2, 2, 2, 0]
    assert list(report["boxscores_found"]) == [2, 1, 0, 0]
    assert "HTTP 404" in report.iloc[1]["notes"]
    assert "not crawled" in report.iloc[3]["notes"]
    path = root / "data/reports/coverage_report.csv"
    before = path.read_bytes()
    assert cli.main(["coverage"]) == 0
    assert path.read_bytes() == before
    output = capsys.readouterr().out
    assert next(line for line in output.splitlines() if line.startswith("brown")).split() == [
        "brown",
        "F",
    ]
    assert "F full | P partial | S score-only | - missing" in output


@pytest.mark.parametrize("fault", ["missing", "checksum", "challenge", "empty", "status", "year"])
def test_bad_schedule_is_reported_and_fallback_used(audit, fault):
    _, config, record = audit
    base = config.school("yale").base_url
    first = base + "/sports/football/schedule/2004"
    second = base + "/sports/football/schedule/2004-05"
    html = game()
    if fault == "challenge":
        html = '<script src="/_Incapsula_Resource?challenge"></script>'
    elif fault == "empty":
        html = "navigation only"
    elif fault == "year":
        html = "<title>2026 Football Schedule</title>" + game()
    path = record("yale", first, html, status=404 if fault == "status" else 200)
    if fault == "missing":
        path.unlink()
    elif fault == "checksum":
        path.write_text("corrupt")
    record("yale", second, game(), slug="2004-05")
    row = coverage.build_coverage_report().set_index("school").loc["yale"]
    assert row["schedule_url"] == second and row["season_slug"] == "2004-05"
    assert row["level"] == "score_only" and first in row["notes"]


@pytest.mark.parametrize(
    "name,school,expected_games,expected_boxes",
    [
        ("schedule_yale_2004", "yale", 10, 9),
        ("schedule_brown_2025_excerpt", "brown", 2, 2),
    ],
)
def test_real_legacy_and_modern_fixture_counts(audit, name, school, expected_games, expected_boxes):
    _, config, record = audit
    html = (Path(__file__).parent / "fixtures" / f"{name}.html").read_text()
    url = config.school(school).base_url + "/sports/football/schedule/2004"
    record(school, url, html)
    # The audit only checks row shape, score presence, and link availability, not game dates.
    for link in find_boxscore_links(html, url, config.boxscore_regex):
        record(school, link, BOX_HTML, kind="boxscore")
    row = coverage.build_coverage_report().set_index("school").loc[school]
    assert row["games_on_schedule"] == expected_games
    assert row["boxscores_found"] == expected_boxes
    assert row["level"] == ("full" if expected_boxes == expected_games else "partial")


def test_unfetched_failed_and_duplicate_boxes_never_claim_full(audit):
    _, config, record = audit
    base = config.school("yale").base_url
    urls = [f"{base}/sports/football/stats/2004/penn/boxscore/{i}" for i in [1, 2, 3, 4]]
    record(
        "yale",
        base + "/sports/football/schedule/2004",
        game(urls[0]) + game(urls[0]) + game(urls[1]) + game(urls[2]) + game(urls[3]),
    )
    record("yale", urls[0], BOX_HTML, kind="boxscore")
    record("yale", urls[1], '<script src="/_Incapsula_Resource"></script>', kind="boxscore")
    record("yale", urls[2], "not a box score", kind="boxscore")
    row = coverage.build_coverage_report().set_index("school").loc["yale"]
    assert row["games_on_schedule"] == 5 and row["boxscores_found"] == 1
    assert row["level"] == "partial"
    assert all(url in row["notes"] for url in urls)


def test_future_schedule_preserves_context_without_inventing_results(audit):
    _, config, record = audit
    url = config.school("yale").base_url + "/sports/football/schedule/2004"
    record("yale", url, game(score="", modern=True))
    row = coverage.build_coverage_report().set_index("school").loc["yale"]
    assert row["games_on_schedule"] == 1 and row["schedule_url"] == url
    assert row["level"] == "missing" and "no results" in row["notes"]


def test_uncrawled_skips_2020_and_includes_transport_failures(tmp_path, monkeypatch):
    config = load_config()
    config = replace(
        config, schools=(config.school("yale"),), splits=Splits(2019, 2021, frozenset({2020}))
    )
    monkeypatch.setattr(coverage, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(coverage, "load_config", lambda: config)
    errors = tmp_path / "data/reports/crawl_errors.csv"
    errors.parent.mkdir(parents=True)
    errors.write_text(
        "url,school,season,kind,error\nhttps://school.example/2019,yale,2019,schedule,ReadTimeout\n"
    )
    report = coverage.build_coverage_report()
    assert list(report["season"]) == [2019, 2021]
    assert list(report["level"]) == ["missing", "missing"]
    assert "ReadTimeout: https://school.example/2019" in report.iloc[0]["notes"]


def test_report_write_interruption_preserves_previous_report(audit, monkeypatch):
    root, _, _ = audit
    coverage.build_coverage_report()
    path = root / "data/reports/coverage_report.csv"
    before = path.read_bytes()
    replace_path = Path.replace

    def interrupt(self, target):
        if Path(target) == path:
            raise InterruptedError
        return replace_path(self, target)

    monkeypatch.setattr(Path, "replace", interrupt)
    with pytest.raises(InterruptedError):
        coverage.build_coverage_report()
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


def test_malformed_input_fails_without_replacing_report(audit):
    root, _, _ = audit
    coverage.build_coverage_report()
    report = root / "data/reports/coverage_report.csv"
    before = report.read_bytes()
    manifest = root / "data/manifest/urls.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("wrong,columns\n")
    with pytest.raises(ValueError, match="invalid CSV columns"):
        coverage.build_coverage_report()
    assert report.read_bytes() == before


@pytest.mark.parametrize("name,modern", [("brown_2004_yale", True), ("harvard_2004_yale", False)])
def test_newer_and_archived_boxscore_shapes_are_usable(audit, name, modern):
    _, config, record = audit
    base = config.school("yale").base_url
    url = base + "/sports/football/stats/2004/harvard/boxscore/1"
    html = (Path(__file__).parent / "fixtures" / f"boxscore_{name}.html").read_text()
    if modern:
        html = '<div id="boxscorePageId">' + html + "</div>"
    html += '<script src="/_Incapsula_Resource?monitor"></script>'
    record("yale", base + "/sports/football/schedule/2004", game(url))
    record("yale", url, html, kind="boxscore")
    row = coverage.build_coverage_report().query("school == 'yale'").iloc[0]
    assert row["level"] == "full"
    assert row["boxscores_found"] == 1


def test_recovered_manifest_matches_opponent_copy_by_date_and_teams(audit):
    root, config, record = audit
    source = Path(__file__).parent / "fixtures"
    schedule = config.school("yale").base_url + "/sports/football/schedule/2004"
    record("yale", schedule, (source / "schedule_yale_2004.html").read_text())
    box = "https://cornellbigred.com/sports/football/stats/2004-05/yale-university/boxscore/4180"
    body = record(
        "cornell",
        box,
        '<article class="box-score">'
        + (source / "boxscore_cornell_2004_yale.html").read_text()
        + "</article>",
        kind="boxscore",
        slug="2004-05",
    )
    # Move the box entry into a recovery-only manifest so discovery cannot rely on urls.csv.
    import csv

    path = root / "data/manifest/urls.csv"
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    recovered = root / "data/manifest/recovered/cornell.csv"
    recovered.parent.mkdir()
    for target, selected in [
        (path, [r for r in rows if r["url"] != box]),
        (recovered, [r for r in rows if r["url"] == box]),
    ]:
        with target.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), lineterminator="\n")
            writer.writeheader()
            writer.writerows(selected)
    row = coverage.build_coverage_report().query("school == 'yale'").iloc[0]
    assert row["level"] == "partial" and row["boxscores_found"] == 1
    assert "recovered box score matched by teams/date" in row["notes"] and box in row["notes"]
    # A checksum failure must remove this recovered availability again.
    body.write_text("damaged")
    row = coverage.build_coverage_report().query("school == 'yale'").iloc[0]
    assert row["boxscores_found"] == 0 and row["level"] == "score_only"


def test_wrong_season_recovery_does_not_inflate_coverage(audit):
    _, config, record = audit
    source = Path(__file__).parent / "fixtures"
    record(
        "yale",
        config.school("yale").base_url + "/sports/football/schedule/2004",
        (source / "schedule_yale_2004.html").read_text(),
    )
    url = "https://yale.example.test/wrong-season"
    record("yale", url, (source / "boxscore_yale_2025_harvard.html").read_text(), kind="boxscore")
    row = coverage.build_coverage_report().query("school == 'yale'").iloc[0]
    assert row["boxscores_found"] == 0
    assert "conflicts with manifest season" in row["notes"]
