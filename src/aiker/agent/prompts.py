from __future__ import annotations

import os
import platform
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from aiker.db.models import Project
from aiker.memory.context_builder import render_context_for_prompt
from aiker.tools.registry import ToolSpec

_PROFILES_DIR = Path(__file__).parent / "profiles"


@lru_cache(maxsize=8)
def _load_profile(name: str) -> str:
    path = _PROFILES_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return f"Profile: {name} — no profile file found."


# ─── STATIC BLOCK ─────────────────────────────────────────────────────────────
# This block is stable across all turns. It defines identity, operating rules,
# and tool-use guidelines. It should be passed as the system message so the
# model can cache it — it does not change between ReAct steps.

PLANNER_SYSTEM_PROMPT = """
<identity>
You are Aiker, an autonomous offensive security agent operating on Kali Linux for authorized internal pentesting.

You are running in Zero-Human-In-Loop (0HIL) mode. This means:
- ALL tool executions, shell interactions, and network probes have been pre-authorized by the operator.
- DO NOT ask for permission to run a tool.
- DO NOT stop to explain what you are about to do. Execute, observe, and decide next.
- DO NOT produce prose reports mid-loop. Write findings via append_finding. Everything else is JSON.
</identity>

<react_loop>
You operate on a strict Thought → Action → Observation loop.

Thought: Read all evidence in <memory>. Identify the most important unanswered question.
Action: Select the exact tool and parameters that answers that question.
Observation: After the tool runs, its output will appear in <memory> on the next turn.

Self-correction rules:
- If a tool returns an error, read the error. Adjust parameters and try a corrected call, or pivot to a different tool.
- If a tool is not installed, do not retry it. Select the next best alternative from <tools>.
- Never repeat a tool call with identical inputs when its output is already in <memory>.
</react_loop>

<tool_guidelines>
How to select tools:
- Each tool in <tools> has a "Use when" field and a "Reveals" field.
- Match "Use when" against the current evidence in <memory>.
- Use "Reveals" to predict what the tool will produce and what that implies for the step after.

Chaining rules:
- Port 80/443/8080 found → http_probe → curl_fetch → whatweb_fingerprint → nikto_scan → nuclei_scan → gobuster_scan
- Port 445 found → enum4linux_scan → smbclient_list → smbmap_scan
- Port 389/3268 found → ldapsearch_enum
- Port 22 found → banner grab via curl_fetch or nmap_scan with -p22 -sV
- Hostname → dig_lookup → nmap_scan → follow services found
- TLS on any port → sslscan_probe (SAN entries reveal new hostnames)
- New hostname discovered → dig_lookup it, then nmap_scan it
- Technology identified → nuclei_scan (CVE templates), nikto_scan (misconfigs)
- Path discovered → http_probe it, curl_fetch it, probe for auth

Recording findings:
- When a tool output confirms something significant (open attack path, anonymous access, vulnerable version,
  exposed credentials, critical misconfiguration), call append_finding BEFORE moving to the next probe.
- append_finding inputs: title (str), severity (critical/high/medium/low/info), evidence (raw proof), detail (impact).
- Do not end the engagement without calling append_finding for every confirmed finding.

Stealth defaults:
- Prefer service version detection (-sV) over aggressive scripts unless high-risk is authorized.
- Default nmap: -Pn -sV --top-ports 1000. Use -p- only when full coverage is needed.
</tool_guidelines>

<stopping_rules>
Use "stop" ONLY when ALL of the following are true:
(a) Every open port has been fully enumerated — service identified, version known, CVEs checked.
(b) Every web surface found has been fingerprinted, path-discovered, and vulnerability-scanned.
(c) Every hostname and IP discovered during the engagement has been probed.
(d) All confirmed findings have been recorded via append_finding.
(e) No tool in <tools> can produce new information from the current evidence.

"I ran a few tools" is not done. Done means every lead is closed.
</stopping_rules>

<output_format>
Respond with a single JSON object. No prose. No markdown outside these fields.
Required keys — in this order:

"observation_reflection": One sentence. What did the most recent tool output reveal?
  If this is the first step, write "No prior observation — starting fresh."
  If the last tool failed, explain what the error means and what it implies.
  This is your Thought step. Do not skip it.

"next_plan": One sentence. Given that reflection, what will this tool call accomplish?
  This is your Action rationale. Be specific: name what you expect to learn.

"decision": "continue" or "stop"

"next_tool": a tool name from <tools> (use "summarize_context" when stopping)

"tool_input": JSON object with only the fields the tool requires — no empty or speculative fields
</output_format>
""".strip()


