# Aiker Target Structure

## Design goal

Aiker should become a ReAct agent for authorized internal pentesting. It must be able to think in steps, call tools, persist evidence, and keep a separate durable context for each engagement or environment.

The key organizational rule is simple:

- one engagement
- one project context
- one durable memory space
- one canonical database record set

## Project folder model

Each engagement should have its own folder, named in a human-friendly and sortable way:

```text
projects/
  [001] 10.24.12.1 corp-dc/
  [002] 10.24.18.20 finance-web/
  [003] acme.local external-gateway/
```

Recommended contents:

```text
aiker/
  pyproject.toml
  README.md
  src/
    aiker/
      __init__.py
      cli.py
      config.py
      app.py
      agent/
        orchestrator.py
        react_loop.py
        prompts.py
        policies.py
      llm/
        openrouter_client.py
        models.py
      tools/
        registry.py
        base.py
        shell_read.py
        shell_write.py
        summarize_context.py
        file_reader.py
        file_writer.py
        nmap.py
        http_probe.py
        nuclei.py
        smb_enum.py
        ldap_enum.py
        bloodhound.py
      memory/
        service.py
        retrieval.py
        summarizer.py
        context_builder.py
      db/
        engine.py
        models.py
        repositories.py
      projects/
        service.py
        naming.py
      reporting/
        service.py
        markdown.py
      telemetry/
        logging.py
        tracing.py
  projects/
    [001] 10.24.12.1 corp-dc/
      engagement.yaml
      notes/
      evidence/
      exports/
      cache/
  data/
    aiker.db
```

## System responsibilities

### `cli`

Owns operator input, command groups, project selection, interactive display, and session control.

### `agent`

Owns the ReAct loop:

1. load current project context
2. build working memory
3. ask the model for the next action
4. call a tool
5. store observation
6. update memory
7. continue until the agent reaches a stopping condition

### `tools`

Owns safe, typed capabilities. The model should never directly invent shell strings as the only execution path. It should call a known tool with validated parameters.

### `memory`

Owns short-term, long-term, and situational memory extraction and retrieval.

### `db`

Owns the canonical state of projects, sessions, tool calls, observations, facts, findings, notes, summaries, and evidence metadata.

### `projects`

Owns naming, numbering, engagement lifecycle, and folder creation for new contexts.

### `reporting`

Owns operator-facing summaries, Markdown exports, final findings, and evidence bundles.

## ReAct loop

```text
User goal
  -> Context builder
  -> LLM decides next action
  -> Tool call
  -> Observation captured
  -> Memory update
  -> Next action
  -> Final answer or handoff
```

Recommended stopping conditions:

- target objective satisfied
- no safe next step available
- operator approval required
- tool failure threshold reached
- token budget reached
- time budget reached

## Project isolation rules

Every project must have:

- its own engagement metadata
- its own session history
- its own memory retrieval scope
- its own findings and notes
- its own exported evidence

No session should mix observations from project `[001]` into project `[002]`.

## Recommended engagement file

Each project folder should contain `engagement.yaml` with at least:

```yaml
project_id: 1
display_name: "[001] 10.24.12.1 corp-dc"
scope:
  - "10.24.12.1"
client: "Internal"
engagement_type: "internal-pentest"
status: "active"
rules_of_engagement:
  active_exploitation_allowed: false
  credential_use_allowed: true
  lateral_movement_allowed: true
tags:
  - "intranet"
  - "ad"
```

## Main structural principle

The folder is the operator-facing context.

The database is the system-facing context.

The agent should use both, but the database should remain the canonical source of truth.
