from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from aiker.db.models import Project


@dataclass(frozen=True)
class ToolResult:
    status: str
    summary: str
    raw_output: str
    artifacts: list[str]
    facts_extracted: list[str]
    confidence: float


def _scope_values(project: Project) -> set[str]:
    return {entry.strip() for entry in project.primary_scope.split(",") if entry.strip()}


def _extract_host(candidate: str) -> str:
    parsed = urlparse(candidate)
    if parsed.scheme:
        return parsed.hostname or candidate
    return candidate


def _target_from_input(project: Project, tool_input: dict) -> str:
    return str(tool_input.get("target", project.target)).strip()


def _url_from_target(target: str) -> str:
    return target if target.startswith(("http://", "https://")) else f"http://{target}"


def _is_in_scope(project: Project, candidate: str) -> bool:
    scope = _scope_values(project)
    if not scope:
        return True
    host = _extract_host(candidate)
    return host in scope


def _resolve_project_path(project_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    resolved = (project_dir / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    project_root = project_dir.resolve()
    if resolved != project_root and project_root not in resolved.parents:
        raise ValueError("Path escapes project directory.")
    return resolved


def _error(summary: str, raw_output: str = "") -> ToolResult:
    return ToolResult(
        status="error",
        summary=summary,
        raw_output=raw_output,
        artifacts=[],
        facts_extracted=[],
        confidence=0.0,
    )


def _ensure_binary(binary: str) -> ToolResult | None:
    if shutil.which(binary) is None:
        return _error(f"{binary} is not installed or not in PATH.")
    return None


def _run_command(args: list[str], timeout_seconds: int = 120) -> ToolResult:
    command_text = " ".join(args)
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except FileNotFoundError:
        return _error(f"Command not found: {args[0]}")
    except subprocess.TimeoutExpired:
        return _error(f"Command timed out after {timeout_seconds}s", raw_output=f"Command: {command_text}")

    status = "success" if result.returncode == 0 else "error"
    summary = f"Executed command with exit code {result.returncode}: {command_text}"
    output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    return ToolResult(
        status=status,
        summary=summary,
        raw_output=output[:120000],
        artifacts=[],
        facts_extracted=[],
        confidence=0.85 if status == "success" else 0.2,
    )


def _with_facts(result: ToolResult, facts: list[str], confidence_floor: float | None = None) -> ToolResult:
    merged_facts = list(dict.fromkeys(result.facts_extracted + [fact for fact in facts if fact.strip()]))
    confidence = result.confidence
    if confidence_floor is not None and confidence < confidence_floor:
        confidence = confidence_floor
    return ToolResult(
        status=result.status,
        summary=result.summary,
        raw_output=result.raw_output,
        artifacts=result.artifacts,
        facts_extracted=merged_facts,
        confidence=confidence,
    )


def _extract_nmap_facts(text: str) -> list[str]:
    facts: list[str] = []
    for port, service in re.findall(r"(?m)^(\d{1,5})/tcp\s+open\s+([a-zA-Z0-9_.-]+)", text):
        facts.append(f"open_port={port}/tcp")
        facts.append(f"service={port}/tcp:{service}")
    return facts


def _extract_http_facts(text: str) -> list[str]:
    facts: list[str] = []
    status_match = re.search(r"HTTP/\d(?:\.\d)?\s+(\d{3})", text)
    if status_match:
        facts.append(f"http_status={status_match.group(1)}")
    server_match = re.search(r"(?im)^server:\s*(.+)$", text)
    if server_match:
        facts.append(f"http_server={server_match.group(1).strip()}")
    title_match = re.search(r"(?is)<title>(.*?)</title>", text)
    if title_match:
        title = " ".join(title_match.group(1).split())
        if title:
            facts.append(f"http_title={title[:120]}")
    return facts


def _extract_ip_facts(text: str) -> list[str]:
    ips = set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text))
    return [f"ip_seen={ip}" for ip in sorted(ips)]


