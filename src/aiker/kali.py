from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from aiker.config import AppPaths


@dataclass(frozen=True)
class RuntimeCheck:
    name: str
    status: str
    value: str
    notes: str = ""


@dataclass(frozen=True)
class ToolCheck:
    name: str
    category: str
    required: bool
    status: str
    resolved_path: str = ""
    notes: str = ""


@dataclass(frozen=True)
class WordlistCheck:
    name: str
    path: str
    required: bool
    status: str
    notes: str = ""


@dataclass(frozen=True)
class EnvironmentReport:
    readiness: str
    readiness_reason: str
    is_linux: bool
    is_kali: bool
    distro_id: str
    distro_name: str
    distro_version: str
    runtime_checks: list[RuntimeCheck]
    tools: list[ToolCheck]
    wordlists: list[WordlistCheck]


@dataclass(frozen=True)
class ToolRequirement:
    name: str
    category: str
    binaries: tuple[str, ...]
    required: bool = False
    notes: str = ""


@dataclass(frozen=True)
class WordlistRequirement:
    name: str
    path: str
    required: bool = False
    notes: str = ""


TOOL_REQUIREMENTS: tuple[ToolRequirement, ...] = (
    ToolRequirement(name="nmap", category="network", binaries=("nmap",), required=True),
    ToolRequirement(name="rustscan", category="network", binaries=("rustscan",), required=True),
    ToolRequirement(name="curl", category="web", binaries=("curl",), required=True),
    ToolRequirement(name="wget", category="web", binaries=("wget",), required=True),
    ToolRequirement(name="dig", category="dns", binaries=("dig",), required=True),
    ToolRequirement(name="nslookup", category="dns", binaries=("nslookup",), required=True),
    ToolRequirement(name="whatweb", category="web", binaries=("whatweb",), required=True),
    ToolRequirement(name="wafw00f", category="web", binaries=("wafw00f",), required=True),
    ToolRequirement(name="nikto", category="web", binaries=("nikto",), required=True),
    ToolRequirement(name="nuclei", category="web", binaries=("nuclei",), required=True),
    ToolRequirement(name="ffuf", category="web", binaries=("ffuf",), required=True),
    ToolRequirement(name="gobuster", category="web", binaries=("gobuster",), required=True),
    ToolRequirement(name="sslscan", category="web", binaries=("sslscan",), required=False),
    ToolRequirement(name="amass", category="recon", binaries=("amass",), required=False),
    ToolRequirement(name="theHarvester", category="recon", binaries=("theHarvester", "theharvester"), required=False),
    ToolRequirement(name="sqlmap", category="attack", binaries=("sqlmap",), required=False),
    ToolRequirement(name="enum4linux-ng", category="ad-smb", binaries=("enum4linux-ng",), required=False),
    ToolRequirement(name="smbclient", category="ad-smb", binaries=("smbclient",), required=False),
    ToolRequirement(name="smbmap", category="ad-smb", binaries=("smbmap",), required=False),
    ToolRequirement(name="netexec", category="ad-smb", binaries=("netexec", "nxc"), required=False),
    ToolRequirement(name="crackmapexec", category="ad-smb", binaries=("crackmapexec",), required=False),
    ToolRequirement(name="ldapsearch", category="directory", binaries=("ldapsearch",), required=False),
    ToolRequirement(name="bloodhound-python", category="ad", binaries=("bloodhound-python",), required=False),
    ToolRequirement(name="responder", category="ad", binaries=("responder",), required=False),
    ToolRequirement(name="tcpdump", category="traffic", binaries=("tcpdump",), required=False),
    ToolRequirement(name="hydra", category="attack", binaries=("hydra",), required=False),
    ToolRequirement(name="burpsuite", category="web-ui", binaries=("burpsuite", "burp"), required=False),
    ToolRequirement(name="python3", category="runtime", binaries=("python3",), required=True),
    ToolRequirement(name="node", category="ui-runtime", binaries=("node",), required=False, notes="Needed for ink-cli."),
    ToolRequirement(name="npm", category="ui-runtime", binaries=("npm",), required=False, notes="Needed for ink-cli."),
)


WORDLIST_REQUIREMENTS: tuple[WordlistRequirement, ...] = (
    WordlistRequirement(
        name="dirb-common",
        path="/usr/share/wordlists/dirb/common.txt",
        required=True,
        notes="Used by aggressive web enumeration fallback.",
    ),
    WordlistRequirement(
        name="seclists-common",
        path="/usr/share/seclists/Discovery/Web-Content/common.txt",
        required=False,
        notes="Preferred larger baseline wordlist.",
    ),
    WordlistRequirement(
        name="rockyou",
        path="/usr/share/wordlists/rockyou.txt",
        required=False,
        notes="Useful for credential attack workflows.",
    ),
)


