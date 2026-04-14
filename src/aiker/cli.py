from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from sqlmodel import Session as DBSession

from aiker.agent.prompts import normalize_profile
from aiker.agent.react_loop import plan_next_step
from aiker.config import ensure_directories, get_app_paths
from aiker.db.engine import build_engine, init_db
from aiker.db.repositories import (
    get_project_by_id,
    get_project_by_target,
    get_session_by_id,
    list_memory_items,
    list_projects,
)
from aiker.kali import build_environment_report
from aiker.llm.openrouter_client import OpenRouterClient
from aiker.memory.context_builder import build_model_context
from aiker.memory.service import record_tool_outcome
from aiker.projects.service import CreateProjectInput, create_project
from aiker.sessions.service import start_session
from aiker.tools.executor import execute_tool
from aiker.tools.registry import default_tools, get_tool_spec, is_high_risk_tool

app = typer.Typer(help="Aiker CLI: ReAct pentest agent framework.")
project_app = typer.Typer(help="Project lifecycle commands.")
session_app = typer.Typer(help="Session lifecycle commands.")
tool_app = typer.Typer(help="Tool execution commands.")
memory_app = typer.Typer(help="Memory inspection commands.")
console = Console()

app.add_typer(project_app, name="project")
app.add_typer(session_app, name="session")
app.add_typer(tool_app, name="tool")
app.add_typer(memory_app, name="memory")


def _ensure_linux_runtime() -> None:
    if not sys.platform.startswith("linux"):
        raise typer.BadParameter("Aiker is Linux-only and is intended to run from Kali Linux or another Linux environment.")


def _status_style(status: str) -> str:
    mapping = {
        "ok": "green",
        "ready": "green",
        "installed": "green",
        "present": "green",
        "warn": "yellow",
        "partial": "yellow",
        "missing": "red",
        "error": "red",
        "unsupported": "red",
        "blocked": "red",
    }
    return mapping.get(status.lower().strip(), "white")


def _print_environment_report(report) -> None:
    readiness_style = _status_style(report.readiness)
    console.print(
        Panel.fit(
            f"[bold]{report.readiness.upper()}[/bold]\n{report.readiness_reason}",
            title="Aiker Doctor",
            border_style=readiness_style,
        )
    )

    runtime_table = Table(title="Runtime")
    runtime_table.add_column("Check", style="cyan")
    runtime_table.add_column("Status")
    runtime_table.add_column("Value")
    runtime_table.add_column("Notes")
    for item in report.runtime_checks:
        runtime_table.add_row(
            item.name,
            f"[{_status_style(item.status)}]{item.status}[/{_status_style(item.status)}]",
            item.value,
            item.notes,
        )
    console.print(runtime_table)

    tool_table = Table(title="Kali Tooling")
    tool_table.add_column("Tool", style="cyan")
    tool_table.add_column("Category")
    tool_table.add_column("Required")
    tool_table.add_column("Status")
    tool_table.add_column("Path")
    tool_table.add_column("Notes")
    for item in report.tools:
        tool_table.add_row(
            item.name,
            item.category,
            "yes" if item.required else "no",
            f"[{_status_style(item.status)}]{item.status}[/{_status_style(item.status)}]",
            item.resolved_path or "-",
            item.notes,
        )
    console.print(tool_table)

    wordlist_table = Table(title="Wordlists")
    wordlist_table.add_column("Wordlist", style="cyan")
    wordlist_table.add_column("Required")
    wordlist_table.add_column("Status")
    wordlist_table.add_column("Path")
    wordlist_table.add_column("Notes")
    for item in report.wordlists:
        wordlist_table.add_row(
            item.name,
            "yes" if item.required else "no",
            f"[{_status_style(item.status)}]{item.status}[/{_status_style(item.status)}]",
            item.path,
            item.notes,
        )
    console.print(wordlist_table)


def _print_workflow_preflight(report) -> None:
    readiness_style = _status_style(report.readiness)
    console.print(
        Panel.fit(
            f"[bold]{report.readiness.upper()}[/bold]\n{report.readiness_reason}",
            title="Workflow Preflight",
            border_style=readiness_style,
        )
    )

    missing_required_tools = [item.name for item in report.tools if item.required and item.status != "installed"]
    missing_required_wordlists = [item.name for item in report.wordlists if item.required and item.status != "present"]
    warnings: list[str] = []
    if not report.is_kali:
        warnings.append("Runtime is Linux, but not Kali. Coverage may differ from the intended operator stack.")
    if missing_required_tools:
        warnings.append(f"Missing required tools: {', '.join(missing_required_tools)}")
    if missing_required_wordlists:
        warnings.append(f"Missing required wordlists: {', '.join(missing_required_wordlists)}")

    if warnings:
        console.print(
            Panel(
                "\n".join(warnings),
                title="Preflight Warnings",
                border_style="yellow",
            )
        )


