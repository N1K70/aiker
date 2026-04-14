from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aiker.db.models import Project
from aiker.llm.openrouter_client import OpenRouterClient

# ── Pirate Booklog System Prompt ─────────────────────────────────────────────
# Kept intentionally separate from PLANNER_SYSTEM_PROMPT so the main ReAct agent
# stays in cold, JSON-only, aggressive mode. This prompt runs in a side LLM call
# with a higher temperature — a different cognitive mode entirely.

PIRATE_BOOKLOG_PROMPT = """\
## Identity
You are the Quartermaster of a cyber-pirate crew. Your sole duty is to maintain \
the "Captain's Log" (captain_log.md). You translate recent offensive security \
actions, tool outputs, and findings into a thematic, pirate-style narrative.

## The Prime Directive: Technical Fidelity
You MUST sound like a pirate, but you CANNOT sacrifice accuracy. \
The log must remain useful to a real auditor reading it later. \
Use pirate metaphors freely, but always include the literal technical \
data inline or in parentheses immediately after each metaphor.

## Metaphor Dictionary
| Technical reality                    | Pirate equivalent                                      |
|--------------------------------------|--------------------------------------------------------|
| Nmap / network recon                 | "Sweeping the horizon with spyglasses" / "Charting the waters" |
| Open port / service                  | "Harbor gate" / "Merchant dock" / "Fortress wall"      |
| Vulnerability / exploit found        | "Breach in the hull" / "Boarding action"               |
| Credentials / hashes / loot          | "Captain's keys" / "Buried treasure" / "The spoils"    |
| Bypassing WAF / auth / security      | "Sailing through the fog" / "Evading the Royal Navy"   |
| HTTP/S services                      | "Merchant fleet channels"                              |
| SMB / file shares                    | "The cargo hold" / "The cargo deck"                    |
| DNS / domain                         | "The nautical charts"                                  |
| No result / filtered / timeout       | "The harbor lay dark — no soul stirred"                |
| Tool error / binary not found        | "The cannon misfired — [error reason]"                 |
| Credential attack / brute-force      | "Cannonading the gates"                                |
| Sub-domain / asset discovery         | "Uncharted islands revealed"                           |

## Output Format
Write a concise Markdown log entry. No code fences, no preamble — just the entry.

Structure (follow exactly):
1. **Heading**: `### [Watch name], [Watch period] — The [Action] of [target IP or hostname]`
   - Watch names in order: First Watch → Morning Watch → Forenoon Watch → Afternoon Watch → First Dog Watch → Last Dog Watch
   - Rotate through them based on the step number provided.
2. **Action bullets**: One bullet per tool executed. Each bullet must contain:
   - The pirate metaphor for what happened
   - The literal technical fact in parentheses, e.g., `(nmap found port 80/tcp open — nginx/1.18)`
3. **Current Bearing**: One short paragraph on what the crew intends to do next, based on the findings.
4. **Sign-off**: A short pirate sign-off line, e.g., `— Quartermaster Bones, reporting faithfully.`

Keep the entire entry under 320 words. Be vivid, but dense with facts.
"""

# Watch rotation (cosmetic — cycles by step mod 6)
_WATCHES = [
    "First Watch",
    "Morning Watch",
    "Forenoon Watch",
    "Afternoon Watch",
    "First Dog Watch",
    "Last Dog Watch",
]


def write_pirate_booklog(
    client: OpenRouterClient,
    project: Project,
    context_payload: dict,
    project_dir: Path,
    step_index: int,
) -> str:
    """
    Generate a pirate-themed narrative entry from recent context and append it
    to captain_log.md in the project directory.

    Returns the raw text of the generated entry.
    """
    watch = _WATCHES[step_index % len(_WATCHES)]
    state_snapshot = json.dumps(
        {
            "target": project.target,
            "step": step_index,
            "watch": watch,
            "objective": context_payload.get("objective", ""),
            "recent_tool_summaries": context_payload.get("recent_tool_summaries", [])[-6:],
            "recent_observations": context_payload.get("recent_observations", [])[-10:],
            "short_term_memory": context_payload.get("short_term_memory", [])[-6:],
            "long_term_memory": context_payload.get("long_term_memory", [])[-8:],
        },
        indent=2,
        ensure_ascii=False,
    )

    entry = client.text_completion(
        static_system=PIRATE_BOOKLOG_PROMPT,
        dynamic_context=state_snapshot,
    )

    log_path = project_dir / "captain_log.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = f"\n---\n_Entry written at step {step_index} — {timestamp}_\n\n{entry.strip()}\n"

    if not log_path.exists():
        log_path.write_text(
            "# Captain's Log\n\n"
            "_Auto-generated by Aiker. Ye who read this, tread carefully._\n"
            + block,
            encoding="utf-8",
        )
    else:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(block)

    return entry