def _parse_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        values[key.strip()] = raw_value.strip().strip('"').strip("'")
    return values


def _tool_check(requirement: ToolRequirement) -> ToolCheck:
    resolved_path = ""
    matched_binary = ""
    for binary in requirement.binaries:
        candidate = shutil.which(binary)
        if candidate:
            resolved_path = candidate
            matched_binary = binary
            break

    status = "installed" if resolved_path else "missing"
    notes = requirement.notes
    if matched_binary and matched_binary != requirement.name:
        alias_note = f"resolved via '{matched_binary}'"
        notes = f"{notes}; {alias_note}".strip("; ").strip() if notes else alias_note

    return ToolCheck(
        name=requirement.name,
        category=requirement.category,
        required=requirement.required,
        status=status,
        resolved_path=resolved_path,
        notes=notes,
    )


def _wordlist_check(requirement: WordlistRequirement) -> WordlistCheck:
    exists = Path(requirement.path).exists()
    return WordlistCheck(
        name=requirement.name,
        path=requirement.path,
        required=requirement.required,
        status="present" if exists else "missing",
        notes=requirement.notes,
    )


def build_environment_report(paths: AppPaths) -> EnvironmentReport:
    os_release = _parse_os_release()
    is_linux = platform.system().lower() == "linux"
    distro_id = os_release.get("ID", "unknown")
    distro_name = os_release.get("PRETTY_NAME", platform.platform())
    distro_version = os_release.get("VERSION_ID", platform.release())
    distro_like = os_release.get("ID_LIKE", "")
    is_kali = distro_id == "kali" or "kali" in distro_like.split()

    tools = [_tool_check(requirement) for requirement in TOOL_REQUIREMENTS]
    wordlists = [_wordlist_check(requirement) for requirement in WORDLIST_REQUIREMENTS]

    runtime_checks = [
        RuntimeCheck(name="platform", status="ok" if is_linux else "unsupported", value=platform.system()),
        RuntimeCheck(
            name="distribution",
            status="ok" if is_kali else ("warn" if is_linux else "unsupported"),
            value=distro_name,
            notes="Kali Linux is the primary target runtime." if is_linux else "Linux is required.",
        ),
        RuntimeCheck(name="kernel", status="ok" if is_linux else "unsupported", value=platform.release()),
        RuntimeCheck(name="architecture", status="ok" if is_linux else "unsupported", value=platform.machine()),
        RuntimeCheck(
            name="python",
            status="ok",
            value=platform.python_version(),
            notes="Aiker requires Python 3.11+.",
        ),
        RuntimeCheck(
            name="openrouter_api_key",
            status="ok" if os.getenv("OPENROUTER_API_KEY") else "warn",
            value="configured" if os.getenv("OPENROUTER_API_KEY") else "missing",
            notes="Required for planner runs.",
        ),
        RuntimeCheck(
            name="aiker_home",
            status="ok",
            value=str(paths.root_dir),
            notes="Workspace root.",
        ),
        RuntimeCheck(
            name="projects_dir",
            status="ok" if paths.projects_dir.exists() else "warn",
            value=str(paths.projects_dir),
            notes="Created on first DB/session operation.",
        ),
        RuntimeCheck(
            name="data_dir",
            status="ok" if paths.data_dir.exists() else "warn",
            value=str(paths.data_dir),
            notes="Created on first DB/session operation.",
        ),
    ]

    missing_required_tools = [item for item in tools if item.required and item.status != "installed"]
    missing_required_wordlists = [item for item in wordlists if item.required and item.status != "present"]

    if not is_linux:
        readiness = "blocked"
        readiness_reason = "Aiker runtime is Linux-only."
    elif missing_required_tools or missing_required_wordlists:
        readiness = "partial"
        missing_labels = [item.name for item in missing_required_tools] + [item.name for item in missing_required_wordlists]
        readiness_reason = f"Missing required Kali dependencies: {', '.join(missing_labels)}"
    elif not is_kali:
        readiness = "partial"
        readiness_reason = "Linux is supported, but Kali Linux is the intended primary runtime."
    else:
        readiness = "ready"
        readiness_reason = "Core Kali runtime, required tools, and baseline wordlists are available."

    return EnvironmentReport(
        readiness=readiness,
        readiness_reason=readiness_reason,
        is_linux=is_linux,
        is_kali=is_kali,
        distro_id=distro_id,
        distro_name=distro_name,
        distro_version=distro_version,
        runtime_checks=runtime_checks,
        tools=tools,
        wordlists=wordlists,
    )
