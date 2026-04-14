from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session as DBSession
from sqlmodel import select

from aiker.db.models import MemoryItem, Observation, Project, Session, ToolExecution


def get_project_by_id(db: DBSession, project_id: int) -> Optional[Project]:
    return db.get(Project, project_id)


def get_project_by_target(db: DBSession, target: str) -> Optional[Project]:
    stmt = select(Project).where(Project.target == target).order_by(Project.id.desc()).limit(1)
    return db.exec(stmt).first()


def get_session_by_id(db: DBSession, session_id: int) -> Optional[Session]:
    return db.get(Session, session_id)


def get_last_project_by_sequence(db: DBSession) -> Optional[Project]:
    stmt = select(Project).order_by(Project.sequence_number.desc()).limit(1)
    return db.exec(stmt).first()


def list_projects(db: DBSession) -> list[Project]:
    stmt = select(Project).order_by(Project.sequence_number.asc())
    return list(db.exec(stmt).all())


def create_session(db: DBSession, project_id: int, goal: str, operator_name: str) -> Session:
    session_obj = Session(project_id=project_id, goal=goal, operator_name=operator_name)
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return session_obj


def create_tool_execution(
    db: DBSession,
    project_id: int,
    session_id: int | None,
    tool_name: str,
    tool_input: dict,
    status: str,
    summary: str,
    raw_output: str,
    facts_extracted: list[str],
    confidence: float,
) -> ToolExecution:
    tool_execution = ToolExecution(
        project_id=project_id,
        session_id=session_id,
        tool_name=tool_name,
        input_json=json.dumps(tool_input, ensure_ascii=True),
        status=status,
        summary=summary,
        raw_output=raw_output,
        facts_json=json.dumps(facts_extracted, ensure_ascii=True),
        confidence=confidence,
    )
    db.add(tool_execution)
    db.commit()
    db.refresh(tool_execution)
    return tool_execution


def create_observation(
    db: DBSession,
    project_id: int,
    session_id: int | None,
    tool_execution_id: int | None,
    observation_type: str,
    content: str,
    confidence: float,
    source_ref: str,
) -> Observation:
    observation = Observation(
        project_id=project_id,
        session_id=session_id,
        tool_execution_id=tool_execution_id,
        observation_type=observation_type,
        content=content,
        confidence=confidence,
        source_ref=source_ref,
    )
    db.add(observation)
    db.commit()
    db.refresh(observation)
    return observation


def create_memory_item(
    db: DBSession,
    project_id: int,
    session_id: int | None,
    memory_tier: str,
    title: str,
    content: str,
    importance: int,
    source_refs: list[str],
    expires_at: datetime | None = None,
) -> MemoryItem:
    memory_item = MemoryItem(
        project_id=project_id,
        session_id=session_id,
        memory_tier=memory_tier,
        title=title,
        content=content,
        importance=importance,
        expires_at=expires_at,
        source_refs_json=json.dumps(source_refs, ensure_ascii=True),
    )
    db.add(memory_item)
    db.commit()
    db.refresh(memory_item)
    return memory_item


def list_recent_tool_executions(db: DBSession, project_id: int, limit: int = 8) -> list[ToolExecution]:
    stmt = (
        select(ToolExecution)
        .where(ToolExecution.project_id == project_id)
        .order_by(ToolExecution.created_at.desc())
        .limit(limit)
    )
    return list(db.exec(stmt).all())


def list_recent_observations(db: DBSession, project_id: int, limit: int = 12) -> list[Observation]:
    stmt = (
        select(Observation)
        .where(Observation.project_id == project_id)
        .order_by(Observation.created_at.desc())
        .limit(limit)
    )
    return list(db.exec(stmt).all())


def list_active_memory_items(
    db: DBSession, project_id: int, memory_tier: str | None = None, limit: int = 20
) -> list[MemoryItem]:
    now = datetime.now(timezone.utc)
    stmt = select(MemoryItem).where(MemoryItem.project_id == project_id)
    stmt = stmt.where((MemoryItem.expires_at.is_(None)) | (MemoryItem.expires_at > now))
    if memory_tier:
        stmt = stmt.where(MemoryItem.memory_tier == memory_tier)
    stmt = stmt.order_by(MemoryItem.created_at.desc()).limit(limit)
    return list(db.exec(stmt).all())


def memory_item_exists(db: DBSession, project_id: int, memory_tier: str, content: str) -> bool:
    stmt = (
        select(MemoryItem.id)
        .where(MemoryItem.project_id == project_id)
        .where(MemoryItem.memory_tier == memory_tier)
        .where(MemoryItem.content == content)
        .limit(1)
    )
    return db.exec(stmt).first() is not None


def list_memory_items(db: DBSession, project_id: int, memory_tier: str | None = None, limit: int = 50) -> list[MemoryItem]:
    stmt = select(MemoryItem).where(MemoryItem.project_id == project_id)
    if memory_tier:
        stmt = stmt.where(MemoryItem.memory_tier == memory_tier)
    stmt = stmt.order_by(MemoryItem.created_at.desc()).limit(limit)
    return list(db.exec(stmt).all())


def count_active_memory_items(db: DBSession, project_id: int, memory_tier: str) -> int:
    now = datetime.now(timezone.utc)
    stmt = (
        select(MemoryItem.id)
        .where(MemoryItem.project_id == project_id)
        .where(MemoryItem.memory_tier == memory_tier)
        .where((MemoryItem.expires_at.is_(None)) | (MemoryItem.expires_at > now))
    )
    return len(list(db.exec(stmt).all()))


def expire_memory_items(db: DBSession, item_ids: list[int]) -> None:
    """Immediately expire a list of MemoryItems by setting expires_at to now."""
    if not item_ids:
        return
    now = datetime.now(timezone.utc)
    for item_id in item_ids:
        item = db.get(MemoryItem, item_id)
        if item is not None:
            item.expires_at = now
            db.add(item)
    db.commit()
