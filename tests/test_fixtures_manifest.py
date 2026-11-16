from pathlib import Path

import yaml

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_list_is_valid():
    entries = yaml.safe_load((FIXTURES / "fixtures.yaml").read_text())
    assert entries, "fixtures.yaml is empty"
    for name, url in entries.items():
        assert name.replace("_", "").isalnum(), name
        assert url.startswith("https://"), url
