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
from app.agents.tools import TOOL_REGISTRY, dispatch_tool

__all__ = [
    "DM_SYSTEM_PROMPT",
    "DungeonMaster",
    "NPC_SYSTEM_PROMPT",
    "NPCAgent",
    "compress_text",
    "parse_dm_response",
    "parse_npc_response",
    "dispatch_tool",
    "TOOL_REGISTRY",
    "SessionHistory",
]
