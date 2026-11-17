"""Small page-shape checks used during capture and discovery, before full parsing."""

import re

from selectolax.lexbor import LexborHTMLParser

GAME_SELECTOR = ".sidearm-schedule-game, .s-game-card"
BOX_SELECTOR = "article.box-score, .s-boxscore, .s-box-score, #boxscorePageId"
CONTENT_SELECTOR = GAME_SELECTOR + ", article.sidearm-story-template"


def declared_schedule_season(html: str) -> int | None:
    """Read a clear season declaration from a football-schedule title, if present."""
    title = LexborHTMLParser(html).css_first("title")
    if title is None:
        return None
    match = re.search(r"\b(\d{4})(?:[-–]\d{2,4})?\s+Football\s+Schedule\b", title.text(), re.I)
    return int(match[1]) if match else None


def challenge_provider(html: str) -> str | None:
    """Identify known challenge pages, allowing monitoring scripts on real sports pages."""
    tree = LexborHTMLParser(html)
    if _has_boxscore_content(tree) or any(
        node.text(strip=True) for node in tree.css(CONTENT_SELECTOR)
    ):
        return None
    for node in tree.css("script[src], iframe[src]"):
        source = (node.attributes.get("src") or "").lower()
        for marker, provider in (
            ("_incapsula_resource", "Incapsula"),
            ("/cdn-cgi/challenge-platform/", "Cloudflare"),
        ):
            if marker in source:
                return provider
    return None


def has_schedule_games(html: str) -> bool:
    """Recognize populated legacy Sidearm rows and current Sidearm game cards."""
    return any(node.text(strip=True) for node in LexborHTMLParser(html).css(GAME_SELECTOR))


def _has_boxscore_content(tree: LexborHTMLParser) -> bool:
    if any(node.text(strip=True) for node in tree.css(BOX_SELECTOR)):
        return True
    # Conference-hosted Sidearm boxes omit the school-site wrapper. Require
    # populated score and statistics tables before treating scripts as monitoring.
    scores = stats = False
    for table in tree.css("table"):
        caption = table.css_first("caption")
        label = re.sub(r"\s+", " ", caption.text()).strip().lower() if caption else ""
        rows = table.css("tbody tr")
        if label == "team score by quarter":
            scores |= len(rows) == 2 and all(len(row.css("th,td")) >= 6 for row in rows)
        elif label == "team statistics":
            stats |= any(len(row.css("th,td")) == 3 for row in rows)
    if scores and stats:
        return True
    text = "\n".join(node.text() for node in tree.css("pre"))
    return (
        "team statistics" in text.lower()
        and len(re.findall(r"^\s*\S[^\n]*?\.{2,}\s+(?:\d+\s+){4,}-\s*\d+", text, re.M)) >= 2
    )


def has_boxscore_content(html: str) -> bool:
    """Recognize populated Sidearm containers or an archived text box score."""
    return _has_boxscore_content(LexborHTMLParser(html))
