"""
Plausibility classification — determines whether an action is reasonable
for a given character based on their stats, class, and level.

Provides guidance for the DM on when to say NO, when to call for a hard
check, and when the genie rule should apply.  All functions return
structured dicts with a ``category``, ``reason``, and suggested ``dc``.

The categories, from easiest to hardest:

- **trivial** — Well within the character's capabilities.  Auto-success.
- **plausible** — Reasonable for class/level.  Normal DC (10-15).
- **ambitious** — A stretch but theoretically possible.  High DC (15-20).
- **implausible** — Very unlikely.  Very high DC (20-25) or auto-fail.
- **impossible** — Beyond any reasonable chance.  Auto-fail, no roll.
"""

from __future__ import annotations

import logging
from typing import Any

from app.character.model import Character

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plausibility category definitions
# ---------------------------------------------------------------------------

CATEGORY_ORDER: list[str] = [
    "trivial",
    "plausible",
    "ambitious",
    "implausible",
    "impossible",
]

CATEGORY_DC: dict[str, int | None] = {
    "trivial": None,  # Auto-success — no roll needed
    "plausible": 12,  # Normal difficulty
    "ambitious": 17,  # Hard — needs good roll
    "implausible": 23,  # Very hard — needs exceptional roll
    "impossible": None,  # Auto-fail — no roll allowed
}

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "trivial": "Well within the character's abilities. No roll needed.",
    "plausible": "Reasonable for the character's class and level. "
    "Call for a normal check.",
    "ambitious": "A stretch, but theoretically possible. "
    "Call for a hard check (DC 15-20).",
    "implausible": "Very unlikely for this character. "
    "Call for a very hard check (DC 20-25) or consider auto-failure.",
    "impossible": "Beyond any reasonable chance for this character. "
    "Auto-failure — describe why it cannot work.",
}

# ---------------------------------------------------------------------------
# Keyword matching helper
# ---------------------------------------------------------------------------


def _matches(text: str, keyword: str) -> bool:
    """Check if *keyword* matches *text* using flexible word matching.

    For single-word keywords, checks word boundaries (so "cast" does not
    match "castle").  For multi-word keywords, checks if ALL individual
    words appear in *text* — this catches variations like "become a god"
    matching the keyword "become god".
    """
    words = keyword.split()
    if len(words) == 1:
        # Single word: check word-boundary match
        return f" {keyword} " in f" {text} "
    # Multi-word: check if all words appear (word-boundary for each)
    return all(f" {w} " in f" {text} " for w in words)


def _any_match(text: str, keywords: list[str]) -> bool:
    """Return True if any keyword in *keywords* matches *text*."""
    return any(_matches(text, kw) for kw in keywords)


# ---------------------------------------------------------------------------
# Class-based capability hints
# ---------------------------------------------------------------------------

