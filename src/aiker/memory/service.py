from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session as DBSession

from aiker.db.models import utc_now
from aiker.db.repositories import (
    count_active_memory_items,
    create_memory_item,
    create_observation,
    create_tool_execution,
    expire_memory_items,
    list_active_memory_items,
    memory_item_exists,
)
from aiker.tools.executor import ToolResult

# ── Memory compression ────────────────────────────────────────────────────────

_COMPRESSION_THRESHOLD = 8   # Compress when short_term reaches this count
_COMPRESSION_KEEP = 2        # Keep the N most-recent items after compressing

_COMPRESSION_SYSTEM_PROMPT = """\
You are a technical memory compressor for an autonomous pentesting agent.

You receive a list of recent tool outputs, observations, and facts from a live engagement.

Your task: distill them into a compact bullet list that preserves every concrete technical fact.

Rules:
- KEEP all specific values: IP addresses, port numbers, service names, versions, URL paths, \
HTTP status codes, usernames, password hashes, CVE IDs, error messages, and response headers.
- DISCARD: timestamps, tool names, redundant status text ("ran successfully", "command executed").
- FORMAT: plain Markdown bullet list starting with `- `. No headers. No intro sentence.
- AIM for 4–8 bullets. Merge related facts into one bullet when possible.
- If all items were errors, produce one bullet describing the error pattern.
"""


def compress_short_term_memory(
    db: DBSession,
    client: "OpenRouterClient",  # type: ignore[name-defined]  # avoid circular import
    project_id: int,
    session_id: int | None,
) -> bool:
    """
    If short_term_memory has reached the compression threshold, summarise all
    active items into a single long_term MemoryItem via a cheap LLM call, then
    immediately expire the old short_term items (keeping the most-recent few).

    Returns True if compression was performed.
    """
    count = count_active_memory_items(db=db, project_id=project_id, memory_tier="short_term")
    if count < _COMPRESSION_THRESHOLD:
        return False

    items = list_active_memory_items(
        db=db, project_id=project_id, memory_tier="short_term", limit=count
    )
    if not items:
        return False

    # Build the payload — items come back newest-first; reverse for chronological order
    payload = "\n".join(
        f"- {item.content}" for item in reversed(items)
    )

    summary = client.text_completion(
        static_system=_COMPRESSION_SYSTEM_PROMPT,
        dynamic_context=payload,
        temperature=0.1,  # deterministic — we want facts, not prose
    )

    create_memory_item(
        db=db,
        project_id=project_id,
        session_id=session_id,
        memory_tier="long_term",
        title="Compressed short-term memory",
        content=summary.strip(),
        importance=3,
        source_refs=["auto:compression"],
        expires_at=None,
    )

    # Expire all but the _COMPRESSION_KEEP most-recent items
    to_expire = [item.id for item in items[_COMPRESSION_KEEP:] if item.id is not None]
    expire_memory_items(db=db, item_ids=to_expire)

    return True


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
