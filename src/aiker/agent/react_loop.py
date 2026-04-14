from __future__ import annotations

from dataclasses import dataclass

from aiker.agent.prompts import PLANNER_SYSTEM_PROMPT, build_planner_user_prompt
from aiker.db.models import Project
from aiker.llm.openrouter_client import OpenRouterClient
from aiker.tools.registry import filter_tools_by_risk, tool_names


@dataclass(frozen=True)
class ReactPlanResult:
    decision: str
    next_tool: str
    tool_input: dict
    reasoning_summary: str


def plan_next_step(
    client: OpenRouterClient,
    project: Project,
    objective: str,
    context_payload: dict,
    profile: str = "auto",
    allow_high_risk: bool = False,
) -> ReactPlanResult:
    available_tools = filter_tools_by_risk(allow_high_risk=allow_high_risk)
    prompt = build_planner_user_prompt(
        project=project,
        objective=objective,
        context_payload=context_payload,
        available_tools=available_tools,
        profile=profile,
        allow_high_risk=allow_high_risk,
    )
    result = client.json_completion(system_prompt=PLANNER_SYSTEM_PROMPT, user_prompt=prompt)
    selected_tool = str(result.get("next_tool", "")).strip()
    selected_decision = str(result.get("decision", "continue")).strip().lower()
    if selected_decision not in {"continue", "stop"}:
        selected_decision = "continue"
    if selected_tool not in tool_names():
        selected_tool = "summarize_context"
    if selected_decision == "stop":
        selected_tool = "summarize_context"
    return ReactPlanResult(
        decision=selected_decision,
        next_tool=selected_tool,
        tool_input=result.get("tool_input", {}) if isinstance(result.get("tool_input", {}), dict) else {},
        reasoning_summary=str(result.get("reasoning_summary", "No reasoning summary.")),
    )
