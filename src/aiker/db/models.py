from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sequence_number: int = Field(index=True, unique=True)
    display_name: str = Field(index=True, unique=True)
    target: str = Field(index=True)
    label: str = Field(default="")
    primary_scope: str = Field(default="")
    engagement_type: str = Field(default="internal-pentest")
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Session(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    operator_name: str = Field(default="unknown")
    goal: str = Field(default="")
    status: str = Field(default="active")
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: Optional[datetime] = Field(default=None)


class ToolExecution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    session_id: Optional[int] = Field(default=None, foreign_key="session.id", index=True)
    tool_name: str = Field(index=True)
    input_json: str = Field(default="{}")
    status: str = Field(default="success")
    summary: str = Field(default="")
    raw_output: str = Field(default="")
    facts_json: str = Field(default="[]")
    confidence: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=utc_now)


class Observation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    session_id: Optional[int] = Field(default=None, foreign_key="session.id", index=True)
    tool_execution_id: Optional[int] = Field(default=None, index=True)
    observation_type: str = Field(default="tool_summary", index=True)
    content: str
    confidence: float = Field(default=0.0)
    source_ref: str = Field(default="")
    created_at: datetime = Field(default_factory=utc_now)


class MemoryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    session_id: Optional[int] = Field(default=None, foreign_key="session.id", index=True)
    memory_tier: str = Field(index=True)
    title: str = Field(default="")
    content: str
    importance: int = Field(default=1)
    expires_at: Optional[datetime] = Field(default=None, index=True)
    source_refs_json: str = Field(default="[]")
    created_at: datetime = Field(default_factory=utc_now)
