# Aiker

Aiker is a Linux-only, CLI-first ReAct agent framework for authorized internal pentesting.

Target runtime:

- Kali Linux
- other Linux distributions used for internal assessment labs

Windows is not a supported runtime target.

Current implementation status:

- Project and session lifecycle in SQLite.
- Project context folders per engagement.
- OpenRouter client wrapper.
- ReAct planning plus tool execution loop with low-temperature defaults.
- Memory and observations persisted from each tool execution.

## Quick Start

```bash
pip install -e .
python -m aiker doctor
python -m aiker --help
```

## Environment Variables

- `OPENROUTER_API_KEY`: required for LLM operations.
- `AIKER_HOME`: optional custom workspace root.
- `AIKER_MODEL`: optional model override (default `qwen/qwen3.6-plus`).

## Core Commands

```bash
python -m aiker doctor
python -m aiker project create --target 10.10.10.5 --label lab-ad --scope 10.10.10.5
python -m aiker project list
python -m aiker session start --project-id 1 --goal "Initial recon" --operator analyst1
python -m aiker run --project-id 1 --objective "Enumerate open services safely" --profile network --steps 2
python -m aiker run --project-id 1 --objective "Validate credential attack path" --profile ad --steps 2 --allow-high-risk
```

## Kali Environment Check

Run the environment doctor before starting aggressive workflows:

```bash
python -m aiker doctor
```

The doctor command reports:

- Linux/Kali runtime status
- required vs optional tooling availability
- baseline wordlists
- OpenRouter API key presence
- current `AIKER_HOME`, `data/`, and `projects/` paths

## One-Command Workflow

The simplest workflow is now:

```bash
python -m aiker workflow --target 10.10.10.5
python -m aiker workflow --target https://intranet.local
python -m aiker workflow --target https://intranet.local --profile web --mode aggressive
```

This command:

- runs a Kali/tooling preflight summary
- creates or reuses a project
- starts a session
- runs an automated baseline read/recon sequence
- prints each step and output preview live

Profiles are supported:

```bash
python -m aiker workflow --target https://intranet.local --profile web
python -m aiker workflow --target 10.10.10.5 --profile network
python -m aiker workflow --target 10.10.10.10 --profile ad
python -m aiker run --project-id 1 --objective "Enumerate domain exposure" --profile ad --steps 3
```

Execution mode defaults to `aggressive`.

High-risk tools are not auto-authorized. The planner can only select them when `--allow-high-risk` is provided.

## Tool Catalog (25+ Kali Tool Calls)

```bash
python -m aiker tool list
```

You can call a specific tool directly:

```bash
python -m aiker tool call --project-id 1 --tool nmap_scan --input-json-file tool_input.json
```

## Manual Tool Calls

Use `--input-json-file` to avoid shell quoting issues.

```bash
python -m aiker tool call --project-id 1 --tool summarize_context
python -m aiker tool call --project-id 1 --tool burp_suite_detect
python -m aiker tool call --project-id 1 --tool write_file --input-json-file tool_input.json --session-id 1
python -m aiker tool call --project-id 1 --tool read_file --input-json-file tool_input_read.json --session-id 1
python -m aiker tool call --project-id 1 --tool hydra_attack --input-json-file hydra_input.json --ack-high-risk
```

## Memory Inspection

```bash
python -m aiker memory show --project-id 1
python -m aiker memory show --project-id 1 --tier long_term
python -m aiker memory show --project-id 1 --tier short_term --limit 20
```

## Ink UI (Metasploit-style)

An Ink-based console UI is available in `ink-cli`:

```bash
cd ink-cli
npm install
npm start
```