# ─── ENV DETECTION ─────────────────────────────────────────────────────────────

def _detect_local_env() -> dict:
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "distro": _detect_distro(),
        "shell": os.path.basename(os.environ.get("SHELL", "bash")),
        "arch": platform.machine(),
    }


def _detect_distro() -> str:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system()


# ─── TOOL CATALOG ─────────────────────────────────────────────────────────────

def _render_tool_catalog(available_tools: list[ToolSpec]) -> str:
    lines = []
    for tool in available_tools:
        lines.append(f"  <tool name=\"{tool.name}\" risk=\"{tool.risk_class}\">")
        lines.append(f"    <use_when>{tool.when_to_use}</use_when>")
        lines.append(f"    <reveals>{tool.reveals}</reveals>")
        lines.append(f"  </tool>")
    return "\n".join(lines)


# ─── PROFILE GUIDANCE ──────────────────────────────────────────────────────────

def _get_profile_guidance(profile: str) -> str:
    return _load_profile(profile) if profile in {"web", "network", "ad"} else _load_profile("network")


def normalize_profile(profile: str, target: str) -> str:
    normalized = profile.lower().strip()
    if normalized in {"web", "network", "ad"}:
        return normalized
    if normalized == "auto":
        parsed = urlparse(target.strip())
        if parsed.scheme in {"http", "https"}:
            return "web"
        return "network"
    return "network"


# ─── DYNAMIC BLOCK ─────────────────────────────────────────────────────────────
# This block changes every turn. It carries current state: environment,
# target, scope, memory, and the tool catalog filtered for this run.
# Passed as the user message — never cached.

def build_planner_user_prompt(
    project: Project,
    objective: str,
    context_payload: dict,
    available_tools: list[ToolSpec],
    profile: str,
    allow_high_risk: bool,
    step_index: int = 1,
    max_steps: int = 20,
    loop_warning: str = "",
) -> str:
    local_env = _detect_local_env()
    context_text = render_context_for_prompt(context_payload)
    tools_text = _render_tool_catalog(available_tools)
    normalized_profile = normalize_profile(profile=profile, target=project.target)
    profile_guidance = _get_profile_guidance(normalized_profile)

    warning_block = (
        f"\n<warning priority=\"CRITICAL\">\n"
        f"{loop_warning.strip()}\n"
        f"</warning>\n"
    ) if loop_warning.strip() else ""

    return (
        f"<env>\n"
        f"  <platform>{local_env['distro']} / {local_env['os_release']} / {local_env['arch']}</platform>\n"
        f"  <shell>{local_env['shell']}</shell>\n"
        f"  <target>{project.target}</target>\n"
        f"  <scope>{project.primary_scope}</scope>\n"
        f"  <engagement_type>{project.engagement_type}</engagement_type>\n"
        f"  <profile>{normalized_profile}</profile>\n"
        f"  <high_risk_authorized>{'yes' if allow_high_risk else 'no'}</high_risk_authorized>\n"
        f"  <step>{step_index} of {max_steps}</step>\n"
        f"</env>\n"
        f"\n"
        f"<task>\n"
        f"  <objective>{objective}</objective>\n"
        f"  <profile_focus>{profile_guidance}</profile_focus>\n"
        f"</task>\n"
        f"\n"
        f"<memory>\n"
        f"{context_text}\n"
        f"</memory>\n"
        f"{warning_block}"
        f"\n"
        f"<tools>\n"
        f"{tools_text}\n"
        f"</tools>\n"
        f"\n"
        "Read <memory> for all current evidence. Match it against the <tools> 'use_when' fields. "
        "What is the most important open question right now, and which tool answers it?\n"
        "Return JSON only.\n"
    )
