"""
Record Keeper Agent — Entity Memory Manager for the RPG.

The Record Keeper is responsible for two analysis passes around each DM
turn:

1. **Pre-DM** — analyses the player's input and current narrative to
   produce a context summary (timeline, plot threads, relevant entities)
   injected into the DM's prompt window.

2. **Post-DM** — examines the DM's narrative output, extracts entity
   changes (NPCs, places, items), and persists them to ``EntityStorage``.

Gracefully degrades when no LLM provider is available: falls back to
simple keyword-based entity matching for pre-DM and returns empty analysis
for post-DM.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.entity_persistence import EntityStorage
from app.agents.npc import compress_text
from app.agents.record_keeper_schemas import EntityChangeLog
from app.llm.base import LLMProvider
from app.world.model import WorldState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------


@dataclass
class RecordKeeperContext:
    """Pre-DM analysis result injected into the DM's context.

    Attributes
    ----------
    timeline_summary : str
        Concise timeline of recent narrative events, one line per turn.
    relevant_entities : list[dict]
        Entity records relevant to the current player input.
    plot_threads : list[str]
        Active and unresolved plot threads extracted from the narrative.
    dm_suggestions : list[str]
        Suggestions for the DM, including causality chains and narrative
        inconsistencies.
    context_text : str
        Combined context string ready for injection into the DM's prompt.
    """

    timeline_summary: str = ""
    relevant_entities: list[dict] = field(default_factory=list)
    plot_threads: list[str] = field(default_factory=list)
    dm_suggestions: list[str] = field(default_factory=list)
    context_text: str = ""


@dataclass
class EntityOperation:
    """A single entity operation extracted from the DM's narrative.

    Attributes
    ----------
    action : str
        One of ``"create"``, ``"update"``, ``"deactivate"``.
    entity_type : str
        One of ``"npc"``, ``"place"``, ``"item"``.
    entity_id : str
        The unique identifier for the entity.
    fields : dict
        Field name → value pairs to set on the entity (e.g.
        ``{"name": "Gribbits", "notes": "Wounded"}``).
    """

    action: str
    entity_type: str
    entity_id: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class PostDMAnalysis:
    """Post-DM analysis result.

    Attributes
    ----------
    entity_operations : list[EntityOperation]
        Operations to apply to entity storage.
    changelog_entries : list[EntityChangeLog]
        Change-log entries to persist for audit trail.
    new_plot_threads : list[str]
        New plot threads discovered in this turn.
    resolved_plot_threads : list[str]
        Plot threads that were resolved in this turn.
    raw_llm_response : str
        The full raw LLM response text (useful for debugging).
    """

    entity_operations: list[EntityOperation] = field(default_factory=list)
    changelog_entries: list[EntityChangeLog] = field(default_factory=list)
    new_plot_threads: list[str] = field(default_factory=list)
    resolved_plot_threads: list[str] = field(default_factory=list)
    raw_llm_response: str = ""


# ---------------------------------------------------------------------------
# Plot Branch System Prompt
# ---------------------------------------------------------------------------

PLOT_SYSTEM_PROMPT: str = """
# ROLE

You are an analytical scribe serving the Dungeon Master.  Your task is to
review the recent narrative and produce a structured timeline, identify
plot threads, and flag narrative elements the DM should track.

# TASK

Analyse the provided recent session turns and produce:

1. A **timeline** of narrative events — 1–3 sentences per relevant turn.
2. **Unresolved plot threads** — active mysteries, dangling hooks, and
   unresolved questions in the story.
3. **Causality chains** — how recent events may trigger future
   consequences or reveal narrative inconsistencies.

# OUTPUT FORMAT

Use the XML tags below to structure your response.  Every tag must be
present, even if empty.

<timeline>
<entry turn="1">The player character arrived at the Dark Forest edge, following
goblin tracks into the undergrowth.</entry>
<entry turn="2">Encountered a wounded goblin scout who revealed the chieftain's
location in exchange for mercy.</entry>
</timeline>

<plot_threads>
<thread status="open">Who is the mysterious goblin chieftain?</thread>
<thread status="open">Why are the goblins raiding the village?</thread>
<thread status="resolved">The old well in the village — explored and cleared of
vermin.</thread>
</plot_threads>

<causality>
The player's attack on the goblin scout may provoke retaliation from the
chieftain.
The player now knows the chieftain's location, enabling a direct
confrontation.
</causality>

# CONSTRAINTS

