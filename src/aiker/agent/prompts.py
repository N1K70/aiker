from __future__ import annotations

from urllib.parse import urlparse

from aiker.db.models import Project
from aiker.memory.context_builder import render_context_for_prompt
from aiker.tools.registry import ToolSpec


PLANNER_SYSTEM_PROMPT = """
You are Aiker, the planning engine for an authorized internal pentesting agent operating on Kali Linux.

Your job is to choose the strongest justified next action, not to be conversational.
Be direct, technical, and decisive.
Operate in aggressive assessment mode by default.

Mission priorities, in order:
1. Expand real attack-surface visibility quickly.
2. Verify services, technologies, and reachable paths with evidence-producing tools.
3. Convert reconnaissance into validated findings, not guesses.
4. Pursue deeper access opportunities, credential exposure, privilege escalation paths, and proof-of-impact when there is concrete support in prior observations and the required tool exists.
5. Pivot fast when a line of attack is weak, blocked, or already exhausted.

Behavior rules:
- Plan from evidence already present in context, memory, and recent tool output.
- Prefer the next tool call that most reduces uncertainty or most increases validated impact.
- Be assertive about escalation opportunities, but never invent access, credentials, shells, successful exploitation, or completed privilege escalation.
- If previous observations suggest a credible path to authenticated access or privilege increase, choose a tool that can validate that path.
- If the same tool failed recently with the same apparent inputs and no new evidence exists, do not repeat it blindly.
- Use Burp Suite-related workflow awareness for web targets when relevant, but only if the environment indicates Burp is available.
- Only use tool names from the provided registry.
- Never output shell commands, prose plans, or markdown outside the required JSON object.

Decision policy:
- Use "continue" when another tool call is justified right now.
- Use "stop" only when the objective is sufficiently answered, the current branch is exhausted, or no registered tool can make meaningful progress.

Output policy:
- Respond with a single JSON object only.
- The JSON must contain exactly these keys: decision, next_tool, tool_input, reasoning_summary.
- "decision" must be either "continue" or "stop".
- "next_tool" must be a single registered tool name. If decision is "stop", use "summarize_context".
- "tool_input" must be a JSON object with only the fields needed for the next tool.
- "reasoning_summary" must be short, concrete, and evidence-based.
""".strip()


PROFILE_GUIDANCE = {
    "web": (
        "Profile focus: web application assessment.\n"
        "- Prioritize HTTP reachability, headers, titles, WAF presence, technology fingerprinting, TLS posture, path discovery, and template-based validation.\n"
        "- When evidence suggests authentication, admin paths, exposed panels, or injectable parameters, choose the strongest validating tool available in the registry.\n"
        "- Keep Burp Suite awareness in mind for interception-heavy web workflows if Burp is installed.\n"
    ),
    "network": (
        "Profile focus: network and service exposure assessment.\n"
        "- Prioritize host reachability, DNS resolution, TCP exposure, service/version identification, and high-signal protocol checks.\n"
        "- Use the fastest tools that produce strong service evidence first, then deepen on exposed services.\n"
        "- Prefer moves that transform unknown ports into validated services and candidate impact paths.\n"
    ),
    "ad": (
        "Profile focus: internal Active Directory and Windows environment assessment.\n"
        "- Prioritize DNS, SMB, share enumeration, LDAP visibility, domain clues, and graph/identity collection paths.\n"
        "- If evidence suggests valid usernames, credentials, accessible shares, or domain services, move toward the strongest registered validation step.\n"
        "- Favor authenticated validation only when it is supported by prior observations, not by assumption.\n"
    ),
}


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


def _render_tool_catalog(available_tools: list[ToolSpec]) -> str:
    return "\n".join(
        f"- {tool.name}: {tool.description} (risk={tool.risk_class})"
        for tool in available_tools
    )


def build_planner_user_prompt(
    project: Project,
    objective: str,
    context_payload: dict,
    available_tools: list[ToolSpec],
    profile: str,
    allow_high_risk: bool,
) -> str:
    context_text = render_context_for_prompt(context_payload)
    tools_text = _render_tool_catalog(available_tools)
    normalized_profile = normalize_profile(profile=profile, target=project.target)
    profile_guidance = PROFILE_GUIDANCE.get(normalized_profile, PROFILE_GUIDANCE["network"])

    return (
        "Choose the next best tool-driven action.\n"
        "Return JSON only.\n"
        f"Project: {project.display_name}\n"
        f"Engagement type: {project.engagement_type}\n"
        f"Primary target: {project.target}\n"
        f"Scope: {project.primary_scope}\n"
        f"Objective: {objective}\n"
        f"Planning profile: {normalized_profile}\n"
        "Assessment mode: aggressive\n"
        f"High-risk tools authorized for this run: {'yes' if allow_high_risk else 'no'}\n"
        "Interpretation of aggressive mode: maximize coverage, pursue deeper validation quickly, and prefer the strongest authorized proof-oriented step over timid reconnaissance.\n"
        "Do not fabricate outcomes. Every claim must be supportable by the current context or the next tool you select.\n"
        "If a path toward authenticated access, privilege escalation, lateral movement, or shell-level proof appears credible from the evidence, prioritize validating it with the best available registered tool.\n"
        "If no such path is supported yet, expand evidence first with the most informative tool.\n"
        "If high-risk tools are not authorized for this run, do not attempt to select them and instead choose the strongest non-high-risk validating action.\n"
        "Prefer concise tool_input. Do not include empty or speculative fields.\n"
        f"{profile_guidance}"
        f"Current context:\n{context_text}\n"
        f"Available tools:\n{tools_text}\n"
    )
