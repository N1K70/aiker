from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk_class: str


def default_tools() -> list[ToolSpec]:
    return [
        ToolSpec(name="read_file", description="Read text files from project scope.", risk_class="low"),
        ToolSpec(name="write_file", description="Write text files in project notes/exports.", risk_class="low"),
        ToolSpec(name="summarize_context", description="Summarize project/session context.", risk_class="low"),
        ToolSpec(name="nmap_scan", description="Run network discovery scans.", risk_class="medium"),
        ToolSpec(name="rustscan_scan", description="Fast TCP port scan with rustscan.", risk_class="medium"),
        ToolSpec(name="http_probe", description="Probe HTTP services and metadata.", risk_class="medium"),
        ToolSpec(name="nuclei_scan", description="Run template-based vuln checks.", risk_class="medium"),
        ToolSpec(name="whatweb_fingerprint", description="Fingerprint web technologies.", risk_class="low"),
        ToolSpec(name="nikto_scan", description="Run basic web misconfiguration checks.", risk_class="medium"),
        ToolSpec(name="ffuf_scan", description="Bruteforce web paths with ffuf.", risk_class="medium"),
        ToolSpec(name="gobuster_scan", description="Enumerate web paths with gobuster.", risk_class="medium"),
        ToolSpec(name="sqlmap_scan", description="Test SQL injection vectors with sqlmap.", risk_class="high"),
        ToolSpec(name="amass_enum", description="Enumerate DNS assets with amass.", risk_class="low"),
        ToolSpec(name="theharvester_enum", description="Collect OSINT from public sources.", risk_class="low"),
        ToolSpec(name="wafw00f_detect", description="Detect web application firewall.", risk_class="low"),
        ToolSpec(name="sslscan_probe", description="Inspect TLS/SSL setup.", risk_class="low"),
        ToolSpec(name="enum4linux_scan", description="Enumerate SMB/NetBIOS info.", risk_class="medium"),
        ToolSpec(name="smbclient_list", description="List SMB shares with smbclient.", risk_class="medium"),
        ToolSpec(name="smbmap_scan", description="Enumerate SMB shares and permissions.", risk_class="medium"),
        ToolSpec(name="netexec_smb", description="Run SMB checks with netexec.", risk_class="high"),
        ToolSpec(name="crackmapexec_smb", description="Run SMB checks with crackmapexec.", risk_class="high"),
        ToolSpec(name="ldapsearch_enum", description="Enumerate LDAP information.", risk_class="medium"),
        ToolSpec(name="bloodhound_collect", description="Collect AD graph data.", risk_class="high"),
        ToolSpec(name="responder_run", description="Run LLMNR/NBT-NS poisoner.", risk_class="high"),
        ToolSpec(name="tcpdump_capture", description="Capture packets with tcpdump.", risk_class="medium"),
        ToolSpec(name="dig_lookup", description="Resolve DNS records with dig.", risk_class="low"),
        ToolSpec(name="nslookup_lookup", description="Resolve DNS records with nslookup.", risk_class="low"),
        ToolSpec(name="curl_fetch", description="Fetch URL response with curl.", risk_class="low"),
        ToolSpec(name="wget_fetch", description="Fetch URL response with wget.", risk_class="low"),
        ToolSpec(name="burp_suite_detect", description="Detect Burp Suite installation and likely launch paths.", risk_class="low"),
        ToolSpec(name="hydra_attack", description="Credential attack with hydra.", risk_class="high"),
    ]


def get_tool_spec(tool_name: str) -> ToolSpec | None:
    for tool in default_tools():
        if tool.name == tool_name:
            return tool
    return None


def is_high_risk_tool(tool_name: str) -> bool:
    tool = get_tool_spec(tool_name)
    return bool(tool and tool.risk_class == "high")


def filter_tools_by_risk(allow_high_risk: bool) -> list[ToolSpec]:
    if allow_high_risk:
        return default_tools()
    return [tool for tool in default_tools() if tool.risk_class != "high"]


def tool_names() -> set[str]:
    return {tool.name for tool in default_tools()}