- Base your analysis strictly on the provided narrative text.
- Do not invent events, characters, or details not present in the input.
- Keep entries concise — 1–3 sentences per timeline entry.
- For plot threads, use ``status="open"`` for active threads and
  ``status="resolved"`` for threads concluded in the recent narrative.
- If no information is available for a section, output the tag pair with
  no content (e.g. ``<timeline></timeline>``).
"""


# ---------------------------------------------------------------------------
# Entity Branch System Prompt
# ---------------------------------------------------------------------------

ENTITY_SYSTEM_PROMPT: str = """
# ROLE

You are a meticulous record keeper for a fantasy RPG.  Your job is to read
the Dungeon Master's narrative output and extract structured information
about entities (NPCs, places, and items) that appear in the story.

# TASK

Examine the DM's narrative text and identify every entity mentioned:

- **NPCs** — characters, creatures, or beings the player interacts with.
- **Places** — locations, rooms, buildings, or regions visited or described.
- **Items** — objects acquired, used, lost, or interacted with.

For each identified entity, determine what action is needed:

- **create** — a new entity appearing for the first time.  Provide all
  available details from the narrative.
- **update** — an existing entity with new information.  Only include
  fields that have changed.
- **deactivate** — an entity that is destroyed, killed, or permanently
  removed from the story.

# OUTPUT FORMAT

Use the XML structure below to report entity changes.

<entity_changes>
<entity action="update" type="npc" id="gribbits">
<field name="notes">Wounded during encounter with the player</field>
<field name="last_seen">Dark Forest camp</field>
</entity>
<entity action="create" type="place" id="dark_forest_path">
<field name="name">Dark Forest Path</field>
<field name="description">A narrow trail winding through ancient oaks,
lit by faint bioluminescent fungi</field>
</entity>
<entity action="create" type="item" id="rusted_key">
<field name="name">Rusted Iron Key</field>
<field name="description">A cold, rusted iron key found under a loose
stone</field>
</entity>
</entity_changes>

# CONSTRAINTS

- **Never invent information** not present in the narrative text.
- Entity IDs should be short, descriptive, lowercase, and use underscores
  (e.g. ``dark_forest_path``, ``rusted_key``).
- The ``action`` attribute must be one of: ``create``, ``update``,
  ``deactivate``.
- The ``type`` attribute must be one of: ``npc``, ``place``, ``item``.
- Include a ``<field name="name">`` entry for every ``create`` action.
- Only report fields that are explicitly mentioned or clearly implied by
  the narrative.
- If no entities are mentioned, return an empty
  ``<entity_changes></entity_changes>`` tag.