# Actions that are purely impossible for whole classes
CLASS_BLACKLIST: dict[str, list[str]] = {
    "Fighter": [
        "cast",
        "magic",
        "teleport",
        "become god",
        "wish",
        "resurrect",
        "summon angel",
    ],
    "Rogue": [
        "cast",
        "magic",
        "teleport",
        "become god",
        "wish",
        "resurrect",
        "summon angel",
    ],
    "Mage": [
        "become god",
        "wish",
        "turn into dragon",
    ],
    "Cleric": [
        "become god",
        "wish",
        "command deity",
    ],
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_action(character: Character, action: str) -> dict[str, Any]:
    """Classify a player action by plausibility for the given character.

    Parameters
    ----------
    character : Character
        The player character.
    action : str
        A description of what the player is trying to do.

    Returns
    -------
    dict
        A dict with these keys:

        - **category** (str): One of ``trivial``, ``plausible``,
          ``ambitious``, ``implausible``, ``impossible``.
        - **reason** (str): A human-readable explanation.
        - **dc** (int | None): Suggested DC, or ``None`` for
          trivial/impossible.
        - **allow_roll** (bool): Whether a tool roll should be allowed.
    """
    action_lower = action.lower()
    char_class = character.character_class

    logger.debug(
        "plausibility.classify_action: class=%s level=%d action='%s'",
        char_class,
        character.level,
        action[:80],
    )

    # ------------------------------------------------------------------
    # Check class blacklist first — these are always impossible
    # ------------------------------------------------------------------
    if char_class in CLASS_BLACKLIST:
        for keyword in CLASS_BLACKLIST[char_class]:
            if _matches(action_lower, keyword):
                logger.debug(
                    "plausibility.classify_action: → impossible (class blacklist: %s)",
                    keyword,
                )
                return {
                    "category": "impossible",
                    "reason": (
                        f"A level {character.level} {char_class} cannot "
                        f"{keyword} — it is beyond their capabilities."
                    ),
                    "dc": None,
                    "allow_roll": False,
                }

    # ------------------------------------------------------------------
    # Score based on level — higher level = more ambitious actions possible
    # ------------------------------------------------------------------
    level = character.level

    # Level-based cap: a level 1 character starts capped at "ambitious"
    if level <= 1:
        implausible_keywords = [
            "teleport",
            "plane shift",
            "raise dead",
            "resurrect",
            "legendary",
            "artifact",
            "ancient dragon",
            "lich",
            "army of",
            "invade",
            "overthrow kingdom",
        ]
        if _any_match(action_lower, implausible_keywords):
            logger.debug(
                "plausibility.classify_action: → impossible (low level — %s)",
                action[:80],
            )
            return {
                "category": "impossible",
                "reason": (
                    f"A level {level} adventurer is not ready for "
                    f"such a feat.  You lack the power, knowledge, "
                    f"and experience."
                ),
                "dc": None,
                "allow_roll": False,
            }

    # ------------------------------------------------------------------
    # Ability score check — stats matter
    # ------------------------------------------------------------------
    abilities = character.abilities or {}

    # Check for actions that rely on strength
    strength = abilities.get("STR", 10)
    strength_keywords = [
        "lift",
        "push",
        "pull",
        "break",
        "bend",
        "carry",
        "throw",
        "smash",
        "shatter",
        "wrestle",
    ]
    if _any_match(action_lower, strength_keywords):
        if strength <= 8:
            logger.debug(
                "plausibility.classify_action: → implausible (STR=%d)", strength
            )
            return {
                "category": "implausible",
                "reason": (
                    f"With STR {strength}, this character is exceptionally "
                    f"weak.  This action is nearly impossible for them."
                ),
                "dc": 23,
                "allow_roll": True,
            }
        if strength >= 14:
            logger.debug("plausibility.classify_action: → plausible (STR=%d)", strength)
            return {
                "category": "plausible",
                "reason": (
                    f"With STR {strength}, the character has the raw strength for this."
                ),
                "dc": 12,
                "allow_roll": True,
            }

    # Check for actions that rely on intelligence
    intelligence = abilities.get("INT", 10)
    int_keywords = [
        "solve",
        "decipher",
        "ancient language",
        "arcana",
        "forget",
        "remember",
        "research",
        "craft",
        "alchemy",
    ]
    if _any_match(action_lower, int_keywords):
        if intelligence < 8:
            logger.debug(
                "plausibility.classify_action: → implausible (INT=%d)", intelligence
            )
            return {
                "category": "implausible",
                "reason": (
                    f"With INT {intelligence}, the character is not "
                    f"learned enough for this."
                ),
                "dc": 22,
                "allow_roll": True,
            }
        if intelligence >= 14:
            logger.debug(
                "plausibility.classify_action: → plausible (INT=%d)", intelligence
            )
            return {
                "category": "plausible",
                "reason": (
                    f"With INT {intelligence}, the character's intellect "
                    f"serves them well here."
                ),
                "dc": 12,
                "allow_roll": True,
            }

    # Check for actions that rely on charisma
    charisma = abilities.get("CHA", 10)
    cha_keywords = [
        "persuade",
        "intimidate",
        "charm",
        "deceive",
        "bargain",
        "negotiate",
        "seduce",
        "convince",
        "lie",
        "bluff",
    ]
    if _any_match(action_lower, cha_keywords):
        if charisma <= 8:
            logger.debug("plausibility.classify_action: → ambitious (CHA=%d)", charisma)
            return {
                "category": "ambitious",
                "reason": (
                    f"With CHA {charisma}, social interactions are a "
                    f"struggle.  This will be difficult."
                ),
                "dc": 18,
                "allow_roll": True,
            }
        if charisma >= 14:
            logger.debug("plausibility.classify_action: → plausible (CHA=%d)", charisma)
            return {
                "category": "plausible",
                "reason": (f"With CHA {charisma}, the character has natural charm."),
                "dc": 12,
                "allow_roll": True,
            }

    # ------------------------------------------------------------------
    # Default: plausible for most general actions
    # ------------------------------------------------------------------
    logger.debug("plausibility.classify_action: → plausible (default)")
    return {
        "category": "plausible",
        "reason": "The action is reasonable for this character.",
        "dc": 12,
        "allow_roll": True,
    }


def suggest_dc(character: Character, category: str) -> dict[str, Any]:
    """Suggest a DC for a given plausibility category, adjusted by level.

    Parameters
    ----------
    character : Character
        The player character.
    category : str
        One of ``trivial``, ``plausible``, ``ambitious``, ``implausible``,
        ``impossible``.

    Returns
    -------
    dict
        A dict with ``category``, ``base_dc``, ``level_adjustment``,
        ``suggested_dc``, and ``allow_roll``.
    """
    if category not in CATEGORY_ORDER:
        raise ValueError(
            f"Invalid category {category!r}.  Must be one of {CATEGORY_ORDER}."
        )

    base_dc = CATEGORY_DC.get(category)
    if base_dc is None:
        return {
            "category": category,
            "base_dc": None,
            "level_adjustment": 0,
            "suggested_dc": None,
            "allow_roll": category == "trivial",
        }

    # Lower-level characters face slightly harder DCs
    level = character.level
    if level <= 2:
        level_adj = 0
    elif level <= 4:
        level_adj = -1  # Easier for mid-level characters
    elif level <= 7:
        level_adj = -2
    else:
        level_adj = -3  # High-level characters find hard things easier

    suggested = max(base_dc + level_adj, 5)

    logger.debug(
        "plausibility.suggest_dc: category=%s base=%s level_adj=%d suggested=%d",
        category,
        base_dc,
        level_adj,
        suggested,
    )
    return {
        "category": category,
        "base_dc": base_dc,
        "level_adjustment": level_adj,
        "suggested_dc": suggested,
        "allow_roll": True,
    }


def get_categories() -> dict[str, str]:
    """Return the full set of plausibility categories and their descriptions.

    Returns
    -------
    dict[str, str]
        Mapping of category name to description.
    """
    return dict(CATEGORY_DESCRIPTIONS)
