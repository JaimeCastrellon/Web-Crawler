from ivydata.cli import main
from ivydata.config import load_config


def test_eight_ivy_schools():
    cfg = load_config()
    ids = {s.id for s in cfg.schools}
    assert ids == {
        "brown", "columbia", "cornell", "dartmouth", "harvard", "penn", "princeton", "yale"
    }  # fmt: skip


def test_season_slugs():
    cfg = load_config()
    assert cfg.school("yale").season_slugs(2004) == ["2004", "2004-05"]
    assert cfg.school("cornell").season_slugs(2004) == ["2004-05", "2004"]
    assert cfg.school("yale").season_slugs(1999) == ["1999", "1999-00"]


def test_splits_and_skip_2020():
    sp = load_config().splits
    seasons = sp.seasons()
    assert seasons[0] == 2000 and seasons[-1] == 2026
    assert 2020 not in seasons
    assert sp.split_for(2000) == "train"
    assert sp.split_for(2023) == "train"
    assert sp.split_for(2024) == "test"
    assert sp.split_for(2025) == "test"
    assert sp.split_for(2026) == "current"


def test_splits_do_not_overlap():
    ranges = sorted(load_config().splits.ranges.values())
    for (_, hi), (lo, _) in zip(ranges, ranges[1:], strict=False):
        assert hi < lo


def test_politeness_floor():
    assert load_config().crawl.min_delay_seconds >= 3.0


def test_aliases_case_insensitive():
    al = load_config().team_aliases
    assert al["yale university"] == "yale"
    assert al["harv"] == "harvard"


def test_cli_config_runs(capsys):
    assert main(["config"]) == 0
    assert "yalebulldogs.com" in capsys.readouterr().out
