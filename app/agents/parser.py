"""
DM Response Parser — extracts structured data from the DM's XML-style output.

The Dungeon Master emits structured XML tags interleaved with narrative text.
This module parses those tags into Python dicts for downstream processing
(narrative display, tool execution, world state changes, NPC requests).

Tag types:
  - ``<narrative>...</narrative>`` — The story text shown to the player.
  - ``<tool_request name="..." params='{...}' />`` — A request to invoke a
    deterministic tool.
  - ``<state_change action="..." path="..." value="..." />`` — A proposed
    modification to world state.
  - ``<npc_request npc_id="..." context="..." />`` — A request for an NPC
    agent (reserved for future use).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_dm_response(response_text: str) -> dict[str, Any]:
    """Parse DM structured response into component parts.

    Uses regex to extract each XML-style tag type from the response text.
    Missing or malformed tags are handled gracefully — the returned dict
    always contains all four keys with sensible defaults.

    Parameters
    ----------
    response_text : str
        The raw text output from the DM language model, which may contain
        narrative text interleaved with XML-style tags.

    Returns
    -------
    dict[str, Any]
        A dictionary with the following keys:

        - **narrative** (``str``):
          The story text extracted from ``<narrative>`` tags.  Empty string
          if no narrative tag is found.
        - **tool_requests** (``list[dict]``):
          Each element has ``name`` (str) and ``params`` (dict) keys.
          Empty list if none found.
        - **state_changes** (``list[dict]``):
          Each element has ``action`` (str), ``path`` (str), and
          ``value`` (any) keys.  Empty list if none found.
        - **npc_requests** (``list[dict]``):
          Each element has ``npc_id`` (str) and ``context`` (str) keys.
          Empty list if none found.
    """
    if not response_text or not isinstance(response_text, str):
        return _empty_result()

    narrative = _extract_narrative(response_text)
    # Strip any residual XML tags that the LLM may have generated
    # inside the narrative content (e.g. <output name='Dialogue'/>).
    narrative = re.sub(r"<[^>]*>", "", narrative)
    # Strip leaked markdown bold artifacts (**narrative**, **tool_request**, etc.)
    narrative = _strip_markdown_bold(narrative)
    # Strip leaked backtick-wrapped state change attributes
    narrative = _strip_backtick_state_attrs(narrative)
    tool_requests = _extract_tool_requests(response_text)
    state_changes = _extract_state_changes(response_text)
    npc_requests = _extract_npc_requests(response_text)

    return {
        "narrative": narrative,
        "tool_requests": tool_requests,
        "state_changes": state_changes,
        "npc_requests": npc_requests,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _empty_result() -> dict[str, Any]:
    """Return a default empty parse result."""
    return {
        "narrative": "",
        "tool_requests": [],
        "state_changes": [],
        "npc_requests": [],
    }


_NARRATIVE_RE = re.compile(
    r"<narrative>\s*(.*?)\s*</narrative>", re.DOTALL | re.IGNORECASE
)


def _extract_narrative(text: str) -> str:
    """Extract content from the first ``<narrative>`` tag pair."""
    match = _NARRATIVE_RE.search(text)
    if match:
        return match.group(1).strip()
    logger.warning(
        "No <narrative> tag found in response (first 200 chars): %s",
        text[:200],
    )
    return ""


# Regex for self-closing tags of the form:
#   <tag_name attr1="val1" attr2='{"json":"val"}' />
# Captures: tag_name, then all attributes as a raw string.
_SELF_CLOSING_TAG_RE = re.compile(r"<(\w+)\s+([^>]+?)\s*/>", re.DOTALL | re.IGNORECASE)

# Regex to extract individual key="value" or key='value' pairs.
_ATTR_RE = re.compile(
    r"""(\w+)\s*=\s*"""
    r""""((?:[^"\\]|\\.)*)" """  # double-quoted value
    r"""|"""
    r"""(\w+)\s*=\s*"""
    r"""'((?:[^'\\]|\\.)*)'""",  # single-quoted value
    re.VERBOSE,
)


