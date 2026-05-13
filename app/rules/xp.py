"""
Experience points and character leveling for the RPG engine.

Uses the standard D&D 5e XP threshold and encounter-building tables.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# XP thresholds per level (cumulative XP needed to reach each level)
# ---------------------------------------------------------------------------
# Standard D&D 5e: level -> total XP required
XP_THRESHOLDS: dict[int, int] = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}

# ---------------------------------------------------------------------------
# XP thresholds per character by level and encounter difficulty (DMG ch. 3)
# ---------------------------------------------------------------------------
# Values represent the XP budget per character for an encounter of that
# difficulty at that level.
_XP_PER_CHAR: dict[int, dict[str, int]] = {
    1: {"easy": 25, "medium": 50, "hard": 75, "deadly": 100},
    2: {"easy": 50, "medium": 100, "hard": 150, "deadly": 200},
    3: {"easy": 75, "medium": 150, "hard": 225, "deadly": 400},
    4: {"easy": 125, "medium": 250, "hard": 375, "deadly": 500},
    5: {"easy": 250, "medium": 500, "hard": 750, "deadly": 1100},
    6: {"easy": 300, "medium": 600, "hard": 900, "deadly": 1400},
    7: {"easy": 350, "medium": 750, "hard": 1100, "deadly": 1700},
    8: {"easy": 450, "medium": 900, "hard": 1400, "deadly": 2100},
    9: {"easy": 550, "medium": 1100, "hard": 1600, "deadly": 2400},
    10: {"easy": 600, "medium": 1200, "hard": 1900, "deadly": 2800},
    11: {"easy": 800, "medium": 1600, "hard": 2400, "deadly": 3600},
    12: {"easy": 1000, "medium": 2000, "hard": 3000, "deadly": 4500},
    13: {"easy": 1100, "medium": 2200, "hard": 3400, "deadly": 5100},
    14: {"easy": 1250, "medium": 2500, "hard": 3800, "deadly": 5700},
    15: {"easy": 1400, "medium": 2800, "hard": 4300, "deadly": 6400},
    16: {"easy": 1600, "medium": 3200, "hard": 4800, "deadly": 7200},
    17: {"easy": 2000, "medium": 3900, "hard": 5900, "deadly": 8800},
    18: {"easy": 2100, "medium": 4200, "hard": 6300, "deadly": 9500},
    19: {"easy": 2400, "medium": 4900, "hard": 7300, "deadly": 10900},
    20: {"easy": 2800, "medium": 5700, "hard": 8500, "deadly": 12700},
}

_VALID_DIFFICULTIES = frozenset({"easy", "medium", "hard", "deadly"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_xp(
    encounter_difficulty: str,
    character_level: int,
    party_size: int = 1,
) -> dict:
    """Calculate the XP awarded for an encounter using the DMG encounter budget (not monster XP).

    Args:
        encounter_difficulty: One of ``"easy"``, ``"medium"``, ``"hard"``,
            or ``"deadly"``.
        character_level: The party's level (1-20).
        party_size: Number of characters in the party (default 1).

    Returns:
        A dict with:
        - **base_xp** (``int``): Total XP for the encounter
          (``per_character * party_size``).
        - **per_character** (``int``): XP per character (standard 5e
          per-character threshold for that level and difficulty).
        - **difficulty** (``str``): The difficulty label.
    """
    if encounter_difficulty not in _VALID_DIFFICULTIES:
        msg = f"Invalid difficulty '{encounter_difficulty}'. Must be one of {sorted(_VALID_DIFFICULTIES)}"
        raise ValueError(msg)

    if not isinstance(character_level, int):
        raise TypeError(
            f"Level must be an integer, got {type(character_level).__name__}"
        )

    if character_level < 1 or character_level > 20:
        raise ValueError(
            f"Invalid level '{character_level}'. Must be 1-20."
        )

    if party_size < 1:
        raise ValueError(
            f"Invalid party_size '{party_size}'. Must be >= 1."
        )

    per_char = _XP_PER_CHAR[character_level][encounter_difficulty]
    base_xp = per_char * party_size

    return {
        "base_xp": base_xp,
        "per_character": per_char,
        "difficulty": encounter_difficulty,
    }


def xp_to_next_level(current_level: int) -> int:
    """Return the XP needed to go from *current_level* to the next level.

    Args:
        current_level: The current level (1-19; level 20 is max).

    Returns:
        XP required to reach the next level. Returns 0 if already at
        max level (20).

    Raises:
        ValueError: If *current_level* is less than 1.
    """
    if current_level < 1:
        raise ValueError(
            f"Invalid level '{current_level}'. Must be 1-20."
        )
    if current_level >= 20:
        return 0
    return XP_THRESHOLDS[current_level + 1] - XP_THRESHOLDS[current_level]


def check_level_up(total_xp: int, current_level: int) -> dict:
    """Check whether a character levels up based on total XP.

    Args:
        total_xp: The character's total accumulated XP.
        current_level: The character's current level.

    Returns:
        A dict with:
        - **leveled_up** (``bool``): Whether the character gained at least
          one level.
        - **new_level** (``int``): The new level (same as current if no
          level-up).
        - **xp_remaining** (``int``): XP left after calculating the new
          level (for multi-level jumps).
    """
    if current_level < 1 or current_level > 20:
        raise ValueError(
            f"Invalid level '{current_level}'. Must be 1-20."
        )

    # Treat negative XP as 0 to avoid odd behaviour
    total_xp = max(0, total_xp)

    if current_level >= 20:
        return {"leveled_up": False, "new_level": 20, "xp_remaining": total_xp}

    # Find the highest level the total_xp supports
    new_level = current_level
    for level in range(current_level + 1, 21):
        if total_xp >= XP_THRESHOLDS[level]:
            new_level = level
        else:
            break

    leveled_up = new_level > current_level
    xp_remaining = total_xp - XP_THRESHOLDS[new_level]

    return {
        "leveled_up": leveled_up,
        "new_level": new_level,
        "xp_remaining": xp_remaining,
    }
