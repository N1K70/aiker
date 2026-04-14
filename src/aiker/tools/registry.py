from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk_class: str
    when_to_use: str
    reveals: str


def default_tools() -> list[ToolSpec]:
    return [
        # ── Utility ──────────────────────────────────────────────────────────
        ToolSpec(
            name="append_finding",
            description="Record a finding into the engagement findings.md file.",
            risk_class="low",
            when_to_use=(
                "Immediately when you confirm something significant: an open attack path, exposed credentials, "
                "a vulnerable service version, anonymous access, a misconfiguration, or any result that would "
                "appear in a pentest report. Do not wait until the end — record findings as you discover them. "
                "Required fields: title (str), severity (critical/high/medium/low/info), evidence (the raw proof), "
                "detail (what it means and why it matters)."
            ),
            reveals="Confirms the finding was written to findings.md in the project folder.",
        ),
        ToolSpec(
            name="read_file",
            description="Read a file from the project folder.",
            risk_class="low",
            when_to_use="When a file was previously written to the project and you need to inspect its contents.",
            reveals="Raw file content saved during the engagement.",
        ),
        ToolSpec(
            name="write_file",
            description="Write text content to a file in the project folder.",
            risk_class="low",
            when_to_use="When you need to persist findings, notes, or structured output for later reference.",
            reveals="Confirms the file was written; no new recon data.",
        ),
        ToolSpec(
            name="summarize_context",
            description="Summarize all current project context and memory.",
            risk_class="low",
            when_to_use="When the engagement is complete and no further tool calls can produce new information.",
            reveals="A consolidated view of everything found so far.",
        ),

        # ── DNS / Reachability ────────────────────────────────────────────────
        ToolSpec(
            name="dig_lookup",
            description="Resolve DNS records for a hostname using dig.",
            risk_class="low",
            when_to_use="First step for any hostname target. Use to confirm the target resolves and collect IP addresses.",
            reveals="A/AAAA/MX/NS records, resolved IPs, nameservers. IPs revealed here are targets for port scanning.",
        ),
        ToolSpec(
            name="nslookup_lookup",
            description="Resolve DNS records using nslookup.",
            risk_class="low",
            when_to_use="Alternative to dig when dig is unavailable or to cross-check DNS results.",
            reveals="Resolved IP addresses and name server information.",
        ),

        # ── Port scanning ─────────────────────────────────────────────────────
        ToolSpec(
            name="nmap_scan",
            description="TCP port scan with service and version detection.",
            risk_class="medium",
            when_to_use="After confirming the host is reachable. Use to discover open ports and what service/version runs on each one.",
            reveals="Open TCP ports, service names, and version banners. Every open port is a lead: "
                    "port 80/443 → web stack; port 445 → SMB; port 22 → SSH; port 389/3268 → LDAP/AD; "
                    "port 3306 → MySQL; port 8080/8443 → alternate web; port 5985 → WinRM.",
        ),
        ToolSpec(
            name="rustscan_scan",
            description="Fast full-port TCP scan using rustscan, then passes results to nmap for service detection.",
            risk_class="medium",
            when_to_use="When you want faster port discovery than nmap alone, especially for full port range coverage.",
            reveals="Same as nmap — open ports and service banners — but with broader port coverage and faster results.",
        ),

        # ── HTTP / Web ────────────────────────────────────────────────────────
        ToolSpec(
            name="http_probe",
            description="Probe an HTTP/HTTPS endpoint and return headers and status.",
            risk_class="medium",
            when_to_use="Immediately after discovering port 80, 443, 8080, or any HTTP service in a scan. "
                        "Also use for any URL discovered during the engagement.",
            reveals="HTTP status code, server header (reveals software and version), response headers, "
                    "redirect chains. Server header leaks (Apache 2.4.49, nginx 1.14, IIS 10.0) are direct "
                    "CVE leads. Redirects reveal additional hostnames or paths to probe.",
        ),
        ToolSpec(
            name="curl_fetch",
            description="Fetch full HTTP response body using curl.",
            risk_class="low",
            when_to_use="After http_probe confirms a service is alive. Use to inspect page content, "
                        "find embedded links, forms, comments, or framework signatures in the body.",
            reveals="Full HTML/JSON body. Comments in source can leak internal paths, credentials, "
                    "software versions, and developer notes. Forms reveal input vectors to probe.",
        ),
        ToolSpec(
            name="wget_fetch",
            description="Fetch an HTTP resource using wget.",
            risk_class="low",
            when_to_use="Alternative to curl_fetch, or when you need to download a file from the target.",
            reveals="Full response body or downloaded file content.",
        ),
        ToolSpec(
            name="whatweb_fingerprint",
            description="Fingerprint web technologies, CMS, frameworks, and libraries.",
            risk_class="low",
            when_to_use="After confirming an HTTP service is alive. Reveals the technology stack to guide "
                        "vulnerability selection and further probing.",
            reveals="CMS (WordPress, Drupal, Joomla), frameworks (Laravel, Django, Rails), server software, "
                    "JavaScript libraries, analytics, and plugin signatures. Each identified technology "
                    "narrows the CVE search space significantly.",
        ),
        ToolSpec(
            name="wafw00f_detect",
            description="Detect the presence and type of a Web Application Firewall.",
            risk_class="low",
            when_to_use="After confirming a web service exists. WAF detection changes which tools and "
                        "techniques are viable next.",
            reveals="WAF vendor and product (Cloudflare, ModSecurity, Imperva, F5, etc.). "
                    "No WAF → aggressive scanning viable. WAF present → must consider evasion or focus "
                    "on logic flaws instead of pattern-detectable attacks.",
        ),
        ToolSpec(
            name="nikto_scan",
            description="Scan web server for common misconfigurations, outdated software, and dangerous files.",
            risk_class="medium",
            when_to_use="After fingerprinting the web stack. Nikto covers common misconfiguration checks "
                        "that fingerprinting alone won't reveal.",
            reveals="Default files, directory listings, outdated server software, dangerous HTTP methods "
                    "(PUT, DELETE), and known vulnerability signatures for common server software.",
        ),
        ToolSpec(
            name="nuclei_scan",
            description="Run template-based vulnerability checks against a target URL or host.",
            risk_class="medium",
            when_to_use="After identifying the web stack or service versions. Nuclei matches templates to "
                        "known CVEs and misconfigs for specific technologies.",
            reveals="Confirmed vulnerability matches with evidence (CVEs, exposed panels, default creds, "
                    "misconfigs). A nuclei hit is a validated finding, not a guess.",
        ),
        ToolSpec(
            name="gobuster_scan",
            description="Enumerate web paths and directories using a wordlist.",
            risk_class="medium",
            when_to_use="After confirming a web server is alive. Use to discover hidden paths, admin panels, "
                        "API endpoints, backup files, and upload directories.",
            reveals="Hidden directories and files: /admin, /backup, /api, /phpmyadmin, /upload, /.git, "
                    "/.env, /wp-admin, /console. Any discovered path is a new surface to probe.",
        ),
        ToolSpec(
            name="ffuf_scan",
            description="Fast web fuzzing for paths, parameters, and virtual hosts using ffuf.",
            risk_class="medium",
            when_to_use="Alternative to gobuster, or when you need parameter fuzzing or vhost enumeration "
                        "in addition to path discovery.",
            reveals="Hidden paths, parameters, and virtual hosts. More flexible than gobuster for "
                    "complex fuzzing scenarios.",
        ),
        ToolSpec(
            name="sslscan_probe",
            description="Inspect TLS/SSL configuration, certificate details, and cipher suites.",
            risk_class="low",
            when_to_use="When port 443 or any TLS-wrapped service is found. Reveals cert info and weak TLS config.",
            reveals="Certificate CN/SAN (can reveal internal hostnames and domain structure), "
                    "weak ciphers (SSLv3, TLS 1.0, RC4, NULL ciphers), and certificate expiry. "
                    "SAN entries often reveal additional hostnames to probe.",
        ),
        ToolSpec(
            name="sqlmap_scan",
            description="Automated SQL injection testing against a URL with a parameter.",
            risk_class="high",
            when_to_use="When a URL with query parameters has been discovered and the application is "
                        "known to interact with a database. Requires a specific injectable URL.",
            reveals="SQL injection vulnerability confirmation, database type, and potentially "
                    "extracted data if injection is successful.",
        ),
        ToolSpec(
            name="burp_suite_detect",
            description="Detect Burp Suite installation on the current operator machine.",
            risk_class="low",
            when_to_use="At the start of a web engagement to determine if Burp is available for manual "
                        "interception and deeper analysis.",
            reveals="Burp Suite installation paths and editions present on the machine.",
        ),

        # ── SMB / Windows / AD ────────────────────────────────────────────────
        ToolSpec(
            name="enum4linux_scan",
            description="Enumerate SMB, NetBIOS, and Windows domain information.",
            risk_class="medium",
            when_to_use="When port 445 or 139 is found open. Enumerates users, shares, policies, and domain info.",
            reveals="Usernames, group names, password policy, share names, workgroup/domain name, "
                    "and OS version. Usernames found here are targets for credential attacks.",
        ),
        ToolSpec(
            name="smbclient_list",
            description="List available SMB shares using smbclient.",
            risk_class="medium",
            when_to_use="After finding port 445 open. Use to list shares and test for anonymous or guest access.",
            reveals="Available share names and whether anonymous listing is permitted. "
                    "Readable shares may contain sensitive files, credentials, or scripts.",
        ),
        ToolSpec(
            name="smbmap_scan",
            description="Enumerate SMB shares and their read/write permissions.",
            risk_class="medium",
            when_to_use="After smbclient confirms shares exist. Smbmap reveals permissions on each share, "
                        "including read/write access.",
            reveals="Share names, access permissions (READ/WRITE/NO ACCESS), and connected user context. "
                    "Write access to a share is a critical finding.",
        ),
        ToolSpec(
            name="ldapsearch_enum",
            description="Query LDAP directory for users, groups, and organizational data.",
            risk_class="medium",
            when_to_use="When port 389 or 3268 (LDAP/Global Catalog) is found open, or when a Windows domain "
                        "is confirmed. Requires a base DN (e.g. DC=corp,DC=local).",
            reveals="Domain users, groups, computers, SPNs (Kerberoastable accounts), and organizational "
                    "structure. SPNs found here are targets for Kerberoasting.",
        ),
        ToolSpec(
            name="netexec_smb",
            description="Run SMB authentication and enumeration checks with netexec.",
            risk_class="high",
            when_to_use="When credentials have been obtained or guessed. Use to validate credentials "
                        "against SMB and check for local admin rights.",
            reveals="Credential validity, local admin status, SMB signing configuration, and OS details.",
        ),
        ToolSpec(
            name="crackmapexec_smb",
            description="Run SMB checks with crackmapexec (legacy alternative to netexec).",
            risk_class="high",
            when_to_use="Same as netexec_smb, when netexec is unavailable.",
            reveals="Same as netexec_smb.",
        ),
        ToolSpec(
            name="bloodhound_collect",
            description="Collect Active Directory graph data for BloodHound analysis.",
            risk_class="high",
            when_to_use="When valid domain credentials are available and the goal is to map privilege "
                        "escalation paths in the AD environment.",
            reveals="Full AD graph: users, computers, groups, ACLs, sessions, and attack paths to Domain Admin.",
        ),

        # ── OSINT / Recon ─────────────────────────────────────────────────────
        ToolSpec(
            name="amass_enum",
            description="Enumerate subdomains and DNS assets using amass.",
            risk_class="low",
            when_to_use="For external or domain targets where subdomain discovery can expand the attack surface.",
            reveals="Subdomains, IP ranges, ASN information, and additional hostnames. "
                    "Each subdomain found is a new target to probe.",
        ),
        ToolSpec(
            name="theharvester_enum",
            description="Collect emails, usernames, and hosts from public sources.",
            risk_class="low",
            when_to_use="For external engagements or when employee/user enumeration from public sources is in scope.",
            reveals="Email addresses, usernames, and hostnames from search engines and public databases. "
                    "Usernames found here can be used in credential attacks.",
        ),

        # ── Network interception ──────────────────────────────────────────────
        ToolSpec(
            name="responder_run",
            description="Run LLMNR/NBT-NS/mDNS poisoner to capture NetNTLM hashes.",
            risk_class="high",
            when_to_use="In an internal network segment where Windows hosts are broadcasting LLMNR/NBT-NS queries. "
                        "Requires a network interface name.",
            reveals="NetNTLM hashes from Windows hosts that respond to poisoned broadcasts. "
                    "Captured hashes can be cracked offline or relayed.",
        ),
        ToolSpec(
            name="tcpdump_capture",
            description="Capture network packets on a local interface.",
            risk_class="medium",
            when_to_use="When passive traffic analysis is needed, or to observe what protocols and hosts "
                        "are active on the network segment.",
            reveals="Live network traffic: protocols in use, communicating hosts, cleartext credentials "
                    "in unencrypted protocols (FTP, HTTP, Telnet, LDAP without TLS).",
        ),

        # ── Credential attacks ────────────────────────────────────────────────
        ToolSpec(
            name="hydra_attack",
            description="Brute-force login credentials against a service.",
            risk_class="high",
            when_to_use="When a login service (SSH, FTP, HTTP-form, SMB) is reachable and a credential list "
                        "is available. Use only when authorized and after softer approaches are exhausted.",
            reveals="Valid credentials for the target service if the attack succeeds.",
        ),
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
