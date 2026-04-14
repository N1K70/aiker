# Aiker Database and Memory Design

## Database-first rule

The database should be the canonical source of truth for the platform.

That means the database should store:

- projects
- sessions
- objectives
- tool executions
- observations
- extracted facts
- findings
- summaries
- notes
- memory items
- evidence metadata
- report exports

Files inside project folders are still useful, but they should be treated as evidence artifacts and exports, not as the only source of truth.

## Recommended database choice

Use SQLite first, with an optional PostgreSQL backend later.

Why SQLite first:

- excellent for Kali and portable VM usage
- zero external service requirement
- simple backups
- easy local deployment
- enough for a single-operator or small-team internal workflow

Why keep PostgreSQL as an upgrade path:

- better multi-user concurrency
- stronger centralized deployment story
- better scaling for large evidence sets

## Core schema

### `projects`

Stores one row per engagement.

Suggested fields:

- `id`
- `sequence_number`
- `display_name`
- `primary_scope`
- `engagement_type`
- `status`
- `client_name`
- `rules_of_engagement_json`
- `created_at`
- `updated_at`

### `project_assets`

Stores discovered or in-scope hosts, URLs, domains, shares, and identities.

Suggested fields:

- `id`
- `project_id`
- `asset_type`
- `value`
- `source`
- `confidence`
- `first_seen_at`
- `last_seen_at`

### `sessions`

Stores each CLI session or agent run.

Suggested fields:

- `id`
- `project_id`
- `operator_name`
- `goal`
- `started_at`
- `ended_at`
- `status`

### `tool_executions`

Stores every tool invocation.

Suggested fields:

- `id`
- `session_id`
- `project_id`
- `tool_name`
- `input_json`
- `status`
- `summary`
- `raw_output`
- `started_at`
- `ended_at`
- `host_context`
- `artifact_count`

### `observations`

Stores normalized statements extracted from tool results.

Suggested fields:

- `id`
- `project_id`
- `session_id`
- `tool_execution_id`
- `observation_type`
- `content`
- `confidence`
- `source_ref`
- `created_at`

### `memory_items`

Stores all memory units, regardless of tier.

Suggested fields:

- `id`
- `project_id`
- `session_id`
- `memory_tier`
- `title`
- `content`
- `importance`
- `expires_at`
- `source_refs_json`
- `created_at`

### `findings`

Stores validated findings and hypotheses.

Suggested fields:

- `id`
- `project_id`
- `title`
- `severity`
- `status`
- `evidence_summary`
- `affected_assets_json`
- `confidence`
- `created_at`
- `updated_at`

### `artifacts`

Stores evidence metadata and optional content blobs.

Suggested fields:

- `id`
- `project_id`
- `tool_execution_id`
- `artifact_type`
- `sha256`
- `mime_type`
- `content_text`
- `content_blob`
- `external_path`
- `created_at`

## Memory tiers

### Short-term memory

Purpose:

- keep the current working window small and relevant
- hold the latest goals, last observations, active host, and pending tasks

Examples:

- last 8 tool summaries
- current enumeration objective
- current subnet or host under analysis
- unresolved errors from the last tool call

TTL:

- current session only
- optionally carried into the next session through summarization

### Long-term memory

Purpose:

- preserve durable facts that remain useful across sessions

Examples:

- "10.24.12.1 exposes SMB and LDAP"
- "corp-dc is likely the domain controller"
- "finance-web has IIS on 443"
- "operator confirmed credential reuse is allowed in this engagement"

TTL:

- no expiration by default
- manually demotable or superseded

### Situational memory

Purpose:

- capture temporary state that matters right now but should not become permanent truth

Examples:

- "VPN tunnel is currently unstable"
- "host 10.24.12.1 did not answer SMB during the last 5 minutes"
- "current focus is lateral movement preparation"
- "operator declined aggressive scans for this session"

TTL:

- time-bound
- session-bound
- auto-expiring

## Retrieval strategy

Before each model call, the context builder should retrieve:

1. project facts from long-term memory
2. current session items from short-term memory
3. active situational items
4. the most relevant findings and latest tool observations

The model should not receive the entire project history every time.

It should receive:

- a compact working set
- evidence references
- summarized state
- the exact tools it can use now

## Summarization pipeline

After a tool call:

1. store raw output
2. extract structured observations
3. write short-term memory
4. promote stable facts to long-term memory
5. write situational entries if the state is temporary

This is the key to keeping context strong without drowning the model in tokens.

## Important evidence rule

The agent should not promote a fact to long-term memory unless it has at least one supporting observation and a source reference.

No memory item should exist without traceability.
