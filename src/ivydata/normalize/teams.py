"""Canonical team ids. Spec: docs/TASKS.md, Task 6."""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

IVY_TEAMS = frozenset(
    {"brown", "columbia", "cornell", "dartmouth", "harvard", "penn", "princeton", "yale"}
)

_seen_unknown: set[str] = set()

# leading poll ranks as printed by different sites: "#8", "No. 8", "(8)", "24 24", "24 ARV", "RV"
_RANK = re.compile(r"^(?:(?:#\s*\d+|no\.\s*\d+|\(\d+\)|\d+|arv|rv)\s+)+", re.I)
_UNIV = re.compile(r"^university of\s+|\s+university$", re.I)
_PREFIX = re.compile(r"^(?:at|vs\.?|@)\s+", re.I)
_SUFFIX = re.compile(r"\s*(?:\(\d+-\d+(?:-\d+)?\)|\*+)\s*$")


def clean_team_name(raw_name: str) -> str:
    """Strip rankings ("#8 Harvard"), "at"/"vs." prefixes, records and asterisks."""
    s = " ".join(raw_name.split())
    for _ in range(3):
        s2 = _SUFFIX.sub("", _RANK.sub("", _PREFIX.sub("", s))).strip()
        if s2 == s:
            break
        s = s2
    return s


def slugify(name: str) -> str:
    s = name.lower().replace("&", " and ").replace("'", "").replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def canonical_team_id(raw_name: str, aliases: dict[str, str]) -> str:
    """Map a raw team name to a lowercase slug using ``Config.team_aliases``.

    Strip rankings ("#8 Harvard"), "at"/"vs." prefixes and trailing records. Unknown names
    are slugified ("Holy Cross" -> "holy-cross") and logged once.
    """
    name = clean_team_name(raw_name)
    key = name.lower()
    if key in aliases:
        return aliases[key]
    short = _UNIV.sub("", name).strip()  # "Bucknell University" -> "Bucknell"
    if short.lower() in aliases:
        return aliases[short.lower()]
    slug = slugify(short or name)
    if slug in aliases:
        return aliases[slug]
    if slug not in _seen_unknown:
        _seen_unknown.add(slug)
        log.debug("team %r -> %s (not in team_aliases.yaml)", raw_name, slug)
    return slug


def is_ivy(team_id: str) -> bool:
    return team_id in IVY_TEAMS