"""


# ---------------------------------------------------------------------------
# Compiled regex patterns for XML parsing
# ---------------------------------------------------------------------------

# Timeline entry: <entry turn="N">text</entry>
_TIMELINE_ENTRY_RE = re.compile(
    r'<entry\s+turn\s*=\s*"(\d+)"\s*>(.*?)</entry>',
    re.DOTALL | re.IGNORECASE,
)

# Plot thread: <thread status="open|resolved">text</thread>
_PLOT_THREAD_RE = re.compile(
    r'<thread(?:\s+status\s*=\s*"(\w+)")?\s*>(.*?)</thread>',
    re.DOTALL | re.IGNORECASE,
)

# Entity change: <entity action="..." type="..." id="...">...</entity>
_ENTITY_CHANGE_RE = re.compile(
    r"<entity"
    r'\s+action\s*=\s*"(\w+)"'
    r'\s+type\s*=\s*"(\w+)"'
    r'\s+id\s*=\s*"([^"]+)"'
    r"\s*>(.*?)</entity>",
    re.DOTALL | re.IGNORECASE,
)

# Field within entity: <field name="...">value</field>
_ENTITY_FIELD_RE = re.compile(
    r'<field\s+name\s*=\s*"([^"]+)"\s*>(.*?)</field>',
    re.DOTALL | re.IGNORECASE,
)

# XML wrapper tags
_TIMELINE_WRAPPER_RE = re.compile(
    r"<timeline>(.*?)</timeline>", re.DOTALL | re.IGNORECASE
)

_PLOT_THREADS_WRAPPER_RE = re.compile(
    r"<plot_threads>(.*?)</plot_threads>", re.DOTALL | re.IGNORECASE
)

_CAUSALITY_WRAPPER_RE = re.compile(
    r"<causality>(.*?)</causality>", re.DOTALL | re.IGNORECASE
)

_ENTITY_CHANGES_WRAPPER_RE = re.compile(
    r"<entity_changes>(.*?)</entity_changes>", re.DOTALL | re.IGNORECASE
)


# ---------------------------------------------------------------------------
# XML parsing helpers — module level (same pattern as parse_npc_response)
# ---------------------------------------------------------------------------


def _parse_timeline_xml(
    text: str,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Parse timeline, plot_threads, and causality XML from an LLM response.

    Parameters
    ----------
    text : str
        The raw LLM response text containing ``<timeline>``,
        ``<plot_threads>``, and ``<causality>`` tags.

    Returns
    -------
    tuple[list[dict], list[str], list[str]]
        A three-element tuple:

        - **timeline_entries** — list of dicts with keys ``turn`` (int)
          and ``text`` (str).
        - **plot_threads** — list of thread description strings.
        - **causality_items** — list of causality description strings.
    """
    timeline_entries: list[dict[str, Any]] = []
    plot_threads: list[str] = []
    causality_items: list[str] = []

    if not text or not isinstance(text, str):
        return timeline_entries, plot_threads, causality_items

    # ---- Timeline entries ----
    timeline_match = _TIMELINE_WRAPPER_RE.search(text)
    if timeline_match:
        timeline_content = timeline_match.group(1)
        for entry_match in _TIMELINE_ENTRY_RE.finditer(timeline_content):
            turn = int(entry_match.group(1))
            entry_text = entry_match.group(2).strip()
            timeline_entries.append({"turn": turn, "text": entry_text})

    # ---- Plot threads ----
    threads_match = _PLOT_THREADS_WRAPPER_RE.search(text)
    if threads_match:
        threads_content = threads_match.group(1)
        for thread_match in _PLOT_THREAD_RE.finditer(threads_content):
            thread_text = thread_match.group(2).strip()
            if thread_text:
                plot_threads.append(thread_text)

    # ---- Causality items (line-separated within <causality> tags) ----
    causality_match = _CAUSALITY_WRAPPER_RE.search(text)
    if causality_match:
        causality_content = causality_match.group(1).strip()
        if causality_content:
            for line in causality_content.split("\n"):
                line = line.strip()
                if line:
                    causality_items.append(line)

    return timeline_entries, plot_threads, causality_items


def _parse_entity_changes_xml(text: str) -> list[EntityOperation]:
    """Parse entity_changes XML from an LLM response.

    Parameters
    ----------
    text : str
        The raw LLM response text containing ``<entity_changes>`` tags.

    Returns
    -------
    list[EntityOperation]
        Extracted entity operations.  Returns an empty list if parsing
        fails or no changes are found.
    """
    operations: list[EntityOperation] = []

    if not text or not isinstance(text, str):
        return operations

    changes_match = _ENTITY_CHANGES_WRAPPER_RE.search(text)
    if not changes_match:
        return operations

    changes_content = changes_match.group(1)

    for entity_match in _ENTITY_CHANGE_RE.finditer(changes_content):
        action = entity_match.group(1).strip().lower()
        entity_type = entity_match.group(2).strip().lower()
        entity_id = entity_match.group(3).strip()
        fields_content = entity_match.group(4)

        # Validate action
        if action not in ("create", "update", "deactivate"):
            logger.warning("Skipping entity with unknown action '%s'", action)
            continue

        # Validate entity type
        if entity_type not in ("npc", "place", "item"):
            logger.warning("Skipping entity with unknown type '%s'", entity_type)
            continue

        if not entity_id:
            logger.warning("Skipping entity with empty id")
            continue

        # Parse field entries inside this entity
        fields: dict[str, Any] = {}
        for field_match in _ENTITY_FIELD_RE.finditer(fields_content):
            field_name = field_match.group(1).strip()
            field_value = field_match.group(2).strip()
            if field_name:
                fields[field_name] = field_value

        operations.append(
            EntityOperation(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                fields=fields,
            )
        )

    return operations


# ---------------------------------------------------------------------------
# RecordKeeperAgent
# ---------------------------------------------------------------------------

_DEFAULT_MINIMAL_CONTEXT: str = ""


