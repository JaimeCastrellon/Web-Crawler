import logging

import pytest

from ivydata.config import load_config
from ivydata.normalize import teams


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Yale University", "yale"),
        ("YALE", "yale"),
        ("YAL", "yale"),
        ("  at #8 Harvard (5-3, 3-1) ", "harvard"),
        ("No. 12 vs. Pennsylvania", "penn"),
        ("vs. Dartmouth College (5-3-1)", "dartmouth"),
        ("BRWN", "brown"),
        ("Holy Cross", "holy-cross"),
        ("Saint Francis (Pa.)", "saint-francis-pa"),
        ("San José State", "san-jose-state"),
        (" Texas A&amp;M ", "texas-a-m"),
    ],
)
def test_team_normalization(raw, expected):
    assert teams.canonical_team_id(raw, load_config().team_aliases) == expected


def test_unknown_logged_once(caplog, monkeypatch):
    monkeypatch.setattr(teams, "_unknown", set())
    with caplog.at_level(logging.WARNING):
        assert teams.canonical_team_id("Holy Cross", {}) == "holy-cross"
        assert teams.canonical_team_id("at HOLY CROSS", {}) == "holy-cross"
    assert len(caplog.records) == 1
    assert "Holy Cross" in caplog.text
    assert (
        teams.canonical_team_id(
            "College of the Holy Cross", {"college of the holy cross": "holy-cross"}
        )
        == "holy-cross"
    )


@pytest.mark.parametrize("raw", ["", "   ", "#8", "vs. ", "!!!"])
def test_unusable_team_names_fail(raw):
    with pytest.raises(ValueError):
        teams.canonical_team_id(raw, {})


def test_is_ivy():
    assert all(teams.is_ivy(t) for t in teams.IVY_TEAMS)
    assert not teams.is_ivy("holy-cross")
    assert not teams.is_ivy("Yale")


@pytest.mark.parametrize(
    "raw",
    [
        "Harvard (5–3, 3–1 Ivy)",
        "Harvard (5-3) (3-1 Ivy)",
        "Harvard 5-3",
        "Harvard ( 5-3, Ivy 3-1 )",
    ],
)
def test_decorated_records_never_become_team_ids(raw):
    assert teams.canonical_team_id(raw, load_config().team_aliases) == "harvard"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("(RV) Harvard", "harvard"),
        ("(RV) Yale", "yale"),
        ("vs. (RV) Dartmouth", "dartmouth"),
        ("#8/10 Rhode Island", "rhode-island"),
    ],
)
def test_brown_schedule_rankings(raw, expected):
    assert teams.canonical_team_id(raw, load_config().team_aliases) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("#24/ARV Dartmouth College", "dartmouth"),
        ("#25/-- Colgate University", "colgate"),
        ("RV/NR Yale University", "yale"),
        ("#22/#25 Harvard University", "harvard"),
        ("#RV Colgate University", "colgate"),
        ("Fordham University (Homecoming)", "fordham"),
        ("University at Albany", "albany"),
    ],
)
def test_saved_export_name_variants(raw, expected):
    assert teams.canonical_team_id(raw, load_config().team_aliases) == expected
