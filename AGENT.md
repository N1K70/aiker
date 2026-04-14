# AGENT.md

## Mission

Build and maintain `Aiker` as a production-grade ReAct agent for authorized internal pentesting.

This repository is not a notebook playground. It is an engineering codebase.

## Non-Negotiable Rules

1. Always read `LOG.md` before starting new coding work.
2. If a task is in `Backlog`, move it to `In Progress` before coding.
3. When work is finished, move it to `Done` with a short note.
4. If new work is discovered while coding, add it to `Backlog`.
5. Keep all code, comments, prompts, docs, and commit notes in English.
6. Prefer incremental, testable changes over giant rewrites.
7. Keep the architecture aligned with:
   - ReAct with Tools
   - per-project context folders
   - database-first state
   - short-term, long-term, and situational memory
   - low-temperature LLM behavior

## Work Cycle

1. Read `LOG.md`.
2. Pick the top `In Progress` task or promote one from `Backlog`.
3. Implement.
4. Run quick verification checks.
5. Update `LOG.md`:
   - mark completed tasks
   - add follow-up tasks
   - record blockers
6. Repeat.

## Definition of Done

A task is done when:

- behavior works locally
- key failure modes are handled
- code is readable and typed
- log is updated
- next tasks are clear

## Current Priority

1. Deliver a working CLI skeleton.
2. Deliver database-backed projects and sessions.
3. Deliver the first OpenRouter + Qwen ReAct loop.
4. Expand tools and memory system incrementally.
