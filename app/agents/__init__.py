# agents package — Dungeon Master, NPC, and summarizer agents

from __future__ import annotations

from app.agents.consultation import (
    append_to_consultation_log,
    build_consultation_context,
    read_consultation_log,
)
from app.agents.context_builder import build_context
from app.agents.dm import DM_SYSTEM_PROMPT, DungeonMaster
from app.agents.history import Fidelity, SessionHistory
from app.agents.npc import (
    NPC_SYSTEM_PROMPT,
    NPCAgent,
    compress_text,
    parse_npc_response,
)
from app.agents.parser import parse_dm_response
from app.agents.record_keeper import (
    ENTITY_SYSTEM_PROMPT,
    PLOT_SYSTEM_PROMPT,
    EntityOperation,
    PostDMAnalysis,
    RecordKeeperAgent,
    RecordKeeperContext,
)
from app.agents.summarizer import (
    META_SUMMARIZER_SYSTEM_PROMPT,
    SUMMARIZER_SYSTEM_PROMPT,
    compress_summary,
    count_tokens,
    should_summarize,
    summarize_meta,
    summarize_turns,
)
from app.agents.tools import TOOL_REGISTRY, dispatch_tool

__all__ = [
    "append_to_consultation_log",
    "build_consultation_context",
    "build_context",
    "DM_SYSTEM_PROMPT",
    "DungeonMaster",
    "ENTITY_SYSTEM_PROMPT",
    "EntityOperation",
    "Fidelity",
    "META_SUMMARIZER_SYSTEM_PROMPT",
    "NPC_SYSTEM_PROMPT",
    "NPCAgent",
    "PLOT_SYSTEM_PROMPT",
    "PostDMAnalysis",
    "RecordKeeperAgent",
    "RecordKeeperContext",
    "SUMMARIZER_SYSTEM_PROMPT",
    "SessionHistory",
    "compress_summary",
    "compress_text",
    "count_tokens",
    "dispatch_tool",
    "parse_dm_response",
    "parse_npc_response",
    "read_consultation_log",
    "should_summarize",
    "summarize_meta",
    "summarize_turns",
    "TOOL_REGISTRY",
]
