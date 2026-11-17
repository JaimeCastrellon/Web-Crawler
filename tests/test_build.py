import csv
from dataclasses import replace
from hashlib import sha1, sha256
from pathlib import Path

import pandas as pd
import pytest

from ivydata import cli
from ivydata.build import (
    GAME_COLUMNS,
    PREGAME_FIELDS,
    TEAM_COLUMNS,
    add_pregame_records,
    assign_splits,
    build,
)
from ivydata.config import Splits, load_config
from ivydata.crawl.fetcher import FetchResult
from ivydata.crawl.manifest import Manifest

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = load_config()


def records(rows):
    return pd.DataFrame(
        [
            {
                "game_id": f"g{i}",
                "date": day,
                "season": season,
                "team": team,
                "opponent": opponent,
                "points": points,
                "points_allowed": allowed,
            }
            for i, (day, season, team, opponent, points, allowed) in enumerate(rows)
        ]
    )


def test_pregame_counts_only_completed_earlier_games_and_resets_each_season():
    frame = records(
        [
            ("2024-09-01", 2024, "yale", "holy-cross", 7, 0),
            ("2024-09-08", 2024, "yale", "cornell", 7, 14),
            ("2024-09-15", 2024, "yale", "brown", 14, 14),
            ("2024-09-22", 2024, "yale", "harvard", None, None),
            ("2024-09-29", 2024, "yale", "penn", 21, 7),
            ("2025-09-01", 2025, "yale", "cornell", 7, 14),
        ]
    )
    before = frame.copy(deep=True)
    result = add_pregame_records(frame.iloc[::-1])
    assert result[PREGAME_FIELDS].values.tolist() == [
        [0, 0, 0, 0, 0, 0],
        [1, 1, 0, 0, 0, 0],
        [2, 1, 1, 0, 0, 1],
        [3, 1, 1, 1, 0, 1],
        [3, 1, 1, 1, 0, 1],
        [0, 0, 0, 0, 0, 0],
    ]
    pd.testing.assert_frame_equal(frame, before)
    # An unplayed game in an earlier week does not acquire a final score or win.
    assert pd.isna(result.iloc[3]["points"])
    changed = frame.copy()
    changed.loc[4, ["points", "points_allowed"]] = [0, 99]
    pd.testing.assert_frame_equal(
        result.iloc[:4][PREGAME_FIELDS], add_pregame_records(changed).iloc[:4][PREGAME_FIELDS]
    )


def test_same_date_results_never_count_toward_each_other():
    frame = records(
        [
            ("2024-09-01", 2024, "yale", "brown", 7, 0),
            ("2024-09-01", 2024, "yale", "penn", 0, 7),
            ("2024-09-08", 2024, "yale", "cornell", 7, 0),
        ]
    )
    result = add_pregame_records(frame)
    assert result["games_before"].tolist() == [0, 0, 2]
    assert result["wins_before"].tolist() == [0, 0, 1]
    assert result["ivy_losses_before"].tolist() == [0, 0, 1]


def test_records_separate_teams_and_ignore_existing_record_columns():
    frame = records(
        [
            ("2024-09-01", 2024, "yale", "brown", 7, 0),
            ("2024-09-01", 2024, "brown", "yale", 0, 7),
            ("2024-09-08", 2024, "brown", "penn", 14, 7),
        ]
    )
    frame["wins_before"] = 999
    result = add_pregame_records(frame)
    assert result["wins_before"].tolist() == [0, 0, 0]
    assert result["losses_before"].tolist() == [0, 0, 1]


def test_invalid_pregame_identities_and_dates_fail():
    frame = records([("2024-09-01", 2024, "yale", "brown", 7, 0)])
    with pytest.raises(ValueError, match="duplicate"):
        add_pregame_records(pd.concat([frame, frame]))
    with pytest.raises(ValueError, match="missing"):
        add_pregame_records(frame.drop(columns="team"))
    frame.loc[0, "date"] = "2024-02-30"
    with pytest.raises(ValueError):
        add_pregame_records(frame)


def test_splits_follow_config_skip_2020_and_do_not_mutate():
    frame = pd.DataFrame({"season": [2000, 2020, 2023, 2024, 2025, 2026]})
    assert assign_splits(frame, CONFIG)["split"].tolist() == [
        "train",
        "train",
        "test",
        "test",
        "current",
    ]
    assert "split" not in frame
    changed = replace(
        CONFIG,
        splits=Splits(
            2000,
            2026,
            frozenset({2020}),
            {"train": (2000, 2024), "test": (2025, 2025), "current": (2026, 2026)},
        ),
    )
    assert assign_splits(frame, changed)["split"].tolist() == [
        "train",
        "train",
        "train",
        "test",
        "current",
    ]
    with pytest.raises(ValueError, match="outside"):
        assign_splits(pd.DataFrame({"season": [1999]}), CONFIG)
    with pytest.raises(ValueError, match="nonmissing"):
        assign_splits(pd.DataFrame({"season": [None]}), CONFIG)
    overlap = replace(
        CONFIG, splits=replace(CONFIG.splits, ranges={"one": (2000, 2026), "two": (2024, 2025)})
    )
    with pytest.raises(ValueError, match="exactly one"):
        assign_splits(pd.DataFrame({"season": [2024]}), overlap)


