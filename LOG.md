# LOG.md

## Project Status

`Aiker` is transitioning from a single-file prototype (`aiker.py`) to a structured Python package.

Runtime target: Linux-only, with Kali Linux as the primary operating environment.

## In Progress

- [ ] Improve output readability with richer progress/timeline view in CLI and Ink.

## Backlog

- [ ] Add evidence artifact persistence and hashing.
- [ ] Add findings table and draft generation workflow.
- [ ] Add scope allowlist guardrails for high-impact tool calls.
- [ ] Add integration tests for CLI flows.
- [ ] Add DB migrations with Alembic instead of table auto-creation only.
- [ ] Add robust project path rendering in CLI without visual wrapping issues.

## Done

- [x] Added architecture documentation in `docs/`:
  - `01-current-state.md`
  - `02-structure.md`
  - `03-style-and-llm-policy.md`
  - `04-database-and-memory.md`
  - `05-tools-cli-and-roadmap.md`
- [x] Added agent operating rules in `AGENT.md`.
- [x] Added active engineering log in `LOG.md`.
- [x] Bootstrapped package structure with `pyproject.toml`, `src/aiker`, and modular domains (`agent`, `db`, `projects`, `sessions`, `tools`, `llm`).
- [x] Implemented SQLite-backed models for `Project` and `Session`.
- [x] Implemented `project create` and `project list` commands.
- [x] Implemented per-project folder creation with `engagement.yaml`.
- [x] Implemented `session start` command with DB persistence.
- [x] Implemented OpenRouter client wrapper with low temperature defaults and Qwen model default.
- [x] Implemented first ReAct planning command: `run --project-id --objective`.
- [x] Moved legacy notebook prototype to `legacy/aiker_colab_prototype.py` to avoid namespace collision.
- [x] Added `.gitignore` and cleaned generated runtime artifacts (`data/`, `projects/`, `*.egg-info`).
- [x] Added executable tool adapters and wired real tool calls into execution flow:
  - `read_file`
  - `write_file`
  - `summarize_context`
  - `nmap_scan`
  - `http_probe`
  - `nuclei_scan`
- [x] Added persistence models for tool and memory pipeline:
  - `ToolExecution`
  - `Observation`
  - `MemoryItem`
- [x] Added memory context builder from recent observations, tool summaries, and memory tiers.
- [x] Added automatic tool outcome recording into observations and short/situational memory.
- [x] Extended `run` with iterative execution (`--steps`) and session binding (`--session-id`).
- [x] Added manual tool execution command:
  - `python -m aiker tool call --tool ...`
  - supports `--input-json` and `--input-json-file`
- [x] Added expanded Kali tool catalog with 25+ tool calls and risk classification.
- [x] Added `python -m aiker workflow --target ...` for one-argument automated reconnaissance flow.
- [x] Added `python -m aiker tool list` to inspect all registered tools.
- [x] Added Ink UI scaffold (`ink-cli`) with metasploit-style visual shell and live workflow streaming.
- [x] Added workflow profiles for automation sequencing:
  - `--profile auto`
  - `--profile web`
  - `--profile network`
  - `--profile ad`
- [x] Added aggressive execution mode as the default for workflow and planner prompts.
- [x] Added Burp Suite detection tool and integrated it into the web workflow path.
- [x] Restricted runtime target to Linux-only and removed Windows-specific Burp detection paths.
- [x] Added `doctor` command for Kali/Linux environment validation:
  - distro/runtime detection
  - required and optional tool availability
  - baseline wordlist checks
  - OpenRouter/API/workspace visibility
- [x] Added automatic environment preflight summary at workflow start.
- [x] Reworked planner prompts for stronger ReAct behavior:
  - dedicated `agent/prompts.py` module
  - direct JSON-only prompt contract
  - evidence-first and non-repetitive tool selection guidance
  - escalation-aware planning without fabricated access claims
  - lower-entropy OpenRouter defaults for more stable decisions
- [x] Made planner prompts profile-aware:
  - `run --profile auto|web|network|ad`
  - profile-specific prompt guidance for web, network, and AD assessments
  - auto-to-web/network normalization based on target shape
- [x] Added high-risk execution policy:
  - planner only sees high-risk tools when `--allow-high-risk` is set
  - `tool call` requires `--ack-high-risk` for high-risk tools
  - aggressive mode remains default, but intrusive execution now requires explicit authorization
- [x] Added long-term memory promotion from high-confidence extracted facts.
- [x] Added `memory show` command with `--tier` and `--limit` filters.
- [x] Added safer folder naming for URL targets (Windows-safe display names).
- [x] Added scope normalization for URL targets (host-based project scope).
- [x] Added retry protection for project sequence allocation under concurrent runs.
- [x] Improved output rendering with preview clipping and line truncation.
- [x] Verified flows:
  - `python -m aiker --help`
  - `python -m aiker project create ...`
  - `python -m aiker project list`
  - `python -m aiker session start ...`
  - `python -m aiker run ...` (expected API-key guard error when key is missing)
  - `python -m aiker tool call --project-id ... --tool summarize_context`
  - `python -m aiker tool call --project-id ... --tool write_file --input-json-file ...`
  - `python -m aiker tool call --project-id ... --tool read_file --input-json-file ...`
  - `python -m aiker tool list`
  - `python -m aiker tool call --project-id ... --tool burp_suite_detect`
  - `python -m aiker workflow --target ... --max-tools ... --show-raw`
  - `python -m aiker workflow --target ... --profile web --mode aggressive`
  - `python -m aiker workflow --target ... --profile web|network|ad`
  - `python -m aiker memory show --project-id ...`
  - `python -m aiker memory show --project-id ... --tier long_term`
  - `python -m aiker --help`
  - module-level smoke test for `aiker.kali.build_environment_report(...)`

## Notes

- Keep this file updated at the end of every coding task.
- If implementation reveals additional work, append it to `Backlog` immediately.
