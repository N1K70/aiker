# Aiker Current State

## What exists today

The current repository contains a single file, `aiker.py`, and it is still a prototype rather than a production agent.

The script is a Colab-exported notebook turned into a Python file. Its actual behavior is:

1. Install dependencies with notebook magic commands.
2. Ask for a single target IP or domain.
3. Send recent command history and the latest output to an LLM.
4. Receive the next suggested command as JSON.
5. Ask the operator for confirmation.
6. Execute the command locally.
7. Save the raw session history to a JSON log file at the end.

This means the current system is a guided command runner with LLM advice, not yet a real ReAct agent with a tool registry, durable memory, project isolation, or database-backed context.

## What the current script already gets right

- It tries to preserve operator approval before executing a suggested command.
- It uses structured JSON output from the model instead of free-form text.
- It keeps a lightweight command history and reuses it as context for the next step.
- It is already oriented toward an internal pentest workflow instead of a generic chat bot.

Those are useful foundations, but they are still only the first 10 percent of the architecture you asked for.

## Critical problems in the current file

### Environment and runtime problems

- `aiker.py:10-12` contains notebook-only commands (`pip install`, `!sudo apt install`) that make the file invalid as a normal Python CLI application.
- `aiker.py:19` imports `google.colab`, which prevents clean execution in Kali or a normal Linux VM.
- `aiker.py:53` hardcodes a Gemini model choice, but the entire design should move to OpenRouter with Qwen.

### Security and safety problems

- `aiker.py:25` hardcodes an API key directly into the source file. That is a critical secret-handling issue.
- `aiker.py:88` runs commands with `shell=True`, which is too permissive for a pentest agent and increases injection risk.
- There is no scope guard, no allowed-target policy, no operator policy layer, and no tool permission model.

### Reliability problems

- `aiker.py:62-64` references `generation_config` and `safety_settings`, but neither is defined in the file.
- `aiker.py:250` uses `paso.get(...)`, but `paso` does not exist there. It should use `paso_analisis`. This would raise a runtime error in the main loop.
- The code mixes prompt generation, command execution, user interaction, and persistence in one file, making it hard to test.

### Architecture gaps

- There is no project-level context folder such as `[001] 10.24.12.1 corp-dc`.
- There is no database. Only a final JSON export exists.
- There is no short-term, long-term, or situational memory model.
- There is no formal ReAct loop with tool calls as first-class actions.
- There is no tool abstraction layer. The model only suggests shell commands.
- There is no retrieval layer, no summarization pipeline, and no evidence indexing.
- The codebase is in Spanish, while you asked for English-first implementation for consistency and operator clarity.

## Current architecture in one sentence

Current Aiker is a single-session LLM-assisted shell runner.

## Target architecture in one sentence

Target Aiker should be a database-backed, project-aware, CLI-first ReAct pentest agent with explicit tools, layered memory, safety guards, and durable evidence management for authorized internal assessments.

## Main conclusion

The existing file should be treated as a concept prototype, not as the base of the final production design.

The correct next step is not to keep extending this single file. The correct next step is to split responsibilities into a real application architecture:

- CLI layer
- agent orchestration layer
- tool execution layer
- context and memory layer
- database layer
- evidence and export layer
- policy and safety layer