@pytest.fixture
def dataset(tmp_path):
    raw = tmp_path / "data/raw"
    out = tmp_path / "data/processed"

    def source(name, school, season, kind="boxscore", recovered=False, status=200, html=None):
        url = f"https://{school}.example.test/{name}"
        content = (html if html is not None else (FIXTURES / f"{name}.html").read_text()).encode()
        path = raw / url.split("/")[2] / f"{sha1(url.encode()).hexdigest()}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        target = (
            raw.parent / "manifest" / ("recovered/" + name + ".csv" if recovered else "urls.csv")
        )
        manifest = Manifest(target)
        manifest.record(
            FetchResult(url, status, path, sha256(content).hexdigest(), True, "2026-11-16"),
            school,
            season,
            kind,
            str(season),
        )
        manifest.save()
        return path, url, target

    source("schedule_yale_2004", "yale", 2004, "schedule")
    for school in ("cornell", "penn", "brown", "columbia", "harvard", "dartmouth"):
        source(f"boxscore_{school}_2004_yale", school, 2004, recovered=True)
    return raw, out, source


def read(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def snapshot(out):
    return {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*.csv")}


def test_build_real_sources_schema_records_missing_values_and_repeatability(dataset):
    raw, out, _ = dataset
    build(raw, out, CONFIG)
    games = read(out / "games.csv")
    teams = read(out / "team_game_stats.csv")
    assert len(games) == 10 and len(teams) == 20
    assert sum(g["stats_level"] == "full" for g in games) == 6
    assert list(games[0]) == GAME_COLUMNS and list(teams[0]) == TEAM_COLUMNS
    assert all(g["split"] == "train" for g in games)
    assert all(g["ivy_game"] in ("true", "false") for g in games)
    assert all(t["is_home"] in ("true", "false") for t in teams)
    assert not any(k in games[0] for k in ("wins", "losses", "record"))
    first = next(t for t in teams if t["team"] == "yale")
    last = [t for t in teams if t["team"] == "yale"][-1]
    assert [first[k] for k in PREGAME_FIELDS] == ["0"] * 6
    assert [last[k] for k in PREGAME_FIELDS] == ["9", "5", "4", "0", "3", "3"]
    assert first["pass_int"] == first["turnovers"] == ""
    cornell_yale = next(t for t in teams if t["team"] == "yale" and "cornell" in t["game_id"])
    assert cornell_yale["pass_int"] == "0" and cornell_yale["turnovers"] == "0"
    assert all(".0" not in t[k] for t in teams for k in ("rush_att", "points", *PREGAME_FIELDS))
    assert (out / "games.csv").read_bytes() == (out / "train/games.csv").read_bytes()
    assert read(out / "test/games.csv") == read(out / "current/games.csv") == []
    before = snapshot(out)
    build(raw, out, CONFIG)
    assert snapshot(out) == before
    assert read(raw.parent / "reports/build_warnings.csv") == []


def test_test_current_and_skipped_seasons_and_empty_split_files(dataset):
    raw, out, source = dataset
    source("boxscore_yale_2024_dartmouth", "yale", 2024)
    source("boxscore_yale_2025_harvard", "yale", 2025)
    source("schedule_harvard_2026_upcoming", "harvard", 2026, "schedule")
    source("skipped", "yale", 2020, "schedule", html="not read")
    build(raw, out, CONFIG)
    assert len(read(out / "test/games.csv")) == 2
    current = read(out / "current/games.csv")
    assert len(current) == 1 and current[0]["home_pts"] == current[0]["away_pts"] == ""
    assert current[0]["neutral_site"] == "true"
    assert all(g["season"] != "2020" for g in read(out / "games.csv"))


def test_header_records_never_change_built_features(dataset):
    raw, out, source = dataset
    build(raw, out, CONFIG)
    before = snapshot(out)
    original = (FIXTURES / "boxscore_harvard_2004_yale.html").read_text()
    changed = original.replace("(5-5,3-4)", "(99-99,88-88)").replace("(10-0,7-0)", "(44-44,77-77)")
    assert original != changed
    source("boxscore_harvard_2004_yale", "harvard", 2004, recovered=True, html=changed)
    build(raw, out, CONFIG)
    assert snapshot(out) == before


@pytest.mark.parametrize("fault", ["missing", "checksum"])
def test_bad_cache_reports_urls_and_preserves_previous_outputs(dataset, fault):
    raw, out, source = dataset
    path, url, _ = source("boxscore_yale_2025_harvard", "yale", 2025)
    build(raw, out, CONFIG)
    before = snapshot(out)
    if fault == "missing":
        path.unlink()
    else:
        path.write_text("damaged")
    with pytest.raises(ValueError, match="processed files were not replaced"):
        build(raw, out, CONFIG)
    assert snapshot(out) == before
    warnings = read(raw.parent / "reports/build_warnings.csv")
    assert any(w["source_url"] == url for w in warnings)


def test_failed_challenged_and_wrong_season_sources_remain_in_warnings(dataset):
    raw, out, source = dataset
    _, failed, _ = source("http500", "yale", 2004, status=500, html="failure")
    _, blocked, _ = source(
        "challenge", "yale", 2004, html='<script src="/_Incapsula_Resource"></script>'
    )
    _, wrong, _ = source("boxscore_yale_2025_harvard", "yale", 2004)
    _, unknown, _ = source("unknown", "yale", 2004, html="unrecognized archive")
    _, pdf, _ = source("pdf", "yale", 2004, html="%PDF-1.4 unsupported")
    build(raw, out, CONFIG)
    assert len(read(out / "games.csv")) == 10
    text = (raw.parent / "reports/build_warnings.csv").read_text()
    assert all(url in text for url in (failed, blocked, wrong, unknown, pdf))
    assert "HTTP 500" in text and "Incapsula" in text and "conflicts with manifest season" in text


def test_conflicting_manifest_does_not_replace_output(dataset):
    raw, out, _ = dataset
    build(raw, out, CONFIG)
    before = snapshot(out)
    source = raw.parent / "manifest/recovered/harvard-copy.csv"
    original = (raw.parent / "manifest/recovered/boxscore_harvard_2004_yale.csv").read_text()
    source.write_text(original.replace(",200,", ",500,"))
    with pytest.raises(ValueError, match="conflicting manifest"):
        build(raw, out, CONFIG)
    assert snapshot(out) == before


def test_missing_manifest_and_no_usable_data_do_not_create_dataset(tmp_path):
    raw = tmp_path / "data/raw"
    out = tmp_path / "data/processed"
    with pytest.raises(FileNotFoundError):
        build(raw, out, CONFIG)
    assert not out.exists()
    manifest = Manifest(raw.parent / "manifest/urls.csv")
    manifest.save()
    build(raw, out, CONFIG)
    assert read(out / "games.csv") == []
    assert len(snapshot(out)) == 8


def test_cli_build_runs_offline_with_explicit_paths(dataset, capsys):
    raw, out, _ = dataset
    assert cli.main(["build", "--raw-dir", str(raw), "--out-dir", str(out)]) == 0
    assert "Built 10 games" in capsys.readouterr().out
    assert len(read(out / "team_game_stats.csv")) == 20


def test_no_usable_source_fails_and_retains_warning_report(dataset):
    raw, out, source = dataset
    config = replace(CONFIG, splits=Splits(2025, 2025, frozenset(), {"test": (2025, 2025)}))
    _, url, _ = source(
        "bad-schedule", "yale", 2025, "schedule", html="<title>2026 Football Schedule</title>"
    )
    with pytest.raises(ValueError, match="no usable games"):
        build(raw, out, config)
    assert not out.exists()
    assert url in (raw.parent / "reports/build_warnings.csv").read_text()


def test_no_network_fetches_and_no_unmanifested_cache_pages(dataset):
    raw, out, _ = dataset
    path = raw / "untracked.example.test/extra.html"
    path.parent.mkdir(parents=True)
    path.write_text((FIXTURES / "boxscore_yale_2025_harvard.html").read_text())
    build(raw, out, CONFIG)
    assert len(read(out / "games.csv")) == 10
    assert all(row["season"] == "2004" for row in read(out / "games.csv"))


def test_unsafe_output_and_split_paths_fail_before_writing(dataset):
    raw, out, _ = dataset
    with pytest.raises(ValueError, match="outside the raw cache"):
        build(raw, raw / "processed", CONFIG)
    config = replace(CONFIG, splits=replace(CONFIG.splits, ranges={"../escape": (2000, 2026)}))
    with pytest.raises(ValueError, match="directory names"):
        build(raw, out, config)
    assert not out.exists()
