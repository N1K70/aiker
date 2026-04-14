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
    # Two-stage reasoning — forces the model to reflect before it acts.
    # observation_reflection: what the previous tool output means.
    # next_plan: therefore, what this step will do and why.
    observation_reflection: str
    next_plan: str

    @property
    def reasoning_summary(self) -> str:
        """Composite for display and logging."""
        return f"{self.observation_reflection} → {self.next_plan}"


def plan_next_step(
    client: OpenRouterClient,
    project: Project,
    objective: str,
    context_payload: dict,
    profile: str = "auto",
    allow_high_risk: bool = False,
    step_index: int = 1,
    max_steps: int = 20,
    loop_warning: str = "",
) -> ReactPlanResult:
    available_tools = filter_tools_by_risk(allow_high_risk=allow_high_risk)
    prompt = build_planner_user_prompt(
        project=project,
        objective=objective,
        context_payload=context_payload,
        available_tools=available_tools,
        profile=profile,
        allow_high_risk=allow_high_risk,
        step_index=step_index,
        max_steps=max_steps,
        loop_warning=loop_warning,
    )
    result = client.json_completion(static_system=PLANNER_SYSTEM_PROMPT, dynamic_context=prompt)

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
        observation_reflection=str(result.get("observation_reflection", "No prior observation.")).strip(),
        next_plan=str(result.get("next_plan", "")).strip() or str(result.get("reasoning_summary", "")).strip() or "No plan.",
    )
