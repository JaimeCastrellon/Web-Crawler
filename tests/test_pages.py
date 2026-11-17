from pathlib import Path

import pytest

from ivydata.crawl.pages import challenge_provider, has_boxscore_content


@pytest.mark.parametrize("name", ["columbia", "harvard", "dartmouth"])
def test_archived_boxscores_allow_monitoring(name):
    html = (Path(__file__).parent / "fixtures" / f"boxscore_{name}_2004_yale.html").read_text()
    assert has_boxscore_content(html)
    assert challenge_provider(html + '<script src="/_Incapsula_Resource"></script>') is None


@pytest.mark.parametrize(
    "html",
    [
        '<div id="boxscorePageId"></div>',
        "<pre>Team Statistics</pre>",
        "<pre>Score by Quarters</pre>",
    ],
)
def test_empty_or_incomplete_boxscore_shape_does_not_hide_challenge(html):
    assert not has_boxscore_content(html)
    assert challenge_provider(html + '<script src="/_Incapsula_Resource"></script>') == "Incapsula"