def _extract_whatweb_facts(text: str) -> list[str]:
    facts: list[str] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return facts
    first_line = lines[0]
    if "[" in first_line and "]" in first_line:
        chunks = re.findall(r"\[([^\]]+)\]", first_line)
        for chunk in chunks:
            if chunk and ":" not in chunk:
                facts.append(f"web_tech={chunk}")
    return facts


def _read_file(project_dir: Path, tool_input: dict) -> ToolResult:
    path_value = str(tool_input.get("path", "")).strip()
    if not path_value:
        return _error("Missing required input: path")
    resolved_path = _resolve_project_path(project_dir, path_value)
    if not resolved_path.exists() or not resolved_path.is_file():
        return _error(f"File not found: {resolved_path}")
    content = resolved_path.read_text(encoding="utf-8", errors="replace")
    return ToolResult(
        status="success",
        summary=f"Read file: {resolved_path}",
        raw_output=content[:120000],
        artifacts=[str(resolved_path)],
        facts_extracted=[f"file_path={resolved_path}", f"file_size={len(content)}"],
        confidence=1.0,
    )


def _write_file(project_dir: Path, tool_input: dict) -> ToolResult:
    path_value = str(tool_input.get("path", "")).strip()
    if not path_value:
        return _error("Missing required input: path")
    content = str(tool_input.get("content", ""))
    append_mode = bool(tool_input.get("append", False))
    resolved_path = _resolve_project_path(project_dir, path_value)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    if append_mode:
        with resolved_path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(content)
    else:
        resolved_path.write_text(content, encoding="utf-8")
    return ToolResult(
        status="success",
        summary=f"Wrote file: {resolved_path}",
        raw_output=content[:4000],
        artifacts=[str(resolved_path)],
        facts_extracted=[f"file_path={resolved_path}", f"append={append_mode}"],
        confidence=1.0,
    )


def _append_finding(project_dir: Path, tool_input: dict) -> ToolResult:
    title = str(tool_input.get("title", "")).strip()
    severity = str(tool_input.get("severity", "info")).strip().lower()
    evidence = str(tool_input.get("evidence", "")).strip()
    detail = str(tool_input.get("detail", "")).strip()

    if not title:
        return _error("append_finding requires title.")
    if severity not in {"critical", "high", "medium", "low", "info"}:
        severity = "info"

    findings_path = project_dir / "findings.md"
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = (
        f"\n## [{severity.upper()}] {title}\n"
        f"_Recorded: {timestamp}_\n\n"
        f"{detail}\n\n"
        f"**Evidence:**\n```\n{evidence}\n```\n"
        f"\n---\n"
    )

    if not findings_path.exists():
        findings_path.write_text(f"# Findings\n\n_Auto-generated by Aiker during engagement._\n{block}", encoding="utf-8")
    else:
        with findings_path.open("a", encoding="utf-8") as fh:
            fh.write(block)

    return ToolResult(
        status="success",
        summary=f"Finding recorded: [{severity.upper()}] {title}",
        raw_output=block,
        artifacts=[str(findings_path)],
        facts_extracted=[f"finding={severity}:{title}"],
        confidence=1.0,
    )


def _summarize_context(context_payload: dict) -> ToolResult:
    compact = {
        "objective": context_payload.get("objective", ""),
        "recent_observations": context_payload.get("recent_observations", []),
        "short_term_memory": context_payload.get("short_term_memory", []),
        "long_term_memory": context_payload.get("long_term_memory", []),
        "situational_memory": context_payload.get("situational_memory", []),
    }
    rendered = json.dumps(compact, ensure_ascii=True, indent=2)
    return ToolResult(
        status="success",
        summary="Summarized current project context.",
        raw_output=rendered[:120000],
        artifacts=[],
        facts_extracted=[],
        confidence=0.9,
    )


