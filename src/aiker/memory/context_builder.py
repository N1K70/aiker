from __future__ import annotations

import json

from sqlmodel import Session as DBSession

from aiker.db.repositories import list_active_memory_items, list_recent_observations, list_recent_tool_executions


def _memory_contents(db: DBSession, project_id: int, memory_tier: str, limit: int = 8) -> list[str]:
    entries = list_active_memory_items(db=db, project_id=project_id, memory_tier=memory_tier, limit=limit)
    return [entry.content for entry in entries]


def build_model_context(db: DBSession, project_id: int, objective: str) -> dict:
    observations = list_recent_observations(db=db, project_id=project_id, limit=10)
    tool_executions = list_recent_tool_executions(db=db, project_id=project_id, limit=6)

    return {
        "objective": objective,
        "recent_observations": [item.content for item in observations],
        "recent_tool_summaries": [item.summary for item in tool_executions],
        "short_term_memory": _memory_contents(db=db, project_id=project_id, memory_tier="short_term", limit=8),
        "long_term_memory": _memory_contents(db=db, project_id=project_id, memory_tier="long_term", limit=8),
        "situational_memory": _memory_contents(db=db, project_id=project_id, memory_tier="situational", limit=8),
    }


def render_context_for_prompt(context_payload: dict) -> str:
    return json.dumps(context_payload, ensure_ascii=True, indent=2)