@app.callback()
def app_callback() -> None:
    _ensure_linux_runtime()


def _db_session() -> DBSession:
    _ensure_linux_runtime()
    paths = get_app_paths()
    ensure_directories(paths)
    init_db(paths)
    engine = build_engine(paths)
    return DBSession(engine)


def _project_dir(project_display_name: str):
    paths = get_app_paths()
    project_dir = paths.projects_dir / project_display_name
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _scope_seed(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme:
        return parsed.hostname or value
    return value


def _default_web_wordlist() -> str | None:
    candidates = [
        r"/usr/share/wordlists/dirb/common.txt",
        r"/usr/share/seclists/Discovery/Web-Content/common.txt",
        r"/usr/share/dirb/wordlists/common.txt",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _log_step(project_dir: Path, step: int, tool: str, reasoning: str, status: str, summary: str, raw_output: str) -> None:
    log_path = project_dir / "engagement_log.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    status_mark = "✓" if status == "success" else "✗"
    preview = raw_output[:1200].strip() if raw_output else ""
    if len(raw_output) > 1200:
        preview += "\n... truncated ..."
    block = (
        f"\n### Step {step} — {tool} [{status_mark}]\n"
        f"_{timestamp}_\n\n"
        f"**Reasoning:** {reasoning}\n\n"
        f"**Result:** {summary}\n\n"
        f"```\n{preview}\n```\n"
        f"\n---\n"
    )
    if not log_path.exists():
        header = (
            f"# Engagement Log\n\n"
            f"_Auto-generated by Aiker. Do not edit manually._\n"
            f"\n---\n"
        )
        log_path.write_text(header + block, encoding="utf-8")
    else:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(block)


def _render_preview(raw_output: str, max_chars: int = 2200, max_line_length: int = 140, max_lines: int = 36) -> str:
    clipped = raw_output[:max_chars]
    lines: list[str] = []
    for line in clipped.splitlines():
        if len(line) > max_line_length:
            lines.append(f"{line[: max_line_length - 3]}...")
        else:
            lines.append(line)
        if len(lines) >= max_lines:
            lines.append("... output truncated ...")
            break
    return "\n".join(lines)


def _auto_recon_sequence(target: str, profile: str, mode: str) -> list[tuple[str, dict]]:
    profile_normalized = profile.lower().strip()
    mode_normalized = mode.lower().strip()
    is_web = target.startswith(("http://", "https://"))
    wordlist = _default_web_wordlist()
    network_tasks: list[tuple[str, dict]] = [
        ("dig_lookup", {"target": target}),
        ("nslookup_lookup", {"target": target}),
        ("nmap_scan", {"target": target}),
        ("rustscan_scan", {"target": target}),
        ("http_probe", {"target": target}),
        ("curl_fetch", {"target": target}),
    ]
    web_tasks: list[tuple[str, dict]] = [
        ("dig_lookup", {"target": target}),
        ("nslookup_lookup", {"target": target}),
        ("http_probe", {"target": target}),
        ("burp_suite_detect", {}),
        ("curl_fetch", {"target": target}),
        ("wget_fetch", {"target": target}),
        ("whatweb_fingerprint", {"target": target}),
        ("wafw00f_detect", {"target": target}),
        ("nikto_scan", {"target": target}),
        ("nuclei_scan", {"target": target}),
        ("sslscan_probe", {"target": target}),
    ]
    ad_tasks: list[tuple[str, dict]] = [
        ("dig_lookup", {"target": target}),
        ("nslookup_lookup", {"target": target}),
        ("nmap_scan", {"target": target}),
        ("enum4linux_scan", {"target": target}),
        ("smbclient_list", {"target": target}),
        ("smbmap_scan", {"target": target}),
        ("http_probe", {"target": target}),
    ]

    if mode_normalized == "aggressive":
        network_tasks.extend(
            [
                ("wget_fetch", {"target": target}),
            ]
        )
        if wordlist:
            web_tasks.extend(
                [
                    ("gobuster_scan", {"target": target, "wordlist": wordlist}),
                    ("ffuf_scan", {"target": target, "wordlist": wordlist}),
                ]
            )
        ad_tasks.extend(
            [
                ("whatweb_fingerprint", {"target": target}),
            ]
        )
    elif mode_normalized != "safe":
        raise typer.BadParameter("mode must be one of: aggressive, safe")

    if profile_normalized == "network":
        return network_tasks
    if profile_normalized == "web":
        return web_tasks
    if profile_normalized == "ad":
        return ad_tasks
    if profile_normalized == "auto":
        return web_tasks if is_web else network_tasks
    raise typer.BadParameter("profile must be one of: auto, web, network, ad")


@project_app.command("create")
def project_create(
    target: Annotated[str, typer.Option("--target", help="Primary target host or domain.")],
    label: Annotated[str, typer.Option("--label", help="Human-friendly engagement label.")] = "",
    scope: Annotated[list[str] | None, typer.Option("--scope", help="Scope item, repeatable.")] = None,
    engagement_type: Annotated[str, typer.Option("--engagement-type", help="Engagement type.")] = "internal-pentest",
) -> None:
    paths = get_app_paths()
    selected_scope = scope if scope else [_scope_seed(target)]
    payload = CreateProjectInput(target=target, label=label, scope=selected_scope, engagement_type=engagement_type)
    with _db_session() as db:
        project = create_project(db=db, paths=paths, payload=payload)

    console.print(f"Created project id={project.id} name='{project.display_name}'", style="green")
    console.print(f"Folder: {paths.projects_dir / project.display_name}", markup=False, no_wrap=True)


@project_app.command("list")
def project_list() -> None:
    with _db_session() as db:
        projects = list_projects(db)

    table = Table(title="Projects")
    table.add_column("ID", style="cyan")
    table.add_column("Seq")
    table.add_column("Name", style="magenta")
    table.add_column("Target")
    table.add_column("Scope")
    table.add_column("Status")

    for item in projects:
        table.add_row(str(item.id), str(item.sequence_number), item.display_name, item.target, item.primary_scope, item.status)

    console.print(table)


@app.command("doctor")
def doctor() -> None:
    paths = get_app_paths()
    ensure_directories(paths)
    report = build_environment_report(paths=paths)
    _print_environment_report(report)


@app.command("workflow")
def workflow(
    target: Annotated[str | None, typer.Option("--target", help="IP or URL to start reconnaissance.")] = None,
    label: Annotated[str, typer.Option("--label", help="Optional project label.")] = "autoflow",
    goal: Annotated[str, typer.Option("--goal", help="Session goal.")] = "Find real attack paths and validate them with proof",
    profile: Annotated[str, typer.Option("--profile", help="Planning profile: auto, web, network, ad.")] = "auto",
    allow_high_risk: Annotated[bool, typer.Option("--allow-high-risk", help="Authorize high-risk tools.")] = False,
    max_steps: Annotated[int, typer.Option("--max-steps", help="Maximum ReAct steps before hard stop.")] = 20,
    show_raw: Annotated[bool, typer.Option("--show-raw", help="Show raw output preview for each step.")] = True,
) -> None:
    if not target:
        target = typer.prompt("Target IP or URL").strip()
    if not target:
        raise typer.BadParameter("target is required.")
    if max_steps < 1:
        raise typer.BadParameter("max-steps must be >= 1")
    if profile.lower().strip() not in {"auto", "web", "network", "ad"}:
        raise typer.BadParameter("profile must be one of: auto, web, network, ad")

    try:
        client = OpenRouterClient.from_env()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    _print_workflow_preflight(build_environment_report(paths=get_app_paths()))

    with _db_session() as db:
        project = get_project_by_target(db, target)
        if project is None:
            payload = CreateProjectInput(
                target=target,
                label=label,
                scope=[_scope_seed(target)],
                engagement_type="internal-pentest",
            )
            project = create_project(db=db, paths=get_app_paths(), payload=payload)
            console.print(f"[green]New project:[/green] {project.display_name}")
        else:
            console.print(f"[cyan]Resuming project:[/cyan] {project.display_name}")

        session_obj = start_session(db=db, project_id=project.id, goal=goal, operator_name="autoflow")
        console.print(f"[green]Session:[/green] {session_obj.id}\n")

        resolved_profile = normalize_profile(profile=profile, target=project.target)
        project_dir = _project_dir(project.display_name)
        timeline: list[dict] = []

        # Write session header to engagement log
        log_path = project_dir / "engagement_log.md"
        session_header = (
            f"\n## Session {session_obj.id} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"**Target:** {target}  **Profile:** {resolved_profile}  **Goal:** {goal}\n\n---\n"
        )
        if not log_path.exists():
            log_path.write_text(
                f"# Engagement Log\n\n_Auto-generated by Aiker. Do not edit manually._\n{session_header}",
                encoding="utf-8",
            )
        else:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(session_header)

        console.print(f"[dim]Log:[/dim] {log_path}\n")

        for step_index in range(1, max_steps + 1):
            # --- Plan ---
            context_payload = build_model_context(db=db, project_id=project.id, objective=goal)
            with console.status(f"[bold cyan][{step_index}/{max_steps}] Planning next move...[/bold cyan]"):
                plan = plan_next_step(
                    client=client,
                    project=project,
                    objective=goal,
                    context_payload=context_payload,
                    profile=resolved_profile,
                    allow_high_risk=allow_high_risk,
                    step_index=step_index,
                    max_steps=max_steps,
                )

            if is_high_risk_tool(plan.next_tool) and not allow_high_risk:
                console.print(
                    f"[yellow]Planner selected high-risk tool '{plan.next_tool}' — skipping (use --allow-high-risk to authorize).[/yellow]"
                )
                break

            # --- Show what the agent is thinking ---
            console.rule(f"[bold magenta]Step {step_index}[/bold magenta]")
            console.print(f"[dim]Observation:[/dim] {plan.observation_reflection}")
            console.print(f"[bold]Plan:[/bold]        {plan.next_plan}")
            console.print(f"[bold]Tool:[/bold]        [cyan]{plan.next_tool}[/cyan]", end="")
            if plan.tool_input:
                console.print(f"  [dim]{json.dumps(plan.tool_input)}[/dim]")
            else:
                console.print()

            # --- Execute ---
            t_start = time.monotonic()
            with console.status(f"[cyan]Running {plan.next_tool}...[/cyan]"):
                result = execute_tool(
                    tool_name=plan.next_tool,
                    tool_input=plan.tool_input,
                    project=project,
                    project_dir=project_dir,
                    context_payload=context_payload,
                )
            elapsed = time.monotonic() - t_start

            execution_id = record_tool_outcome(
                db=db,
                project_id=project.id,
                session_id=session_obj.id,
                tool_name=plan.next_tool,
                tool_input=plan.tool_input,
                result=result,
            )

            # Write step to engagement log automatically
            _log_step(
                project_dir=project_dir,
                step=step_index,
                tool=plan.next_tool,
                reasoning=plan.reasoning_summary,
                status=result.status,
                summary=result.summary,
                raw_output=result.raw_output,
            )

            timeline.append(
                {
                    "step": step_index,
                    "tool": plan.next_tool,
                    "status": result.status,
                    "elapsed": f"{elapsed:.1f}s",
                    "reasoning": plan.reasoning_summary,
                    "summary": result.summary,
                    "execution_id": execution_id,
                    "raw_output": result.raw_output,
                }
            )

            status_style = "green" if result.status == "success" else "red"
            console.print(
                f"[{status_style}]{result.status.upper()}[/{status_style}]  "
                f"[dim]{elapsed:.1f}s[/dim]  {result.summary}"
            )

            if show_raw and result.raw_output:
                preview = _render_preview(result.raw_output)
                console.print(
                    Panel(
                        preview,
                        title=f"[dim]{plan.next_tool} output[/dim]",
                        border_style="blue",
                        padding=(0, 1),
                    )
                )

            if plan.decision == "stop":
                console.print("\n[yellow]Agent reached a stopping point.[/yellow]")
                break

        # --- Final timeline summary ---
        console.rule("[bold]Workflow Complete[/bold]")
        summary_table = Table(title=f"Timeline — {target}", show_lines=False, box=None)
        summary_table.add_column("#", style="dim", width=3)
        summary_table.add_column("Tool", style="cyan", min_width=20)
        summary_table.add_column("Status", width=9)
        summary_table.add_column("Time", width=7)
        summary_table.add_column("Reasoning / Finding")
        for entry in timeline:
            s = entry["status"]
            status_cell = f"[green]{s}[/green]" if s == "success" else f"[red]{s}[/red]"
            note = entry["reasoning"] if len(entry["reasoning"]) <= 80 else f"{entry['reasoning'][:77]}..."
            summary_table.add_row(str(entry["step"]), entry["tool"], status_cell, entry["elapsed"], note)
        console.print(summary_table)


@session_app.command("start")
def session_start(
    project_id: Annotated[int, typer.Option("--project-id", help="Project id to bind the session.")],
    goal: Annotated[str, typer.Option("--goal", help="Operator objective for this session.")],
    operator: Annotated[str, typer.Option("--operator", help="Operator name.")] = "unknown",
) -> None:
    with _db_session() as db:
        session_obj = start_session(db=db, project_id=project_id, goal=goal, operator_name=operator)
    console.print(
        f"[green]Started session[/green] id={session_obj.id} project_id={session_obj.project_id} goal='{session_obj.goal}'"
    )


@app.command("run")
def run_once(
    project_id: Annotated[int, typer.Option("--project-id", help="Project id to use.")],
    objective: Annotated[str, typer.Option("--objective", help="Current objective for this planning step.")],
    profile: Annotated[str, typer.Option("--profile", help="Planning profile: auto, web, network, ad.")] = "auto",
    mode: Annotated[str, typer.Option("--mode", help="Planning mode: aggressive or safe.")] = "aggressive",
    allow_high_risk: Annotated[
        bool,
        typer.Option("--allow-high-risk", help="Allow the planner to choose tools marked as high risk."),
    ] = False,
    steps: Annotated[int, typer.Option("--steps", help="Number of ReAct iterations to execute.")] = 1,
    session_id: Annotated[int | None, typer.Option("--session-id", help="Existing session id to use.")] = None,
    operator: Annotated[str, typer.Option("--operator", help="Operator name if auto-creating a session.")] = "aiker-auto",
) -> None:
    if steps < 1:
        raise typer.BadParameter("steps must be >= 1")
    if mode.lower().strip() not in {"aggressive", "safe"}:
        raise typer.BadParameter("mode must be one of: aggressive, safe")
    if profile.lower().strip() not in {"auto", "web", "network", "ad"}:
        raise typer.BadParameter("profile must be one of: auto, web, network, ad")

    try:
        client = OpenRouterClient.from_env()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    with _db_session() as db:
        project = get_project_by_id(db, project_id)
        if project is None:
            raise typer.BadParameter(f"Project id {project_id} does not exist.")

        active_session_id = session_id
        if active_session_id is None:
            session_obj = start_session(db=db, project_id=project_id, goal=objective, operator_name=operator)
            active_session_id = session_obj.id
        else:
            existing_session = get_session_by_id(db, active_session_id)
            if existing_session is None:
                raise typer.BadParameter(f"Session id {active_session_id} does not exist.")
            if existing_session.project_id != project_id:
                raise typer.BadParameter("session_id does not belong to the provided project_id.")

        project_dir = _project_dir(project.display_name)
        resolved_profile = normalize_profile(profile=profile, target=project.target)

        for step_index in range(1, steps + 1):
            context_payload = build_model_context(
                db=db,
                project_id=project_id,
                objective=f"{objective} (mode={mode}, profile={resolved_profile})",
            )
            plan = plan_next_step(
                client=client,
                project=project,
                objective=f"{objective} (mode={mode}, profile={resolved_profile})",
                context_payload=context_payload,
                profile=resolved_profile,
                allow_high_risk=allow_high_risk,
                step_index=step_index,
                max_steps=steps,
            )
            if is_high_risk_tool(plan.next_tool) and not allow_high_risk:
                raise typer.BadParameter(
                    f"Planner selected high-risk tool '{plan.next_tool}' without --allow-high-risk."
                )
            tool_result = execute_tool(
                tool_name=plan.next_tool,
                tool_input=plan.tool_input,
                project=project,
                project_dir=project_dir,
                context_payload=context_payload,
            )
            execution_id = record_tool_outcome(
                db=db,
                project_id=project_id,
                session_id=active_session_id,
                tool_name=plan.next_tool,
                tool_input=plan.tool_input,
                result=tool_result,
            )

            console.print(f"\n[bold]Step {step_index}/{steps}[/bold]")
            console.print(
                Panel(
                    json.dumps(
                        {
                            "decision": plan.decision,
                            "next_tool": plan.next_tool,
                            "tool_input": plan.tool_input,
                            "reasoning_summary": plan.reasoning_summary,
                            "profile": resolved_profile,
                            "allow_high_risk": allow_high_risk,
                            "tool_status": tool_result.status,
                            "tool_summary": tool_result.summary,
                            "execution_id": execution_id,
                        },
                        indent=2,
                    ),
                    title="ReAct Step Result",
                    border_style="cyan",
                )
            )

            decision = plan.decision.lower().strip()
            if decision in {"stop", "done", "complete"}:
                console.print("[yellow]Stopping because model decision requested stop.[/yellow]")
                break


@tool_app.command("list")
def tool_list() -> None:
    table = Table(title="Tool Catalog")
    table.add_column("Tool", style="cyan")
    table.add_column("Risk")
    table.add_column("Description")
    for spec in default_tools():
        table.add_row(spec.name, spec.risk_class, spec.description)
    console.print(table)


@tool_app.command("call")
def tool_call(
    project_id: Annotated[int, typer.Option("--project-id", help="Project id to use.")],
    tool_name: Annotated[str, typer.Option("--tool", help="Registered tool name.")],
    input_json: Annotated[str, typer.Option("--input-json", help="Tool input as JSON object.")] = "{}",
    input_json_file: Annotated[
        Path | None, typer.Option("--input-json-file", help="Path to a JSON file with tool input.")
    ] = None,
    session_id: Annotated[int | None, typer.Option("--session-id", help="Optional session id for persistence.")] = None,
    ack_high_risk: Annotated[
        bool,
        typer.Option("--ack-high-risk", help="Acknowledge and allow execution of a tool marked as high risk."),
    ] = False,
) -> None:
    if get_tool_spec(tool_name) is None:
        raise typer.BadParameter(f"Unknown tool: {tool_name}")
    if is_high_risk_tool(tool_name) and not ack_high_risk:
        raise typer.BadParameter(
            f"Tool '{tool_name}' is high risk. Re-run with --ack-high-risk to execute it."
        )
    if input_json_file is not None:
        input_json = input_json_file.read_text(encoding="utf-8")
    try:
        parsed_input = json.loads(input_json)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"input-json must be valid JSON: {exc}") from exc
    if not isinstance(parsed_input, dict):
        raise typer.BadParameter("input-json must be a JSON object.")

    with _db_session() as db:
        project = get_project_by_id(db, project_id)
        if project is None:
            raise typer.BadParameter(f"Project id {project_id} does not exist.")
        if session_id is not None:
            existing_session = get_session_by_id(db, session_id)
            if existing_session is None:
                raise typer.BadParameter(f"Session id {session_id} does not exist.")
            if existing_session.project_id != project_id:
                raise typer.BadParameter("session_id does not belong to the provided project_id.")

        project_dir = _project_dir(project.display_name)
        context_payload = build_model_context(db=db, project_id=project_id, objective="manual_tool_call")
        tool_result = execute_tool(
            tool_name=tool_name,
            tool_input=parsed_input,
            project=project,
            project_dir=project_dir,
            context_payload=context_payload,
        )
        execution_id = record_tool_outcome(
            db=db,
            project_id=project_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_input=parsed_input,
            result=tool_result,
        )

    console.print(
        Panel(
            json.dumps(
                {
                    "tool": tool_name,
                    "status": tool_result.status,
                    "summary": tool_result.summary,
                    "facts_extracted": tool_result.facts_extracted,
                    "execution_id": execution_id,
                },
                indent=2,
            ),
            title="Tool Result",
            border_style="green" if tool_result.status == "success" else "red",
        )
    )


@memory_app.command("show")
def memory_show(
    project_id: Annotated[int, typer.Option("--project-id", help="Project id to inspect.")],
    tier: Annotated[str | None, typer.Option("--tier", help="Memory tier filter.")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum number of rows.")] = 30,
) -> None:
    if limit < 1:
        raise typer.BadParameter("limit must be >= 1")

    with _db_session() as db:
        project = get_project_by_id(db, project_id)
        if project is None:
            raise typer.BadParameter(f"Project id {project_id} does not exist.")
        rows = list_memory_items(db=db, project_id=project_id, memory_tier=tier, limit=limit)

    table = Table(title=f"Memory: {project.display_name}")
    table.add_column("ID", style="cyan")
    table.add_column("Tier", style="magenta")
    table.add_column("Importance")
    table.add_column("Expires")
    table.add_column("Content")
    for item in rows:
        expires = item.expires_at.isoformat() if item.expires_at else "-"
        content = item.content if len(item.content) <= 90 else f"{item.content[:87]}..."
        table.add_row(str(item.id), item.memory_tier, str(item.importance), expires, content)
    console.print(table)
