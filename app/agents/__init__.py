# agents package — Dungeon Master, NPC, and summarizer agents

from app.agents.dm import DM_SYSTEM_PROMPT, DungeonMaster
from app.agents.history import SessionHistory
from app.agents.npc import (
    NPC_SYSTEM_PROMPT,
    NPCAgent,
    compress_text,
    parse_npc_response,
)
from app.agents.parser import parse_dm_response
from app.agents.summarizer import (
    SUMMARIZER_SYSTEM_PROMPT,
    compress_summary,
    count_tokens,
    should_summarize,
    summarize_turns,
)
from app.agents.tools import TOOL_REGISTRY, dispatch_tool

__all__ = [
    "DM_SYSTEM_PROMPT",
    "DungeonMaster",
    "NPC_SYSTEM_PROMPT",
    "NPCAgent",
    "SUMMARIZER_SYSTEM_PROMPT",
    "SessionHistory",
    "compress_summary",
    "compress_text",
    "count_tokens",
    "dispatch_tool",
    "parse_dm_response",
    "parse_npc_response",
    "should_summarize",
    "summarize_turns",
    "TOOL_REGISTRY",
]
