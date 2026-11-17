"""Canonical team ids. Spec: docs/TASKS.md, Task 6."""

from __future__ import annotations

import html
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)
_unknown: set[str] = set()
IVY_TEAMS = frozenset(
    {"brown", "columbia", "cornell", "dartmouth", "harvard", "penn", "princeton", "yale"}
)


def _clean(raw: str) -> str:
    name = " ".join(unicodedata.normalize("NFKC", html.unescape(raw)).split()).casefold()
    # Prefix order varies ("at #8 Harvard" / "#8 at Harvard").
    previous = None
    while previous != name:
        previous = name
        name = re.sub(r"^(?:at\b|vs\.?(?:\s|$)|#\s*\d+\b|no\.?\s*\d+\b)\s*", "", name).strip()
    previous = None
    while previous != name:
        previous = name
        name = re.sub(r"\s*\(\s*\d+\s*[-–]\s*\d+[^)]*\)\s*$", "", name).strip()
    return re.sub(r"\s+\d+\s*[-–]\s*\d+(?:\s*[-–]\s*\d+)?$", "", name).strip()


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.casefold()).strip("-")


def canonical_team_id(raw_name: str, aliases: dict[str, str]) -> str:
    """Map a raw team name to a lowercase slug using ``Config.team_aliases``.

    Strip rankings ("#8 Harvard"), "at"/"vs." prefixes and trailing records. Unknown names
    are slugified ("Holy Cross" -> "holy-cross") and logged once.
    """
    name = _clean(raw_name)
    if not name or not _slug(name):
        raise ValueError(f"empty/unusable team name: {raw_name!r}")
    for alias, canonical in aliases.items():
        if name == _clean(alias) or name == canonical.casefold():
            return _slug(canonical)
    slug = _slug(name)
    if slug not in _unknown:
        logger.warning("Unknown team name %r; using %s", raw_name, slug)
        _unknown.add(slug)
    return slug


def is_ivy(team_id: str) -> bool:
    return team_id in IVY_TEAMS