class RecordKeeperAgent:
    """Agent that manages entity memory for the game.

    The Record Keeper performs two analysis passes around each DM turn:

    **Pre-DM** — analyses the player's input and current world state to
    produce a context summary (timeline, plot threads, relevant entities)
    that gets injected into the DM's prompt window.

    **Post-DM** — examines the DM's narrative output, extracts entity
    changes (NPCs, places, items), and persists them to
    ``EntityStorage``.

    Gracefully degrades when no LLM provider is available: falls back to
    simple keyword-based entity matching for pre-DM and returns empty
    analysis for post-DM.

    Parameters
    ----------
    llm_provider : LLMProvider or None
        The LLM provider for narrative analysis.  If ``None``, only
        keyword-based entity matching is available.
    entity_storage : EntityStorage
        Persistent storage for NPC, place, and item records.
    character_name : str
        The player character's name, used for entity relevance hints.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None,
        entity_storage: EntityStorage,
        character_name: str = "",
    ) -> None:
        self.llm_provider = llm_provider
        self.entity_storage = entity_storage
        self.character_name = character_name

    # ------------------------------------------------------------------
    # Internal helpers — LLM call (retry-once pattern from NPCAgent)
    # ------------------------------------------------------------------

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Call the LLM provider and return the response text.

        Implements a retry-once pattern identical to
        :meth:`NPCAgent._call_llm`.  Raises immediately if no LLM
        provider is configured — callers should check ``llm_provider``
        before calling this method.

        Parameters
        ----------
        messages : list[dict[str, str]]
            The message list in OpenAI chat format.

        Returns
        -------
        str
            The response content text.

        Raises
        ------
        RuntimeError
            If the LLM provider is ``None`` or the call fails after one
            retry, or returns empty content.
        """
        if self.llm_provider is None:
            raise RuntimeError("LLM provider is not available")

        try:
            response = self.llm_provider.call(messages)
        except Exception:
            logger.warning("RecordKeeper LLM call failed, retrying once")
            try:
                response = self.llm_provider.call(messages)
            except Exception as e:
                raise RuntimeError(
                    f"RecordKeeper LLM call failed after retry: {e}"
                ) from e

        content = response.get("content", "")
        if not content:
            raise RuntimeError("RecordKeeper LLM returned empty content")

        return content

    # ------------------------------------------------------------------
    # Internal helpers — context builders
    # ------------------------------------------------------------------

    def _build_plot_context(
        self,
        player_input: str,
        world_state: WorldState,
        current_narrative: str,
    ) -> list[dict[str, str]]:
        """Build the message list for the plot-analysis LLM call.

        Parameters
        ----------
        player_input : str
            The player's latest input.
        world_state : WorldState
            The current game world state.
        current_narrative : str
            The accumulated narrative text.

        Returns
        -------
        list[dict[str, str]]
            Messages in OpenAI chat format.
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": PLOT_SYSTEM_PROMPT},
        ]

        context_lines = [
            f"Character: {self.character_name or 'Unknown'}",
            f"Current location: {world_state.current_location}",
            f"Turn count: {world_state.turn_count}",
            "",
            "--- Recent Narrative ---",
            current_narrative or "(no narrative yet)",
            "",
            "--- Player Input ---",
            player_input,
            "",
            (
                "Analyse the narrative above and produce timeline entries, "
                "plot threads, and causality chains using the specified "
                "XML tags."
            ),
        ]
        messages.append({"role": "user", "content": "\n".join(context_lines)})

        return messages

    def _build_entity_context(
        self,
        dm_response: str,
        world_state: WorldState,
        turn_count: int,
    ) -> list[dict[str, str]]:
        """Build the message list for the entity-analysis LLM call.

        Parameters
        ----------
        dm_response : str
            The DM's narrative output to analyse.
        world_state : WorldState
            The current game world state.
        turn_count : int
            The current turn number.

        Returns
        -------
        list[dict[str, str]]
            Messages in OpenAI chat format.
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": ENTITY_SYSTEM_PROMPT},
        ]

        context_lines = [
            f"Turn: {turn_count}",
            f"Location: {world_state.current_location}",
            "",
            "--- DM Narrative to Analyse ---",
            dm_response,
            "",
            (
                "Extract entity changes from the narrative above and "
                "report them using the entity_changes XML format."
            ),
        ]
        messages.append({"role": "user", "content": "\n".join(context_lines)})

        return messages

    # ------------------------------------------------------------------
    # Internal helpers — keyword-based entity matching (fallback)
    # ------------------------------------------------------------------

    def _keyword_match_entities(self, text: str) -> list[dict[str, Any]]:
        """Find entities relevant to *text* using simple keyword matching.

        Tokenises the input text and matches each token as a substring
        against entity IDs and names.  Returns all matching entity dicts
        without duplicates.

        Parameters
        ----------
        text : str
            The input text to match against known entities.

        Returns
        -------
        list[dict]
            Matching entity records from storage.  Empty list if no
            matches or if *text* is empty.
        """
        if not text:
            return []

        # Tokenise: split on whitespace and strip common punctuation
        tokens = set(
            word.lower().strip(".,!?;:'\"()-[]{}")
            for word in text.split()
            if word.strip(".,!?;:'\"()-[]{}")
        )

        matched: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for entity in self.entity_storage.list_entities():
            entity_id = (entity.get("entity_id") or "").lower()
            entity_name = (entity.get("name") or "").lower()

            for token in tokens:
                if not token:
                    continue
                if token in entity_id or token in entity_name:
                    eid = entity.get("entity_id", "")
                    if eid not in seen_ids:
                        matched.append(entity)
                        seen_ids.add(eid)
                    break  # one match per entity is enough

        return matched

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_pre_dm(
        self,
        player_input: str,
        world_state: WorldState,
        current_narrative: str,
    ) -> RecordKeeperContext:
        """Pre-DM analysis: produce context for the DM's prompt.

        When an LLM provider is available, calls the LLM with the plot
        system prompt to produce a timeline, plot threads, and causality
        analysis.  Also fetches relevant entities via keyword matching.

        When no LLM is available, returns a minimal context with only
        keyword-matched entities (no timeline or plot analysis).

        Parameters
        ----------
        player_input : str
            The player's latest input.
        world_state : WorldState
            The current game world state.
        current_narrative : str
            The accumulated narrative text.

        Returns
        -------
        RecordKeeperContext
            Pre-DM analysis context for the DM.  Never raises — returns
            a minimal (possibly empty) context on failure.
        """
        # Always try to find relevant entities via keyword matching
        relevant_entities = self._keyword_match_entities(player_input)

        # No LLM → minimal context with just entity lookups
        if self.llm_provider is None:
            context_text = self._build_fallback_context_text(relevant_entities)
            return RecordKeeperContext(
                timeline_summary="",
                relevant_entities=relevant_entities,
                plot_threads=[],
                dm_suggestions=[],
                context_text=context_text,
            )

        # Call LLM with plot-analysis prompt
        try:
            messages = self._build_plot_context(
                player_input, world_state, current_narrative
            )
            raw_response = self._call_llm(messages)
        except Exception:
            logger.exception("RecordKeeper pre-DM LLM call failed")
            context_text = self._build_fallback_context_text(relevant_entities)
            return RecordKeeperContext(
                timeline_summary="",
                relevant_entities=relevant_entities,
                plot_threads=[],
                dm_suggestions=[],
                context_text=context_text,
            )

        # Parse the XML response
        try:
            timeline_entries, plot_threads, causality_items = _parse_timeline_xml(
                raw_response
            )

            # Build timeline summary text
            timeline_lines: list[str] = []
            for entry in timeline_entries:
                turn = entry.get("turn", "?")
                text = entry.get("text", "")
                timeline_lines.append(f"[Turn {turn}] {text}")
            timeline_summary = "\n".join(timeline_lines)

            # Build combined context text
            context_parts: list[str] = []
            if timeline_summary:
                context_parts.append("=== Timeline ===")
                context_parts.append(timeline_summary)
            if causality_items:
                context_parts.append("=== Causality & Suggestions ===")
                context_parts.extend(causality_items)
            if relevant_entities:
                context_parts.append("=== Relevant Entities ===")
                for entity in relevant_entities:
                    eid = entity.get("entity_id", "?")
                    ename = entity.get("name", eid)
                    etype = entity.get("entity_type", "?")
                    context_parts.append(f"  - [{etype}] {ename} ({eid})")

            context_text = "\n".join(context_parts)

            return RecordKeeperContext(
                timeline_summary=timeline_summary,
                relevant_entities=relevant_entities,
                plot_threads=plot_threads,
                dm_suggestions=causality_items,
                context_text=context_text,
            )

        except Exception:
            logger.exception("RecordKeeper pre-DM XML parsing failed")
            context_text = self._build_fallback_context_text(relevant_entities)
            return RecordKeeperContext(
                timeline_summary="",
                relevant_entities=relevant_entities,
                plot_threads=[],
                dm_suggestions=[],
                context_text=context_text,
            )

    def analyze_post_dm(
        self,
        dm_response: str,
        world_state: WorldState,
        turn_count: int,
    ) -> PostDMAnalysis:
        """Post-DM analysis: extract entity changes from the DM's narrative.

        When an LLM provider is available, calls the LLM with the entity
        system prompt to identify entity changes (creates, updates,
        deactivations).  Parses the XML response into
        :class:`EntityOperation` objects and :class:`EntityChangeLog`
        entries.

        When no LLM is available, returns an empty analysis.

        Parameters
        ----------
        dm_response : str
            The DM's narrative output to analyse.
        world_state : WorldState
            The current game world state.
        turn_count : int
            The current turn number (for changelog timestamps).

        Returns
        -------
        PostDMAnalysis
            Entity operations and changelog entries.  Never raises —
            returns an empty analysis on failure.
        """
        # No LLM → empty analysis
        if self.llm_provider is None:
            return PostDMAnalysis()

        # Call LLM with entity-analysis prompt
        try:
            messages = self._build_entity_context(dm_response, world_state, turn_count)
            raw_response = self._call_llm(messages)
        except Exception:
            logger.exception("RecordKeeper post-DM LLM call failed")
            return PostDMAnalysis()

        # Parse the entity_changes XML
        try:
            operations = _parse_entity_changes_xml(raw_response)

            # Build changelog entries from operations
            changelog_entries: list[EntityChangeLog] = []
            for op in operations:
                changelog_entries.append(
                    EntityChangeLog(
                        turn=turn_count,
                        entity_type=op.entity_type,
                        entity_id=op.entity_id,
                        change_type=op.action,
                        changed_fields=list(op.fields.keys()),
                        summary=self._build_change_summary(op),
                    )
                )

            # Extract new/resolved plot threads from the raw response
            # (the entity prompt doesn't explicitly output these, but the
            # raw response may contain plot-thread hints — we leave the
            # extraction of these to future refinement)

            return PostDMAnalysis(
                entity_operations=operations,
                changelog_entries=changelog_entries,
                raw_llm_response=raw_response,
            )

        except Exception:
            logger.exception("RecordKeeper post-DM XML parsing failed")
            return PostDMAnalysis(
                raw_llm_response=raw_response,
            )

    def fetch_entity(self, entity_type: str, entity_id: str) -> dict | None:
        """Fetch an entity record by type and ID.

        Delegates directly to :meth:`EntityStorage.get_entity`.

        Parameters
        ----------
        entity_type : str
            One of ``"npc"``, ``"place"``, ``"item"``.
        entity_id : str
            The unique identifier of the entity.

        Returns
        -------
        dict or None
            The entity data dictionary, or ``None`` if not found.
        """
        return self.entity_storage.get_entity(entity_type, entity_id)

    # ------------------------------------------------------------------
    # Internal helpers — context & summary builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fallback_context_text(
        relevant_entities: list[dict[str, Any]],
    ) -> str:
        """Build a minimal context text from entity lookups only.

        Used when the LLM is unavailable or when LLM analysis fails.

        Parameters
        ----------
        relevant_entities : list[dict]
            Entity records matched via keyword matching.

        Returns
        -------
        str
            Minimal context text, or empty string if no entities.
        """
        if not relevant_entities:
            return ""

        parts = ["=== Relevant Entities ==="]
        for entity in relevant_entities:
            eid = entity.get("entity_id", "?")
            ename = entity.get("name", eid)
            etype = entity.get("entity_type", "unknown")
            parts.append(f"  - [{etype}] {ename} ({eid})")
        return "\n".join(parts)

    @staticmethod
    def _build_change_summary(op: EntityOperation) -> str:
        """Build a human-readable change summary for an entity operation.

        Parameters
        ----------
        op : EntityOperation
            The entity operation to summarise.

        Returns
        -------
        str
            A concise summary of the change (e.g.
            ``"Created npc 'Gribbits'"``).
        """
        if op.action == "create":
            name = op.fields.get("name", op.entity_id)
            return f"Created {op.entity_type} '{name}'"
        if op.action == "update":
            fields_str = ", ".join(op.fields.keys()) if op.fields else "general"
            return f"Updated {op.entity_type} '{op.entity_id}' ({fields_str})"
        if op.action == "deactivate":
            return f"Deactivated {op.entity_type} '{op.entity_id}'"
        return f"{op.action} {op.entity_type} '{op.entity_id}'"
