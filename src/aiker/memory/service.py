from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session as DBSession

from aiker.db.models import utc_now
from aiker.db.repositories import create_memory_item, create_observation, create_tool_execution, memory_item_exists
from aiker.tools.executor import ToolResult


def record_tool_outcome(
    db: DBSession,
    project_id: int,
    session_id: int | None,
    tool_name: str,
    tool_input: dict,
    result: ToolResult,
) -> int:
    execution = create_tool_execution(
        db=db,
        project_id=project_id,
        session_id=session_id,
        tool_name=tool_name,
        tool_input=tool_input,
        status=result.status,
        summary=result.summary,
        raw_output=result.raw_output,
        facts_extracted=result.facts_extracted,
        confidence=result.confidence,
    )

    source_ref = f"tool_execution:{execution.id}"
    create_observation(
        db=db,
        project_id=project_id,
        session_id=session_id,
        tool_execution_id=execution.id,
        observation_type="tool_summary",
        content=result.summary,
        confidence=result.confidence,
        source_ref=source_ref,
    )

    for fact in result.facts_extracted:
        create_observation(
            db=db,
            project_id=project_id,
            session_id=session_id,
            tool_execution_id=execution.id,
            observation_type="fact",
            content=fact,
            confidence=result.confidence,
            source_ref=source_ref,
        )

    create_memory_item(
        db=db,
        project_id=project_id,
        session_id=session_id,
        memory_tier="short_term",
        title=f"{tool_name} summary",
        content=result.summary,
        importance=2 if result.status == "success" else 3,
        source_refs=[source_ref],
        expires_at=utc_now() + timedelta(hours=8),
    )

    if result.status != "success":
        create_memory_item(
            db=db,
            project_id=project_id,
            session_id=session_id,
            memory_tier="situational",
            title=f"{tool_name} error",
            content=f"Tool error: {result.summary}",
            importance=3,
            source_refs=[source_ref],
            expires_at=utc_now() + timedelta(hours=4),
        )

    _promote_long_term_facts(
        db=db,
        project_id=project_id,
        session_id=session_id,
        source_ref=source_ref,
        result=result,
    )

    return execution.id


def _promote_long_term_facts(
    db: DBSession,
    project_id: int,
    session_id: int | None,
    source_ref: str,
    result: ToolResult,
) -> None:
    if result.status != "success":
        return
    if result.confidence < 0.7:
        return
    for fact in result.facts_extracted:
        normalized = fact.strip()
        if not normalized:
            continue
        if normalized.startswith("file_path="):
            continue
        if memory_item_exists(db=db, project_id=project_id, memory_tier="long_term", content=normalized):
            continue
        create_memory_item(
            db=db,
            project_id=project_id,
            session_id=session_id,
            memory_tier="long_term",
            title="Promoted fact",
            content=normalized,
            importance=3,
            source_refs=[source_ref],
            expires_at=None,
        )