def _nmap_scan(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("nmap")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("Missing target for nmap_scan.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    ports = str(tool_input.get("ports", "")).strip()
    timeout_seconds = max(10, min(int(tool_input.get("timeout_seconds", 180)), 900))
    args = ["nmap", "-Pn", "-sV", "--top-ports", "100", target]
    if ports:
        args.extend(["-p", ports])
    result = _run_command(args, timeout_seconds=timeout_seconds)
    return _with_facts(result, _extract_nmap_facts(result.raw_output), confidence_floor=0.9)


def _rustscan_scan(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("rustscan")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("Missing target for rustscan_scan.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    timeout_seconds = max(20, min(int(tool_input.get("timeout_seconds", 180)), 900))
    args = ["rustscan", "-a", target, "--ulimit", "5000", "--", "-sV", "--top-ports", "100"]
    result = _run_command(args, timeout_seconds=timeout_seconds)
    return _with_facts(result, _extract_nmap_facts(result.raw_output), confidence_floor=0.85)


def _http_probe(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("curl")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("Missing target for http_probe.")
    url = _url_from_target(target)
    if not _is_in_scope(project, url):
        return _error(f"Target outside project scope: {url}")
    timeout_seconds = max(5, min(int(tool_input.get("timeout_seconds", 20)), 120))
    args = ["curl", "-I", "--max-time", str(timeout_seconds), url]
    result = _run_command(args, timeout_seconds=timeout_seconds + 10)
    return _with_facts(result, [f"http_url={url}"] + _extract_http_facts(result.raw_output), confidence_floor=0.8)


def _nuclei_scan(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("nuclei")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("Missing target for nuclei_scan.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    timeout_seconds = max(30, min(int(tool_input.get("timeout_seconds", 240)), 1200))
    args = ["nuclei", "-u", target]
    return _run_command(args, timeout_seconds=timeout_seconds)


def _whatweb_fingerprint(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("whatweb")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("Missing target for whatweb_fingerprint.")
    url = _url_from_target(target)
    if not _is_in_scope(project, url):
        return _error(f"Target outside project scope: {url}")
    result = _run_command(["whatweb", url], timeout_seconds=120)
    return _with_facts(result, [f"http_url={url}"] + _extract_whatweb_facts(result.raw_output), confidence_floor=0.8)


def _nikto_scan(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("nikto")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("Missing target for nikto_scan.")
    url = _url_from_target(target)
    if not _is_in_scope(project, url):
        return _error(f"Target outside project scope: {url}")
    timeout_seconds = max(30, min(int(tool_input.get("timeout_seconds", 300)), 1200))
    return _run_command(["nikto", "-h", url], timeout_seconds=timeout_seconds)


def _ffuf_scan(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("ffuf")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    wordlist = str(tool_input.get("wordlist", "")).strip()
    if not target or not wordlist:
        return _error("ffuf_scan requires target and wordlist.")
    url = _url_from_target(target)
    if not _is_in_scope(project, url):
        return _error(f"Target outside project scope: {url}")
    return _run_command(["ffuf", "-u", f"{url.rstrip('/')}/FUZZ", "-w", wordlist, "-t", "30"], timeout_seconds=600)


def _gobuster_scan(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("gobuster")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    wordlist = str(tool_input.get("wordlist", "")).strip()
    if not target or not wordlist:
        return _error("gobuster_scan requires target and wordlist.")
    url = _url_from_target(target)
    if not _is_in_scope(project, url):
        return _error(f"Target outside project scope: {url}")
    args = ["gobuster", "dir", "-u", url, "-w", wordlist, "-t", "20"]
    return _run_command(args, timeout_seconds=600)


def _sqlmap_scan(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("sqlmap")
    if check:
        return check
    url = str(tool_input.get("url", "")).strip()
    if not url:
        return _error("sqlmap_scan requires url.")
    if not _is_in_scope(project, url):
        return _error(f"Target outside project scope: {url}")
    return _run_command(["sqlmap", "-u", url, "--batch"], timeout_seconds=900)


def _amass_enum(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("amass")
    if check:
        return check
    domain = str(tool_input.get("domain", "")).strip()
    if not domain:
        domain = _extract_host(_target_from_input(project, tool_input))
    if not domain:
        return _error("amass_enum requires domain.")
    return _run_command(["amass", "enum", "-d", domain], timeout_seconds=600)


def _theharvester_enum(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("theHarvester")
    if check:
        return check
    domain = str(tool_input.get("domain", "")).strip()
    source = str(tool_input.get("source", "bing")).strip()
    if not domain:
        domain = _extract_host(_target_from_input(project, tool_input))
    if not domain:
        return _error("theharvester_enum requires domain.")
    args = ["theHarvester", "-d", domain, "-b", source]
    return _run_command(args, timeout_seconds=480)


def _wafw00f_detect(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("wafw00f")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("wafw00f_detect requires target.")
    url = _url_from_target(target)
    if not _is_in_scope(project, url):
        return _error(f"Target outside project scope: {url}")
    return _run_command(["wafw00f", url], timeout_seconds=180)


def _sslscan_probe(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("sslscan")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    port = str(tool_input.get("port", "443")).strip()
    if not target:
        return _error("sslscan_probe requires target.")
    host = _extract_host(target)
    if not _is_in_scope(project, host):
        return _error(f"Target outside project scope: {host}")
    return _run_command(["sslscan", f"{host}:{port}"], timeout_seconds=240)


def _enum4linux_scan(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("enum4linux-ng")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("enum4linux_scan requires target.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    return _run_command(["enum4linux-ng", "-A", target], timeout_seconds=600)


def _smbclient_list(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("smbclient")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    username = str(tool_input.get("username", "")).strip()
    password = str(tool_input.get("password", "")).strip()
    if not target:
        return _error("smbclient_list requires target.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    if username:
        return _run_command(["smbclient", "-L", f"//{target}", "-U", f"{username}%{password}"], timeout_seconds=240)
    return _run_command(["smbclient", "-L", f"//{target}", "-N"], timeout_seconds=240)


def _smbmap_scan(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("smbmap")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("smbmap_scan requires target.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    return _run_command(["smbmap", "-H", target], timeout_seconds=240)


def _netexec_smb(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("netexec")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    username = str(tool_input.get("username", "")).strip()
    password = str(tool_input.get("password", "")).strip()
    if not target or not username:
        return _error("netexec_smb requires target and username.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    return _run_command(["netexec", "smb", target, "-u", username, "-p", password], timeout_seconds=300)


def _crackmapexec_smb(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("crackmapexec")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    username = str(tool_input.get("username", "")).strip()
    password = str(tool_input.get("password", "")).strip()
    if not target or not username:
        return _error("crackmapexec_smb requires target and username.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    return _run_command(["crackmapexec", "smb", target, "-u", username, "-p", password], timeout_seconds=300)


def _ldapsearch_enum(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("ldapsearch")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    base_dn = str(tool_input.get("base_dn", "")).strip()
    if not target or not base_dn:
        return _error("ldapsearch_enum requires target and base_dn.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    args = ["ldapsearch", "-x", "-H", f"ldap://{target}", "-b", base_dn]
    return _run_command(args, timeout_seconds=300)


def _bloodhound_collect(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("bloodhound-python")
    if check:
        return check
    domain = str(tool_input.get("domain", "")).strip()
    username = str(tool_input.get("username", "")).strip()
    password = str(tool_input.get("password", "")).strip()
    nameserver = str(tool_input.get("nameserver", project.target)).strip()
    if not domain or not username:
        return _error("bloodhound_collect requires domain and username.")
    if not _is_in_scope(project, nameserver):
        return _error(f"Target outside project scope: {nameserver}")
    args = [
        "bloodhound-python",
        "-d",
        domain,
        "-u",
        username,
        "-p",
        password,
        "-ns",
        nameserver,
        "-c",
        "All",
    ]
    return _run_command(args, timeout_seconds=1200)


def _responder_run(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("responder")
    if check:
        return check
    interface = str(tool_input.get("interface", "")).strip()
    if not interface:
        return _error("responder_run requires interface.")
    args = ["responder", "-I", interface, "-rdw"]
    return _run_command(args, timeout_seconds=max(20, min(int(tool_input.get("timeout_seconds", 60)), 300)))


def _tcpdump_capture(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("tcpdump")
    if check:
        return check
    interface = str(tool_input.get("interface", "")).strip()
    count = str(tool_input.get("count", "50")).strip()
    if not interface:
        return _error("tcpdump_capture requires interface.")
    args = ["tcpdump", "-i", interface, "-c", count]
    return _run_command(args, timeout_seconds=max(20, min(int(tool_input.get("timeout_seconds", 120)), 300)))


def _dig_lookup(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("dig")
    if check:
        return check
    target = _extract_host(_target_from_input(project, tool_input))
    if not target:
        return _error("dig_lookup requires target.")
    result = _run_command(["dig", target], timeout_seconds=60)
    return _with_facts(result, [f"dns_query={target}"] + _extract_ip_facts(result.raw_output), confidence_floor=0.75)


def _nslookup_lookup(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("nslookup")
    if check:
        return check
    target = _extract_host(_target_from_input(project, tool_input))
    if not target:
        return _error("nslookup_lookup requires target.")
    result = _run_command(["nslookup", target], timeout_seconds=60)
    return _with_facts(result, [f"dns_query={target}"] + _extract_ip_facts(result.raw_output), confidence_floor=0.75)


def _curl_fetch(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("curl")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("curl_fetch requires target.")
    url = _url_from_target(target)
    if not _is_in_scope(project, url):
        return _error(f"Target outside project scope: {url}")
    result = _run_command(["curl", "-L", "--max-time", "30", url], timeout_seconds=60)
    return _with_facts(result, [f"http_url={url}"] + _extract_http_facts(result.raw_output), confidence_floor=0.75)


def _wget_fetch(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("wget")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    if not target:
        return _error("wget_fetch requires target.")
    url = _url_from_target(target)
    if not _is_in_scope(project, url):
        return _error(f"Target outside project scope: {url}")
    result = _run_command(["wget", "-qO-", url], timeout_seconds=60)
    return _with_facts(result, [f"http_url={url}"] + _extract_http_facts(result.raw_output), confidence_floor=0.75)


def _hydra_attack(project: Project, tool_input: dict) -> ToolResult:
    check = _ensure_binary("hydra")
    if check:
        return check
    target = _target_from_input(project, tool_input)
    service = str(tool_input.get("service", "")).strip()
    user_list = str(tool_input.get("user_list", "")).strip()
    pass_list = str(tool_input.get("pass_list", "")).strip()
    if not target or not service or not user_list or not pass_list:
        return _error("hydra_attack requires target, service, user_list, pass_list.")
    if not _is_in_scope(project, target):
        return _error(f"Target outside project scope: {target}")
    args = ["hydra", "-L", user_list, "-P", pass_list, f"{service}://{target}"]
    return _run_command(args, timeout_seconds=900)


def _burp_suite_detect() -> ToolResult:
    candidate_paths: list[str] = []

    for binary in ("burpsuite", "burp"):
        resolved = shutil.which(binary)
        if resolved:
            candidate_paths.append(resolved)

    common_paths = [
        "/usr/bin/burpsuite",
        "/usr/local/bin/burpsuite",
        "/opt/BurpSuiteCommunity/BurpSuiteCommunity",
        "/opt/BurpSuitePro/BurpSuitePro",
    ]
    for path_value in common_paths:
        if Path(path_value).exists():
            candidate_paths.append(path_value)

    unique_paths = list(dict.fromkeys(candidate_paths))
    if unique_paths:
        rendered = "\n".join(unique_paths)
        return ToolResult(
            status="success",
            summary="Burp Suite installation detected.",
            raw_output=rendered,
            artifacts=unique_paths,
            facts_extracted=["burp_installed=true"] + [f"burp_path={path}" for path in unique_paths],
            confidence=1.0,
        )

    return ToolResult(
        status="error",
        summary="Burp Suite was not detected on the current host.",
        raw_output="",
        artifacts=[],
        facts_extracted=["burp_installed=false"],
        confidence=0.6,
    )


def execute_tool(
    tool_name: str,
    tool_input: dict,
    project: Project,
    project_dir: Path,
    context_payload: dict | None = None,
) -> ToolResult:
    handlers = {
        "read_file": lambda: _read_file(project_dir=project_dir, tool_input=tool_input),
        "write_file": lambda: _write_file(project_dir=project_dir, tool_input=tool_input),
        "append_finding": lambda: _append_finding(project_dir=project_dir, tool_input=tool_input),
        "summarize_context": lambda: _summarize_context(context_payload=context_payload or {}),
        "nmap_scan": lambda: _nmap_scan(project=project, tool_input=tool_input),
        "rustscan_scan": lambda: _rustscan_scan(project=project, tool_input=tool_input),
        "http_probe": lambda: _http_probe(project=project, tool_input=tool_input),
        "nuclei_scan": lambda: _nuclei_scan(project=project, tool_input=tool_input),
        "whatweb_fingerprint": lambda: _whatweb_fingerprint(project=project, tool_input=tool_input),
        "nikto_scan": lambda: _nikto_scan(project=project, tool_input=tool_input),
        "ffuf_scan": lambda: _ffuf_scan(project=project, tool_input=tool_input),
        "gobuster_scan": lambda: _gobuster_scan(project=project, tool_input=tool_input),
        "sqlmap_scan": lambda: _sqlmap_scan(project=project, tool_input=tool_input),
        "amass_enum": lambda: _amass_enum(project=project, tool_input=tool_input),
        "theharvester_enum": lambda: _theharvester_enum(project=project, tool_input=tool_input),
        "wafw00f_detect": lambda: _wafw00f_detect(project=project, tool_input=tool_input),
        "sslscan_probe": lambda: _sslscan_probe(project=project, tool_input=tool_input),
        "enum4linux_scan": lambda: _enum4linux_scan(project=project, tool_input=tool_input),
        "smbclient_list": lambda: _smbclient_list(project=project, tool_input=tool_input),
        "smbmap_scan": lambda: _smbmap_scan(project=project, tool_input=tool_input),
        "netexec_smb": lambda: _netexec_smb(project=project, tool_input=tool_input),
        "crackmapexec_smb": lambda: _crackmapexec_smb(project=project, tool_input=tool_input),
        "ldapsearch_enum": lambda: _ldapsearch_enum(project=project, tool_input=tool_input),
        "bloodhound_collect": lambda: _bloodhound_collect(project=project, tool_input=tool_input),
        "responder_run": lambda: _responder_run(project=project, tool_input=tool_input),
        "tcpdump_capture": lambda: _tcpdump_capture(project=project, tool_input=tool_input),
        "dig_lookup": lambda: _dig_lookup(project=project, tool_input=tool_input),
        "nslookup_lookup": lambda: _nslookup_lookup(project=project, tool_input=tool_input),
        "curl_fetch": lambda: _curl_fetch(project=project, tool_input=tool_input),
        "wget_fetch": lambda: _wget_fetch(project=project, tool_input=tool_input),
        "burp_suite_detect": lambda: _burp_suite_detect(),
        "hydra_attack": lambda: _hydra_attack(project=project, tool_input=tool_input),
    }
    handler = handlers.get(tool_name)
    if handler is None:
        return _error(f"Unknown tool: {tool_name}")
    try:
        return handler()
    except ValueError as exc:
        return _error(str(exc))
