"""Small page-shape checks used during capture and discovery, before full parsing."""

import re

from selectolax.lexbor import LexborHTMLParser

GAME_SELECTOR = ".sidearm-schedule-game, .s-game-card"
CONTENT_SELECTOR = GAME_SELECTOR + ", article.box-score, article.sidearm-story-template"


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
    if any(node.text(strip=True) for node in tree.css(CONTENT_SELECTOR)):
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