def _extract_tool_requests(text: str) -> list[dict[str, Any]]:
    """Extract all ``<tool_request>`` tags from the response text.

    Each tool request must have a ``name`` attribute (string) and may have
    a ``params`` attribute (JSON string parsed into a dict).  If ``params``
    is missing or not valid JSON, it defaults to an empty dict.
    """
    requests: list[dict[str, Any]] = []
    for match in _SELF_CLOSING_TAG_RE.finditer(text):
        if match.group(1).lower() != "tool_request":
            continue
        attrs = _parse_attributes(match.group(2))
        name = attrs.get("name", "")
        if not name:
            continue

        params_raw = attrs.get("params", "{}")
        if isinstance(params_raw, str):
            try:
                params = json.loads(params_raw)
            except (json.JSONDecodeError, ValueError):
                params = {}
        else:
            params = {}

        requests.append({"name": name, "params": params})
    return requests


def _extract_state_changes(text: str) -> list[dict[str, Any]]:
    """Extract all ``<state_change>`` tags from the response text.

    Each state change must have ``action``, ``path``, and ``value``
    attributes.  ``value`` is parsed as JSON if possible; if parsing fails,
    it is kept as a raw string.
    """
    changes: list[dict[str, Any]] = []
    for match in _SELF_CLOSING_TAG_RE.finditer(text):
        if match.group(1).lower() != "state_change":
            continue
        attrs = _parse_attributes(match.group(2))
        action = attrs.get("action", "")
        path = attrs.get("path", "")
        raw_value = attrs.get("value", "")

        if not action or not path:
            continue

        # Try parsing value as JSON; fall back to raw string
        value = _try_parse_json(raw_value)

        changes.append({"action": action, "path": path, "value": value})
    return changes


def _extract_npc_requests(text: str) -> list[dict[str, str]]:
    """Extract all ``<npc_request>`` tags from the response text.

    Each NPC request must have an ``npc_id`` attribute.  All other
    attributes (``context``, ``goal``, ``personality``, ``mood``) are
    optional and returned as-is from the parsed tag.
    """
    requests: list[dict[str, str]] = []
    for match in _SELF_CLOSING_TAG_RE.finditer(text):
        if match.group(1).lower() != "npc_request":
            continue
        attrs = _parse_attributes(match.group(2))
        npc_id = attrs.get("npc_id", "")
        if not npc_id:
            continue
        requests.append(attrs)
    return requests


def _parse_attributes(attr_text: str) -> dict[str, str]:
    """Parse key="value" attribute pairs from a raw attribute string.

    Supports both double-quoted and single-quoted values.  Returns a dict
    mapping attribute names to their string values.  Malformed pairs are
    silently ignored.
    """
    attrs: dict[str, str] = {}
    for match in _ATTR_RE.finditer(attr_text):
        # Double-quoted: groups 1 (name) and 2 (value)
        if match.group(1) is not None:
            attrs[match.group(1)] = match.group(2)
        # Single-quoted: groups 3 (name) and 4 (value)
        elif match.group(3) is not None:
            attrs[match.group(3)] = match.group(4)
    return attrs


def _try_parse_json(value: str) -> Any:
    """Try to parse *value* as JSON; return the raw string on failure.

    Handles the common case where attribute values are JSON objects,
    arrays, numbers, booleans, or null.
    """
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


# Regex for markdown bold patterns like **narrative**, **tool_request**, etc.
_MARKDOWN_BOLD_RE = re.compile(r"\*\*[a-zA-Z_]+\*\*")


def _strip_markdown_bold(text: str) -> str:
    """Strip leaked markdown bold artifacts from narrative text.

    The DM sometimes wraps tag-like names in markdown bold markers,
    e.g. **narrative**, **tool_request**.  These are not intentional
    markdown formatting — strip them entirely.
    """
    return _MARKDOWN_BOLD_RE.sub("", text)


# Regex for backtick-wrapped state change attributes like
# `action="set" path="location" value="village_street"`
_BACKTICK_STATE_ATTR_RE = re.compile(r"`[^`]*?(?:action=|path=|value=)[^`]*`")


def _strip_backtick_state_attrs(text: str) -> str:
    """Strip leaked backtick-wrapped state change attributes from narrative.

    The DM sometimes outputs raw state change attributes inside backticks,
    e.g. `action="set" path="location" value="village_street"`.  These
    leak through if they appear outside of XML tags.
    """
    return _BACKTICK_STATE_ATTR_RE.sub("", text)
