# Aiker Tools, CLI, and Roadmap

## CLI direction

The application should be CLI-first and pleasant to operate from Kali Linux.

Recommended UX stack:

- Typer for command structure
- Rich for tables, panels, progress, and syntax formatting
- Textual later if a full TUI becomes necessary

Recommended command surface:

```text
aiker project create
aiker project list
aiker session start
aiker run
aiker tool call
aiker memory show
aiker findings list
aiker export report
```

Example usage:

```bash
aiker project create --name "[001] 10.24.12.1 corp-dc" --scope 10.24.12.1
aiker session start --project 1 --goal "Enumerate internal AD attack surface"
aiker run --project 1
aiker findings list --project 1
```

## Minimum toolset

The agent should expose tools through a registry with typed inputs and outputs.

### Core platform tools

- `read_file`
- `write_file`
- `append_note`
- `search_project_data`
- `summarize_context`
- `store_memory`
- `list_artifacts`
- `show_recent_observations`

### Safe shell tools

- `run_command_read_only`
- `run_command_scoped`
- `run_command_with_approval`

These tools should validate arguments before execution and enforce project scope.

### Internal pentest tools

- `nmap_scan`
- `rustscan_scan`
- `dns_lookup`
- `http_probe`
- `ffuf_scan`
- `nuclei_scan`
- `whatweb_fingerprint`
- `nikto_scan`
- `smb_enumerate`
- `ldap_enumerate`
- `kerberos_enumerate`
- `bloodhound_collect`
- `impacket_wrapper`
- `netexec_wrapper`

### Analysis tools

- `extract_facts_from_output`
- `diff_observations`
- `summarize_host`
- `build_attack_surface_summary`
- `generate_finding_draft`

## Kali Linux support

The runtime should assume Kali as a first-class environment.

Recommended external tools to support:

- `nmap`
- `rustscan`
- `ffuf`
- `gobuster`
- `whatweb`
- `nikto`
- `nuclei`
- `netexec`
- `crackmapexec` if still required in your environment
- `impacket-*`
- `enum4linux-ng`
- `smbclient`
- `ldapsearch`
- `bloodhound-python`
- `responder`
- `tcpdump`
- `curl`
- `dig`

The application should detect missing tools and report them cleanly instead of failing with raw shell noise.

## Safety model for internal pentest use

This project is explicitly for authorized intra-company pentesting, so the safety model should be operational rather than generic.

Required controls:

- explicit scope definition per project
- operator approval gates for high-impact actions
- command logging
- evidence logging
- tool risk classification
- session replayability
- target allowlist enforcement

Example risk classes:

- `low`: passive discovery, reading files, summarization
- `medium`: authenticated enumeration, service probing
- `high`: exploitation, relay attempts, password spraying, disruptive actions

## Suggested modern Python stack

- `openai` SDK pointed at OpenRouter
- `typer`
- `rich`
- `pydantic`
- `sqlalchemy` or `sqlmodel`
- `alembic`
- `httpx`
- `orjson`
- `tenacity`
- `structlog`
- `pytest`
- `ruff`
- `mypy`

## Implementation roadmap

### Phase 1

Create the real project skeleton:

- package layout
- config loading
- CLI bootstrap
- database engine
- project creation flow

### Phase 2

Implement the first production ReAct loop:

- OpenRouter client
- Qwen 3.6 Plus model configuration
- tool registry
- structured tool results
- iteration limits

### Phase 3

Implement memory:

- short-term memory
- long-term memory
- situational memory
- summarization and promotion rules

### Phase 4

Add internal pentest tools and evidence tracking:

- network enumeration
- web enumeration
- AD-focused tools
- artifact storage
- finding drafts

### Phase 5

Add operator quality features:

- report export
- project dashboards in CLI
- replay mode
- diff mode between sessions
- richer TUI if needed

## Final recommendation

Do not continue growing the current single-file Colab prototype.

Rebuild Aiker as a Python package with:

- a CLI-first workflow
- OpenRouter plus Qwen 3.6 Plus
- a strict tool layer
- a database-first memory system
- project folders for engagement context
- Kali-friendly operational tooling
