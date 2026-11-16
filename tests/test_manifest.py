import csv
from pathlib import Path

import pytest

from ivydata.crawl.fetcher import FetchResult
from ivydata.crawl.manifest import MANIFEST_COLUMNS, Manifest


def result(url, status=200):
    return FetchResult(url, status, None, "a" * 64, False, "2026-11-16T20:00:00+00:00")


def test_manifest_roundtrip_upsert_sort_and_determinism(tmp_path):
    path = tmp_path / "manifest/urls.csv"
    manifest = Manifest(path)
    manifest.record(result("https://yale.example/z"), "yale", 2025, "schedule", "2025")
    manifest.record(result("https://yale.example/a"), "yale", 2004, "boxscore", "2004-05")
    manifest.record(result("https://brown.example/robots.txt"), "brown", 2025, "robots")
    manifest.save()
    loaded = Manifest(path)
    loaded.record(result("https://yale.example/z", 404), "yale", 2025, "schedule", "2025")
    loaded.save()
    before = path.read_bytes()
    rows = list(csv.DictReader(path.open()))
    assert list(rows[0]) == MANIFEST_COLUMNS
    assert [(r["school"], r["season"], r["status"]) for r in rows] == [
        ("brown", "2025", "200"),
        ("yale", "2004", "200"),
        ("yale", "2025", "404"),
    ]
    assert rows[0]["season_slug"] == "" and rows[1]["season_slug"] == "2004-05"
    assert rows[2]["fetched_at"] == "2026-11-16T20:00:00+00:00"
    Manifest(path).save()
    assert path.read_bytes() == before


def test_manifest_empty_and_invalid_input(tmp_path):
    path = tmp_path / "urls.csv"
    Manifest(path).save()
    assert path.read_text() == ",".join(MANIFEST_COLUMNS) + "\n"
    path.write_text("bad,columns\n")
    with pytest.raises(ValueError, match="columns"):
        Manifest(path)
    path.write_text(",".join(MANIFEST_COLUMNS) + "\nmissing,fields\n")
    with pytest.raises(ValueError, match="row"):
        Manifest(path)


def test_manifest_interruption_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "urls.csv"
    manifest = Manifest(path)
    manifest.record(result("https://yale.example/a"), "yale", 2025, "schedule")
    manifest.save()
    before = path.read_bytes()
    manifest.record(result("https://yale.example/b"), "yale", 2025, "boxscore")
    original_replace = Path.replace

    def interrupt(self, target):
        if Path(target) == path:
            raise InterruptedError("simulated interruption")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", interrupt)
    with pytest.raises(InterruptedError):
        manifest.save()
    assert path.read_bytes() == before
    assert len(list(tmp_path.iterdir())) == 1
