"""
modules/redteam.py — Red Team Cybersecurity Simulator
Kill chain: Recon → Weaponize → Deliver → Exploit → Post-Exploit → Report
Tools: theHarvester, amass, searchsploit, sqlmap, msfconsole, linpeas,
       pspy, msfvenom, enum4linux, crackmapexec, responder, mimikatz (sim)

ALL SIMULATED — educational only. No real exploitation occurs.
"""

import time, random, hashlib
from core.ui import *
from core.world import fake_ip, fake_mac, fake_cve

# ── Fake data ──────────────────────────────────────────────────────────────────

DOMAINS = ["acme-corp.local", "target.local", "corp.internal", "vulnlab.net"]
EMAILS  = [
    "admin@{d}", "info@{d}", "ceo@{d}", "helpdesk@{d}",
    "webmaster@{d}", "devops@{d}", "noreply@{d}", "security@{d}",
]
SUBDOMAINS = [
    "mail", "vpn", "admin", "portal", "api", "dev", "staging",
    "git", "jenkins", "jira", "confluence", "backup", "ftp", "smtp",
]
EXPLOITS = [
    {"id":"EDB-49757","name":"Apache 2.4.49 Path Traversal","type":"webapps","cve":"CVE-2021-41773","severity":"CRITICAL"},
    {"id":"EDB-50383","name":"Log4Shell Remote Code Execution","type":"remote","cve":"CVE-2021-44228","severity":"CRITICAL"},
    {"id":"EDB-47837","name":"OpenSSH Username Enumeration","type":"remote","cve":"CVE-2018-15473","severity":"MEDIUM"},
    {"id":"EDB-42315","name":"EternalBlue SMB Remote Code Execution","type":"remote","cve":"CVE-2017-0144","severity":"CRITICAL"},
    {"id":"EDB-39161","name":"HFS HTTP File Server 2.3 RCE","type":"remote","cve":"CVE-2014-6287","severity":"HIGH"},
    {"id":"EDB-44289","name":"MySQL 5.5 UDF Privilege Escalation","type":"local","cve":"CVE-2016-6662","severity":"HIGH"},
    {"id":"EDB-45010","name":"Linux Kernel 4.13 Local Privilege Escalation","type":"local","cve":"CVE-2017-16995","severity":"HIGH"},
    {"id":"EDB-41020","name":"Shellshock Bash Remote Code Execution","type":"remote","cve":"CVE-2014-6271","severity":"CRITICAL"},
    {"id":"EDB-48653","name":"Sudo Heap Overflow","type":"local","cve":"CVE-2021-3156","severity":"HIGH"},
    {"id":"EDB-50064","name":"PrintNightmare Windows Priv Esc","type":"local","cve":"CVE-2021-1675","severity":"CRITICAL"},
]
MSF_MODULES = [
    "exploit/multi/handler",
    "exploit/windows/smb/ms17_010_eternalblue",
    "exploit/unix/webapp/apache_mod_cgi_bash_env_exec",
    "exploit/multi/http/log4shell_header_injection",
    "auxiliary/scanner/smb/smb_ms17_010",
    "auxiliary/scanner/portscan/tcp",
    "auxiliary/scanner/ssh/ssh_login",
    "post/linux/gather/hashdump",
    "post/multi/recon/local_exploit_suggester",
    "post/linux/manage/shell_to_meterpreter",
]
PRIVESC_FINDINGS = [
    ("HIGH",    "SUID binary found: /usr/bin/nmap  (version < 5.21 allows shell escape)"),
    ("CRITICAL","Sudo rule: ALL=(ALL) NOPASSWD: /usr/bin/vim  — trivial shell escape"),
    ("HIGH",    "Writable /etc/passwd detected — can add root-level user"),
    ("MEDIUM",  "World-writable cron job: /etc/cron.d/backup.sh"),
    ("HIGH",    "Docker socket accessible to current user: /var/run/docker.sock"),
    ("MEDIUM",  "Kernel version 4.15 — check for CVE-2017-16995 (eBPF privesc)"),
    ("LOW",     "NFS share mounted with no_root_squash"),
    ("HIGH",    "PATH hijack possible — /tmp in PATH before /usr/bin"),
    ("CRITICAL","Credentials in env: DB_PASSWORD=s3cr3tpassword123"),
    ("HIGH",    "Unencrypted SSH private key found: /home/user/.ssh/id_rsa"),
]
LOOT_EXAMPLES = [
    ("/etc/shadow",              "Password hashes — crack with hashcat/john"),
    ("/home/user/.ssh/id_rsa",  "SSH private key — lateral movement"),
    ("/var/www/html/.env",      "App secrets: DB_PASS, JWT_SECRET, API_KEY"),
    ("/opt/app/config.yaml",    "Database credentials in plaintext"),
    ("C:\\SAM",                 "Windows SAM hive — extract with secretsdump"),
    ("/root/.bash_history",     "Command history — may contain credentials"),
    ("/etc/krb5.keytab",        "Kerberos keytab — AS-REP roasting possible"),
]
PAYLOAD_TYPES = {
    "linux/x64/meterpreter/reverse_tcp": ("ELF",  "Meterpreter reverse TCP — Linux x64"),
    "windows/x64/meterpreter/reverse_tcp":("EXE", "Meterpreter reverse TCP — Windows x64"),
    "cmd/unix/reverse_bash":              ("SH",   "Bash reverse shell — simple, no deps"),
    "php/meterpreter/reverse_tcp":        ("PHP",  "PHP web shell with Meterpreter"),
    "python/meterpreter/reverse_tcp":     ("PY",   "Python reverse shell — cross-platform"),
    "java/shell_reverse_tcp":             ("JAR",  "Java reverse shell — works with Log4j"),
}

SEV_COL = {
    "CRITICAL": f"{BG_RED}{B}{BWHITE}",
    "HIGH":     f"{BRED}{B}",
    "MEDIUM":   f"{BYELLOW}",
    "LOW":      f"{BBLUE}",
    "INFO":     f"{DIM}",
}
def sev(s):
    return f"{SEV_COL.get(s,'')} {s:<8} {R}"


class RedTeamModule:
    def __init__(self, world, save):
        self.w = world
        self.s = save
        # Persistent red team state
        if not hasattr(self.w, "rt_state"):
            self.w.rt_state = {
                "phase":        "recon",
                "target":       None,
                "emails":       [],
                "subdomains":   [],
                "open_ports":   [],
                "exploited":    False,
                "shell_type":   None,
                "loot":         [],
                "listener_up":  False,
                "sessions":     {},
                "report_items": [],
            }

    def _rt(self): return self.w.rt_state

    def _xp(self, pts, reason):
        lvl = self.s.add_xp(pts, reason)
        xp_flash(pts, reason)
        if lvl > 0:
            from core.save import LEVEL_TITLES, level_for_xp
            lv = level_for_xp(self.s.get("xp", 0))
            print(f"\n  {BYELLOW}{B}★ LEVEL UP → Level {lv}{R}\n")

    def _phase_banner(self, phase):
        colors = {
            "recon":    BCYAN,
            "weaponize":BYELLOW,
            "deliver":  BMAGENTA,
            "exploit":  BRED,
            "post":     f"{BG_RED}{BYELLOW}",
            "report":   BGREEN,
        }
        col = colors.get(phase, BCYAN)
        print(f"\n  {col}{B}[ PHASE: {phase.upper()} ]{R}\n")

    def _require_phase(self, needed_phases, cmd):
        """Warn if player is skipping phases (on hard+)."""
        if self.s.get("difficulty", 2) >= 3:
            rt = self._rt()
            if rt["phase"] not in needed_phases and rt["phase"] != "report":
                print(warn(f"  ⚠ You should complete the '{needed_phases[0]}' phase first."))
                print(dim(f"  Current phase: {rt['phase']}"))

    # ═══════════════════════════════════════════════════════════════════════════
    # RECON
    # ═══════════════════════════════════════════════════════════════════════════

    def theHarvester(self, args):
        """OSINT email and subdomain harvesting."""
        domain = None
        source = "all"
        limit  = 100
        for i, a in enumerate(args):
            if a == "-d" and i+1 < len(args): domain = args[i+1]
            elif a == "-b" and i+1 < len(args): source = args[i+1]
            elif a == "-l" and i+1 < len(args):
                try: limit = int(args[i+1])
                except: pass

        if not domain:
            print(warn("  Usage: theHarvester -d <domain> -b <source> [-l limit]"))
            print(dim("  Sources: google  bing  linkedin  twitter  shodan  all"))
            return

        self._phase_banner("recon")
        print(f"  {BRED}theHarvester{R} v4.4.2")
        print(f"  Target domain : {cyan(domain)}")
        print(f"  Data source   : {source}")
        print()

        spinner("Querying data sources", 2.0)

        # Emails
        n_emails = random.randint(4, 12)
        emails   = [e.format(d=domain) for e in random.sample(EMAILS, min(n_emails, len(EMAILS)))]
        emails  += [f"user{random.randint(1,99)}@{domain}" for _ in range(max(0, n_emails-len(EMAILS)))]
        self._rt()["emails"] += emails

        # Subdomains / IPs
        n_subs = random.randint(5, 14)
        subs   = random.sample(SUBDOMAINS, min(n_subs, len(SUBDOMAINS)))
        hosts  = [(f"{s}.{domain}", fake_ip()) for s in subs]
        self._rt()["subdomains"] += [h[0] for h in hosts]

        # Print results
        print(ok(f"  [*] Emails found: {len(emails)}"))
        for e in emails:
            print(f"      {cyan(e)}")

        print(ok(f"\n  [*] Hosts found: {len(hosts)}"))
        for hostname, ip in hosts:
            print(f"      {cyan(hostname):<40} {dim(ip)}")

        print(f"\n  [*] IP range discovered: {fake_ip('/24')}")
        print(dim(f"\n  Tip: pipe emails to hydra for credential stuffing"))
        print(dim(f"  Tip: feed subdomains to nmap for port scanning"))

        self._rt()["target"] = domain
        self._rt()["phase"]  = "recon"
        self._rt()["report_items"].append(f"RECON: {len(emails)} emails, {len(hosts)} hosts found for {domain}")
        self._xp(18, "theHarvester recon")

        if self.s.grant_achievement("osint_operator", "Ran OSINT recon with theHarvester"):
            print(f"  {BYELLOW}{B}🏆 Achievement: OSINT Operator!{R}")

    def amass(self, args):
        """Subdomain enumeration."""
        sub = args[0] if args else "enum"
        domain = None
        passive = "-passive" in args
        for i, a in enumerate(args):
            if a == "-d" and i+1 < len(args): domain = args[i+1]

        if not domain:
            print(warn("  Usage: amass enum [-passive] -d <domain>"))
            print(dim("  Modes: enum  intel  db  track  viz"))
            return

        self._phase_banner("recon")
        print(f"  {BRED}Amass{R} v3.23.3 — subdomain enumeration")
        print(f"  Domain : {cyan(domain)}")
        print(f"  Mode   : {'passive (no active DNS)' if passive else 'active'}")
        print()

        spinner("Enumerating subdomains via DNS brute force + cert transparency", 2.2)

        found = random.sample(SUBDOMAINS, random.randint(6, len(SUBDOMAINS)))
        full  = [(f"{s}.{domain}", fake_ip()) for s in found]
        self._rt()["subdomains"] += [h[0] for h in full]

        for hostname, ip in full:
            print(f"  {cyan(hostname):<42} {dim(ip)}")

        print(f"\n  {ok(str(len(full)))} subdomains discovered")
        print(dim(f"  ASN info, CIDR ranges, and certificate data collected"))
        self._rt()["phase"] = "recon"
        self._xp(15, "amass enumeration")

    def dnsenum(self, args):
        """DNS enumeration."""
        domain = args[0] if args else "target.local"
        print(f"\n  {BRED}dnsenum{R} 1.3.1")
        print(f"  Host: {cyan(domain)}\n")
        spinner("DNS enumeration", 1.0)

        records = [
            ("A",   domain,           fake_ip()),
            ("MX",  f"mail.{domain}", fake_ip()),
            ("NS",  f"ns1.{domain}",  fake_ip()),
            ("TXT", domain,           '"v=spf1 include:_spf.google.com ~all"'),
        ]
        for rtype, name, val in records:
            print(f"  {cyan(rtype):<6} {name:<35} {dim(val)}")

        print(f"\n  Zone transfer attempt on ns1.{domain}...")
        if random.random() > 0.6:
            print(err(f"  ✗ AXFR failed — zone transfer disabled"))
        else:
            print(warn(f"  ⚠ Zone transfer SUCCEEDED! Full zone data exposed:"))
            for sub in random.sample(SUBDOMAINS, 4):
                print(f"      {sub}.{domain}  →  {fake_ip()}")
            print(warn("  This is a critical misconfiguration!"))
            self._xp(10, "zone transfer success")
        self._xp(10, "dnsenum")

    def whois(self, args):
        domain = args[0] if args else "target.com"
        print(f"\n  {info('whois')} {domain}\n")
        print(f"  Domain Name: {domain.upper()}")
        print(f"  Registry:    ICANN")
        print(f"  Registrar:   GoDaddy LLC")
        print(f"  Created:     2019-03-{random.randint(1,28):02d}")
        print(f"  Updated:     2025-03-{random.randint(1,28):02d}")
        print(f"  Expires:     2027-03-{random.randint(1,28):02d}")
        print(f"  Name Server: ns1.{domain}  ns2.{domain}")
        print(f"  Registrant:  REDACTED FOR PRIVACY")
        print(dim("\n  Tip: Registrar info → use for phishing pretexts"))
        self.s.add_xp(5, "whois")

    # ═══════════════════════════════════════════════════════════════════════════
    # WEAPONIZE
    # ═══════════════════════════════════════════════════════════════════════════

    def searchsploit(self, args):
        """Search exploit-db locally."""
        if not args:
            print(warn("  Usage: searchsploit <search terms>"))
            print(dim("  Options: --id  -m <id>  --cve <CVE-YEAR-NNNN>"))
            return

        self._phase_banner("weaponize")

        cve_search = "--cve" in args
        mirror     = "-m" in args
        query      = " ".join(a for a in args if not a.startswith("-"))

        print(f"  {BRED}SearchSploit{R} — Exploit Database")
        print(f"  Query: {cyan(query)}\n")

        # Filter by keyword
        matches = [e for e in EXPLOITS
                   if any(w.lower() in e["name"].lower() or w.lower() in e["cve"].lower()
                          for w in query.split())]
        if not matches:
            matches = random.sample(EXPLOITS, min(3, len(EXPLOITS)))

        print(f"  {'Exploit Title':<52} {'Path'}")
        print(dim("  " + "─" * 80))
        for ex in matches:
            col = SEV_COL.get(ex["severity"], "")
            name_col = f"{col}{ex['name'][:50]}{R}"
            path = f"exploits/{ex['type']}/{ex['id']}.py"
            print(f"  {name_col:<61} {dim(path)}")
            print(f"  {dim('CVE: '+ex['cve']):<61} {dim('EDB-ID: '+ex['id'])}")
            print()

        if mirror:
            chosen = matches[0]
            print(ok(f"  Copied to current directory: {chosen['id']}.py"))

        self._rt()["phase"] = "weaponize"
        self._rt()["report_items"].append(f"WEAPONIZE: Found {len(matches)} exploit(s) for '{query}'")
        self._xp(14, "searchsploit")

    def msfvenom(self, args):
        """Payload generation."""
        payload  = None
        lhost    = "100.64.1.10"
        lport    = "4444"
        fmt      = "elf"
        out      = "payload.bin"
        encoder  = None
        iters    = 1

        i = 0
        while i < len(args):
            a = args[i]
            if a == "-p" and i+1 < len(args):   payload = args[i+1]; i+=1
            elif a == "LHOST" in a:
                if "=" in a: lhost = a.split("=")[1]
            elif a == "LPORT" in a:
                if "=" in a: lport = a.split("=")[1]
            elif a == "-f" and i+1 < len(args):  fmt    = args[i+1]; i+=1
            elif a == "-o" and i+1 < len(args):  out    = args[i+1]; i+=1
            elif a == "-e" and i+1 < len(args):  encoder= args[i+1]; i+=1
            elif a == "-i" and i+1 < len(args):
                try: iters = int(args[i+1])
                except: pass
                i+=1
            else:
                # LHOST=x LPORT=y style
                if "LHOST=" in a: lhost = a.split("=")[1]
                if "LPORT=" in a: lport = a.split("=")[1]
            i += 1

        if not payload:
            print(warn("  Usage: msfvenom -p <payload> LHOST=<ip> LPORT=<port> -f <fmt> -o <file>"))
            print(dim("\n  Common payloads:"))
            for p, (ext, desc) in PAYLOAD_TYPES.items():
                print(f"    {cyan(p):<45} {dim(desc)}")
            return

        self._phase_banner("weaponize")
        pinfo = PAYLOAD_TYPES.get(payload, ("BIN", "custom payload"))
        ext, desc = pinfo

        print(f"  {BRED}msfvenom{R} — Payload Generator")
        print(f"  Payload : {cyan(payload)}")
        print(f"  LHOST   : {lhost}   LPORT: {lport}")
        print(f"  Format  : {fmt}   Output: {out}")
        if encoder:
            print(f"  Encoder : {warn(encoder)}  Iterations: {iters}")
            print(warn(f"  ⚠ Encoding does not guarantee AV evasion — use sparingly"))
        print()

        spinner("Generating payload", 1.2)

        size = random.randint(200, 900)
        print(ok(f"  Payload size: {size} bytes"))
        print(ok(f"  Final size of {fmt} file: {size + random.randint(50, 300)} bytes"))
        print(ok(f"  Saved as: {out}"))
        print()
        print(dim("  ⚠ OPSEC note: test against AV before deploying"))
        print(dim("  ⚠ Ensure your listener is running before delivery"))
        print(dim(f"  Start listener: msfconsole → use exploit/multi/handler"))

        self._rt()["phase"] = "weaponize"
        self._rt()["report_items"].append(f"WEAPONIZE: Generated {payload} payload → {out}")
        self._xp(16, "msfvenom payload")

        if self.s.grant_achievement("payload_crafter", "Generated a payload with msfvenom"):
            print(f"  {BYELLOW}{B}🏆 Achievement: Payload Crafter!{R}")

    # ═══════════════════════════════════════════════════════════════════════════
    # DELIVER / EXPLOIT
    # ═══════════════════════════════════════════════════════════════════════════

    def msfconsole(self, args):
        """Metasploit Framework console simulation."""
        self._phase_banner("exploit")
        print(f"  {BRED}{B}")
        print(r"  __  __      _                _       _ _   ")
        print(r"  |  \/  | ___| |_ __ _ ___ _ __| | ___ (_) |_ ")
        print(r"  | |\/| |/ _ \ __/ _` / __| '_ \| |/ _ \| | __|")
        print(r"  | |  | |  __/ || (_| \__ \ |_) | | (_) | | |_ ")
        print(r"  |_|  |_|\___|\__\__,_|___/ .__/|_|\___/|_|\__|")
        print(r"                           |_|                   ")
        print(f"{R}")
        print(f"  {dim('Metasploit Framework v6.3.44-dev')}")
        print(f"  {ok(str(len(EXPLOITS)))} exploits  {ok('10')} auxiliary  {ok('5')} post")
        print(f"  {dim('Type help for a list of commands')}\n")

        active_module = None
        module_opts   = {"LHOST": "100.64.1.10", "LPORT": "4444", "RHOSTS": ""}
        sessions      = self._rt()["sessions"]

        while True:
            prompt_base = f"  {BRED}msf6{R}"
            if active_module:
                short = active_module.split("/")[-1]
                prompt_base += f" {cyan('exploit')}({BYELLOW}{short}{R})"
            try:
                cmd_in = input(f"{prompt_base} > ").strip()
            except (EOFError, KeyboardInterrupt):
                print(dim("\n  Leaving msfconsole...")); break

            if not cmd_in: continue
            parts = cmd_in.split()
            c = parts[0].lower()

            if c in ("exit","quit","q"):
                print(dim("  Leaving msfconsole...")); break

            elif c == "help" or c == "?":
                print(info("\n  Core commands:"))
                cmds = [
                    ("search <term>",    "Search modules"),
                    ("use <module>",     "Select a module"),
                    ("info",             "Show module info"),
                    ("show options",     "Show required options"),
                    ("set <OPT> <val>",  "Set option value"),
                    ("setg <OPT> <val>", "Set global option"),
                    ("run / exploit",    "Run the module"),
                    ("sessions",         "List active sessions"),
                    ("sessions -i <id>", "Interact with session"),
                    ("back",             "Deselect module"),
                    ("exit",             "Leave msfconsole"),
                ]
                for cmd_s, desc in cmds:
                    print(f"    {cyan(cmd_s):<30} {dim(desc)}")
                print()

            elif c == "search":
                query = " ".join(parts[1:])
                print(f"\n  Matching modules for '{query}':\n")
                print(f"  {'#':<4} {'Name':<50} {'Disclosure':<12} {'Rank'}")
                print(dim("  " + "─" * 80))
                hits = [m for m in MSF_MODULES if any(w in m for w in query.lower().split())]
                if not hits: hits = MSF_MODULES[:4]
                for i, m in enumerate(hits[:6]):
                    rank = random.choice(["excellent","great","good","normal"])
                    rank_col = ok(rank) if rank == "excellent" else (warn(rank) if rank == "great" else dim(rank))
                    print(f"  {i:<4} {cyan(m):<50} {'2024-01-01':<12} {rank_col}")
                print()

            elif c == "use":
                if len(parts) < 2:
                    print(warn("  use <module path>")); continue
                mod = parts[1]
                # Match partial
                full = next((m for m in MSF_MODULES if parts[1] in m), parts[1])
                active_module = full
                print(ok(f"  [{active_module}] selected"))
                print(dim(f"  Run 'show options' to see required settings"))

            elif c == "info":
                if not active_module:
                    print(warn("  No module selected")); continue
                ex = next((e for e in EXPLOITS if e["name"].lower() in active_module.lower()), None)
                print(f"\n  Module: {cyan(active_module)}")
                if ex:
                    print(f"  CVE   : {warn(ex['cve'])}")
                    print(f"  Rank  : {ok('excellent')}")
                    print(f"  Severity: {sev(ex['severity'])}")
                print(f"  LHOST  : callback IP for reverse shell")
                print(f"  RHOST  : target IP/hostname")
                print()

            elif c == "show":
                sub2 = parts[1] if len(parts) > 1 else ""
                if sub2 == "options":
                    print(f"\n  {'Name':<14} {'Current':<20} {'Required':<10} Description")
                    print(dim("  " + "─" * 65))
                    opts = [
                        ("RHOSTS",  module_opts.get("RHOSTS",""),  "yes", "Target address(es)"),
                        ("LHOST",   module_opts.get("LHOST",""),   "yes", "Local callback IP"),
                        ("LPORT",   module_opts.get("LPORT",""),   "yes", "Local callback port"),
                        ("PAYLOAD", "linux/x64/meterpreter/reverse_tcp","yes","Payload to use"),
                    ]
                    for name, val, req, desc in opts:
                        req_col = ok(req) if req == "yes" else dim(req)
                        val_col = warn(val) if not val else cyan(val)
                        print(f"  {name:<14} {val_col:<29} {req_col:<10} {dim(desc)}")
                    print()
                elif sub2 in ("payloads","exploits","post","auxiliary"):
                    for m in random.sample(MSF_MODULES, min(5, len(MSF_MODULES))):
                        if sub2.rstrip("s") in m or sub2 == "payloads":
                            print(f"  {dim(m)}")

            elif c in ("set","setg"):
                if len(parts) < 3:
                    print(warn("  set <OPTION> <value>")); continue
                key, val = parts[1].upper(), parts[2]
                module_opts[key] = val
                scope = "global" if c == "setg" else "module"
                print(ok(f"  {key} => {val}  ({scope})"))

            elif c in ("run","exploit","check"):
                if not active_module:
                    print(warn("  No module selected. Use: use <module>")); continue
                if not module_opts.get("RHOSTS") and c != "check":
                    print(warn("  RHOSTS not set. Use: set RHOSTS <target-ip>")); continue

                rhost = module_opts.get("RHOSTS","10.0.0.1")
                lhost = module_opts.get("LHOST","100.64.1.10")
                lport = module_opts.get("LPORT","4444")

                print(f"\n  {BRED}[*]{R} Started reverse TCP handler on {lhost}:{lport}")
                self._rt()["listener_up"] = True
                spinner(f"Running {active_module.split('/')[-1]} against {rhost}", 1.8)

                success = random.random() > 0.35
                if success:
                    sid = str(len(sessions) + 1)
                    sessions[sid] = {"host": rhost, "type": "meterpreter", "module": active_module}
                    self._rt()["exploited"]  = True
                    self._rt()["shell_type"] = "meterpreter"
                    self._rt()["phase"]      = "post"
                    self._rt()["report_items"].append(f"EXPLOIT: Gained {sessions[sid]['type']} session on {rhost} via {active_module}")
                    print(ok(f"\n  [+] {rhost} - Meterpreter session {sid} opened ({lhost}:{lport})"))
                    print(dim(f"  Use 'sessions -i {sid}' to interact"))
                    self._xp(40, "msfconsole exploit")
                    if self.s.grant_achievement("shell_obtained", "Gained a Meterpreter session"):
                        print(f"  {BYELLOW}{B}🏆 Achievement: Shell Obtained!{R}")
                else:
                    print(warn(f"\n  [-] {rhost} - Exploit failed (target may be patched)"))
                    print(dim("  Try: check (verify target is vulnerable)"))
                    print(dim("  Or:  use a different module"))
                print()

            elif c == "sessions":
                interact = "-i" in parts
                if interact and len(parts) >= 3:
                    sid = parts[parts.index("-i")+1]
                    self._meterpreter_shell(sid, sessions, module_opts)
                else:
                    if not sessions:
                        print(dim("  No active sessions.")); continue
                    print(f"\n  {'Id':<4} {'Type':<14} {'Host':<20} Via")
                    print(dim("  " + "─" * 55))
                    for sid, info in sessions.items():
                        print(f"  {sid:<4} {info['type']:<14} {info['host']:<20} {dim(info['module'].split('/')[-1])}")
                    print()

            elif c == "back":
                active_module = None
                print(dim("  Module deselected."))

            elif c == "db_nmap":
                target = parts[1] if len(parts) > 1 else module_opts.get("RHOSTS","10.0.0.1")
                print(info(f"  Running nmap against {target} and storing results..."))
                spinner("db_nmap scan", 1.2)
                result = self.w.generate_scan(target)
                print(ok(f"  {len(result['ports'])} ports added to workspace"))

            elif c == "workspace":
                print(dim("  Workspace: default"))

            else:
                print(warn(f"  Unknown command: {c}. Type 'help' for options."))

    def _meterpreter_shell(self, sid, sessions, opts):
        """Interactive Meterpreter-like shell."""
        info_s = sessions.get(sid, {})
        rhost  = info_s.get("host", "target")
        print(ok(f"\n  [*] Starting interaction with {sid}...\n"))
        print(f"  meterpreter > {dim('(type help for commands, exit to background)')}\n")

        while True:
            try:
                cmd_in = input(f"  {BRED}meterpreter{R} > ").strip()
            except (EOFError, KeyboardInterrupt):
                print(); break

            if not cmd_in: continue
            parts2 = cmd_in.split()
            c2 = parts2[0].lower()

            if c2 in ("exit","background","bg","quit"):
                print(ok(f"  Session {sid} backgrounded.")); break

            elif c2 == "help":
                mets = [
                    ("sysinfo",        "Target OS/hostname info"),
                    ("getuid",         "Current user ID"),
                    ("getpid",         "Current process ID"),
                    ("shell",          "Drop to system shell"),
                    ("upload <f>",     "Upload file to target"),
                    ("download <f>",   "Download file from target"),
                    ("ls / pwd / cd",  "File system navigation"),
                    ("hashdump",       "Dump password hashes (requires root)"),
                    ("run post/<mod>", "Run post-exploitation module"),
                    ("migrate <pid>",  "Migrate to another process"),
                    ("getsystem",      "Attempt privilege escalation"),
                    ("screenshot",     "Capture desktop screenshot"),
                    ("keyscan_start",  "Start keylogger"),
                    ("portfwd",        "Port forwarding through session"),
                    ("route",          "Manage routing through session"),
                    ("background/exit","Return to msfconsole"),
                ]
                for cmd_s, desc in mets:
                    print(f"    {cyan(cmd_s):<28} {dim(desc)}")
                print()

            elif c2 == "sysinfo":
                print(f"  Computer     : {rhost}")
                print(f"  OS           : {random.choice(['Ubuntu 22.04 LTS','Debian 12','CentOS 7','Windows Server 2019'])}")
                print(f"  Architecture : x64")
                print(f"  Meterpreter  : x64/linux")

            elif c2 == "getuid":
                uid = "root (uid=0)" if self._rt().get("privesc_done") else f"www-data (uid=33)"
                print(f"  Server username: {warn(uid) if 'root' in uid else dim(uid)}")

            elif c2 == "getsystem":
                spinner("Attempting privilege escalation techniques", 1.5)
                success = random.random() > 0.4
                if success:
                    self._rt()["privesc_done"] = True
                    self._rt()["report_items"].append(f"POST: getsystem succeeded on {rhost}")
                    print(ok("  ...got system via technique 1 (Named Pipe Impersonation)"))
                    self._xp(30, "getsystem privesc")
                    if self.s.grant_achievement("root_obtained", "Achieved root via getsystem"):
                        print(f"  {BYELLOW}{B}🏆 Achievement: Root Obtained!{R}")
                else:
                    print(warn("  ...could not get system."))
                    print(dim("  Try: run post/multi/recon/local_exploit_suggester"))

            elif c2 == "hashdump":
                if not self._rt().get("privesc_done"):
                    print(err("  [-] priv.hashdump: Operation failed: 1 (ERROR)")); continue
                print(ok("  Dumping password hashes:\n"))
                users = ["root","daemon","www-data","ubuntu","mysql","postgres"]
                for u in users:
                    h = hashlib.md5((u+"pass").encode()).hexdigest()
                    print(f"  {cyan(u)}::{h}")
                self._rt()["loot"].append("/etc/shadow (hashdump)")
                self._rt()["report_items"].append(f"POST: Dumped hashes via hashdump on {rhost}")
                self._xp(25, "hashdump")

            elif c2 == "download":
                f = parts2[1] if len(parts2) > 1 else "/etc/passwd"
                spinner(f"Downloading {f}", 0.6)
                self._rt()["loot"].append(f)
                self._rt()["report_items"].append(f"POST: Downloaded {f} from {rhost}")
                print(ok(f"  {f} → ./loot/"))
                self._xp(10, "meterpreter download")

            elif c2 == "upload":
                f = parts2[1] if len(parts2) > 1 else "payload.sh"
                spinner(f"Uploading {f}", 0.5)
                print(ok(f"  {f} → /tmp/{f}"))

            elif c2 in ("run","execute"):
                mod = parts2[1] if len(parts2) > 1 else ""
                if "local_exploit_suggester" in mod:
                    print(info("\n  Local exploit suggestions:\n"))
                    for finding in random.sample(PRIVESC_FINDINGS, 4):
                        sev_str, desc = finding
                        print(f"    {sev(sev_str)} {desc}")
                    print()
                elif "hashdump" in mod:
                    print(ok("  Attempting hashdump via post module..."))
                elif "shell_to_meterpreter" in mod:
                    print(ok("  Upgrading shell to Meterpreter..."))
                    spinner("Upgrading", 0.8)
                    print(ok("  Meterpreter session upgraded."))
                else:
                    spinner(f"Running {mod}", 0.8)
                    print(ok(f"  Module completed."))

            elif c2 == "migrate":
                pid = parts2[1] if len(parts2) > 1 else "1234"
                spinner(f"Migrating to PID {pid}", 0.7)
                print(ok(f"  Successfully migrated to process {pid}"))

            elif c2 == "screenshot":
                print(ok("  Screenshot saved: screenshot.png"))
                print(dim("  (simulated — no actual screen captured)"))

            elif c2 == "keyscan_start":
                print(ok("  Keylogger started. Run keyscan_dump to view."))
            elif c2 == "keyscan_dump":
                print(dim("  Captured: 'password123' 'admin@corp.com' 'ssh-key-phrase'"))
            elif c2 == "keyscan_stop":
                print(ok("  Keylogger stopped."))

            elif c2 in ("ls","pwd","cd","cat","ps","whoami","id","ifconfig","ipconfig"):
                self._met_sys_cmd(c2, parts2[1:], rhost)

            elif c2 == "portfwd":
                print(info("  Port forward: local → remote tunnel added"))
                print(dim("  Use: portfwd add -l 8080 -p 80 -r 10.0.0.2"))

            elif c2 == "route":
                print(info("  Active routing table through session:"))
                print(dim(f"  Subnet: 10.0.0.0/24  Gateway: session {sid}"))

            else:
                print(dim(f"  meterpreter: unknown command '{c2}'"))

    def _met_sys_cmd(self, cmd, args, host):
        if cmd == "pwd":   print(f"  /var/www/html")
        elif cmd == "ls":  print("  index.php  config.php  uploads/  .env  backup.sql")
        elif cmd == "id":  print(f"  uid=33(www-data) gid=33(www-data) groups=33(www-data)")
        elif cmd == "whoami": print("  www-data")
        elif cmd == "ps":
            procs = [("1","root","systemd"),("432","root","sshd"),
                     ("1234","www-data","apache2"),("5678","mysql","mysqld")]
            for pid, user, name in procs:
                print(f"  {pid:>6}  {user:<12}  {name}")
        elif cmd in ("ifconfig","ipconfig"):
            print(f"  eth0  {fake_ip()}  {fake_mac()}")

    # ═══════════════════════════════════════════════════════════════════════════
    # POST EXPLOITATION
    # ═══════════════════════════════════════════════════════════════════════════

    def linpeas(self, args):
        """Linux Privilege Escalation Auditing Script."""
        self._phase_banner("post")
        print(f"  {BRED}{B}linPEAS{R} — Linux Privilege Escalation Awesome Script")
        print(dim("  Running all checks — this takes a moment...\n"))
        spinner("Gathering system information", 1.0)

        categories = [
            ("System Information",      ["OS: Ubuntu 22.04.3 LTS", f"Kernel: {random.choice(['5.15.0-91','6.1.0-18','5.4.0-169'])}"]),
            ("Users & Groups",          [f"Current user: www-data (uid=33)", "sudo -l: NOPASSWD entries found!"]),
            ("SUID/SGID Files",         ["/usr/bin/nmap", "/usr/bin/python3.10", "/usr/bin/vim.basic"]),
            ("Cron Jobs",               ["*/5 * * * * root /opt/scripts/backup.sh", "Backup script world-writable!"]),
            ("Network Info",            [f"Listening: 0.0.0.0:3306 (MySQL open to all!)", "Tailscale0: 100.64.1.x"]),
            ("Interesting Files",       ["/var/www/html/.env (readable!)", "/opt/app/config.yaml"]),
            ("Environment",             ["DB_PASSWORD=hunter2 in environment!", "PATH contains /tmp (hijackable)"]),
            ("Docker",                  ["Current user in 'docker' group — root-equivalent!"]),
        ]

        all_findings = []
        for cat, items in categories:
            print(f"\n  {BRED}══ {cat} ══{R}")
            for item in items:
                is_vuln = any(w in item for w in ["NOPASSWD","world-writable","readable","open to","PASSWORD=","hijackable","docker group"])
                if is_vuln:
                    print(f"  {BYELLOW}╔══╡ {warn(item)}")
                    print(f"  {BYELLOW}╚══╡{R} {dim('Potential privilege escalation vector')}")
                    all_findings.append(item)
                else:
                    print(f"    {dim(item)}")
            pause(0.08)

        print(f"\n  {BRED}═══════════════ SUMMARY ═══════════════{R}")
        print(f"  Interesting findings: {BYELLOW}{len(all_findings)}{R}")
        for f in all_findings:
            print(f"    {warn('→')} {f[:65]}")

        self._rt()["phase"] = "post"
        self._rt()["report_items"].append(f"POST: linPEAS found {len(all_findings)} privesc vectors")
        self._xp(25, "linPEAS run")

        if self.s.grant_achievement("privesc_hunter", "Ran linPEAS and found privesc vectors"):
            print(f"\n  {BYELLOW}{B}🏆 Achievement: PrivEsc Hunter!{R}")

    def pspy(self, args):
        """Process spy — monitors processes without root."""
        self._phase_banner("post")
        duration = 10
        for i, a in enumerate(args):
            if a in ("-i","--interval") and i+1 < len(args):
                try: duration = int(args[i+1])
                except: pass

        print(f"  {BRED}pspy{R} v1.2.1 — process monitor (no root required)")
        print(dim("  Watching for new processes. Ctrl+C to stop.\n"))

        events = [
            ("root",    "/usr/sbin/cron -f"),
            ("root",    "/bin/sh /opt/backup.sh"),
            ("www-data","/usr/bin/php /var/www/html/cron.php"),
            ("root",    "mysqldump -u root -pS3cr3tPass! database > /tmp/backup.sql"),
            ("root",    "/usr/bin/python3 /opt/scripts/cleanup.py"),
            ("jenkins", "git pull origin main"),
        ]

        print(f"  {'TIME':<12} {'UID':<10} {'COMMAND'}")
        print(dim("  " + "─" * 70))
        try:
            for _ in range(8):
                ts  = time.strftime("%H:%M:%S")
                ev  = random.choice(events)
                uid, cmd = ev
                is_juicy = any(w in cmd for w in ["password","passwd","secret","Pass","key","token"])
                line = f"  {dim(ts):<20} {uid:<10} {cmd}"
                if is_juicy:
                    print(warn(line) + f"  {BYELLOW}← credentials!{R}")
                    self._rt()["loot"].append(f"Credential in process: {cmd}")
                    self._rt()["report_items"].append(f"POST: pspy captured credential in process args")
                else:
                    print(line)
                pause(0.35)
        except KeyboardInterrupt:
            pass

        print(dim("\n  [pspy stopped]"))
        self._xp(18, "pspy monitoring")

    def enum4linux(self, args):
        """SMB/Windows enumeration."""
        target = args[0] if args else next(
            (a for a in args if not a.startswith("-")), fake_ip())
        full = "-a" in args

        self._phase_banner("post")
        print(f"  {BRED}enum4linux{R} v1.3.1")
        print(f"  Target: {cyan(target)}\n")
        spinner("SMB enumeration", 1.5)

        sections = [
            ("OS Info",      [f"OS: Windows Server 2019", "SMBv1: ENABLED (dangerous!)"]),
            ("Users",        ["admin", "backup_svc", "domain_admin", "testuser"]),
            ("Groups",       ["Domain Admins","Remote Desktop Users","Backup Operators"]),
            ("Shares",       [("ADMIN$","Remote Admin (hidden)"),("C$","Default share"),
                              ("backups","Readable by Everyone! ← juicy")]),
            ("Password Policy", ["Min length: 0 (no policy!)", "Lockout: disabled"]),
        ]

        for title, items in sections:
            print(f"\n  {info(title + ':')}")
            if isinstance(items[0], tuple):
                for name, desc in items:
                    flag = warn("⚠ ") if "juicy" in desc or "hidden" in desc.lower() else "  "
                    print(f"  {flag}{cyan(name):<20} {dim(desc)}")
            else:
                for item in items:
                    flag = warn("⚠ ") if any(w in item for w in ["ENABLED","Readable","0 (","disabled"]) else "  "
                    print(f"  {flag}{item}")

        self._rt()["report_items"].append(f"POST: enum4linux found SMBv1 enabled and open share on {target}")
        self._xp(18, "enum4linux")

    def crackmapexec(self, args):
        """CME — network authentication tester."""
        protocol = args[0] if args else "smb"
        target   = next((a for a in args if not a.startswith("-") and a != protocol), fake_ip())
        user_flag = next((args[i+1] for i,a in enumerate(args) if a=="-u" and i+1<len(args)), "admin")
        pass_flag = next((args[i+1] for i,a in enumerate(args) if a=="-p" and i+1<len(args)), "password")

        self._phase_banner("post")
        print(f"  {BRED}CrackMapExec{R} v5.4.0")
        print(f"  Protocol: {protocol.upper()}  Target: {cyan(target)}")
        print(f"  Credentials: {user_flag} : {warn(pass_flag)}\n")

        spinner("Authenticating", 0.8)

        success = random.random() > 0.4
        status  = ok("[+] SUCCESS") if success else err("[-] FAILURE")
        pwn3d   = ok("(Pwn3d!)") if success and random.random() > 0.5 else ""

        print(f"  {protocol.upper():<6} {target:<20} {dim('445')} {dim('Windows Server 2019 x64')} {status} {pwn3d}")

        if success:
            self._rt()["exploited"] = True
            self._rt()["report_items"].append(f"POST: CME authenticated to {target} as {user_flag}")
            self._xp(20, "crackmapexec success")
            if pwn3d:
                print(warn(f"\n  ⚠ Admin access confirmed — proceed to hashdump"))

    def responder(self, args):
        """LLMNR/NBT-NS/MDNS poisoning."""
        iface = next((a for a in args if not a.startswith("-")), "eth0")

        self._phase_banner("post")
        print(f"  {BRED}Responder{R} v3.1.4.0")
        print(f"  Interface: {iface}")
        print(warn("  ⚠ LLMNR/NBT-NS/MDNS poisoning active — capture NTLMv2 hashes\n"))
        print(dim("  Listening for broadcast name resolution requests..."))
        print(dim("  Ctrl+C to stop (press Enter to simulate capture)\n"))

        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass

        victim_ip   = fake_ip("192.168.1")
        victim_user = random.choice(["CORP\\jsmith","CORP\\admin","CORP\\helpdesk"])
        ntlm_hash   = ":".join([
            f"{random.randint(0,65535):04x}",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" + "aaa",
            f"{random.randint(10**15,10**16-1):x}",
        ])

        print(warn(f"  [+] NTLMv2 Hash captured!"))
        print(f"  {dim('Client  :')} {victim_ip}")
        print(f"  {dim('Username:')} {warn(victim_user)}")
        print(f"  {dim('Hash    :')} {dim(ntlm_hash[:60]+'...')}")
        print(f"\n  {ok('Saved to: Responder/logs/NTLMv2.txt')}")
        print(dim("  Crack with: hashcat -m 5600 NTLMv2.txt rockyou.txt"))

        self._rt()["loot"].append(f"NTLMv2 hash: {victim_user}")
        self._rt()["report_items"].append(f"POST: Captured NTLMv2 hash for {victim_user} via Responder")
        self._xp(22, "responder hash capture")
        if self.s.grant_achievement("hash_catcher", "Captured an NTLMv2 hash with Responder"):
            print(f"  {BYELLOW}{B}🏆 Achievement: Hash Catcher!{R}")

    def sqlmap(self, args):
        """SQL injection scanner and exploiter."""
        url = next((args[i+1] for i,a in enumerate(args) if a in ("-u","--url") and i+1<len(args)),
                   "http://target.local/login.php?id=1")
        dbs      = "--dbs" in args
        dump     = "--dump" in args
        level    = next((args[i+1] for i,a in enumerate(args) if a=="--level" and i+1<len(args)), "1")
        batch    = "--batch" in args

        self._phase_banner("exploit")
        print(f"  {BRED}sqlmap{R} v1.8.0")
        print(f"  URL  : {cyan(url)}")
        print(f"  Level: {level}  Batch: {batch}")
        print()
        spinner("Testing injection points", 1.8)

        param = url.split("?")[1].split("=")[0] if "?" in url else "id"
        injectable = random.random() > 0.3

        if not injectable:
            print(warn(f"  [!] Parameter '{param}' does not appear to be injectable"))
            print(dim("  Try: --level 3 --risk 2  or different parameters"))
            return

        print(ok(f"  [+] Parameter '{param}' is injectable!"))
        print(f"  {dim('Type:')} {random.choice(['boolean-based blind','time-based blind','UNION query'])}")
        print(f"  {dim('DBMS:')} {random.choice(['MySQL 8.0','PostgreSQL 14','MSSQL 2019'])}")
        print()

        if dbs:
            databases = ["information_schema","mysql","performance_schema","app_db","users","backup"]
            print(ok("  Available databases:"))
            for db in databases:
                print(f"    [*] {cyan(db)}")

        if dump:
            print(ok("\n  Dumping 'users' table:"))
            print(f"  {'id':<4} {'username':<15} {'password_hash':<35} {'email'}")
            print(dim("  " + "─" * 70))
            for i in range(4):
                u    = random.choice(["admin","user","backup","test"])
                h    = hashlib.md5(f"{u}pass".encode()).hexdigest()
                mail = f"{u}@target.local"
                print(f"  {i+1:<4} {u:<15} {warn(h):<35} {dim(mail)}")
            self._rt()["loot"].append("Database dump: users table")
            self._rt()["report_items"].append(f"EXPLOIT: SQLmap dumped users table from {url}")
            self._xp(30, "sqlmap dump")
        else:
            self._xp(18, "sqlmap injection found")

        if self.s.grant_achievement("sql_slinger", "Found SQL injection with sqlmap"):
            print(f"\n  {BYELLOW}{B}🏆 Achievement: SQL Slinger!{R}")

    # ═══════════════════════════════════════════════════════════════════════════
    # REPORT
    # ═══════════════════════════════════════════════════════════════════════════

    def report(self, args):
        """Generate engagement report."""
        rt     = self._rt()
        output = args[0] if args else "report.md"
        fmt    = "markdown"
        if "--pdf" in args: fmt = "pdf"
        if "--html" in args: fmt = "html"

        self._phase_banner("report")
        print(f"  {BRED}Engagement Report Generator{R}")
        print(f"  Format: {fmt}  Output: {output}")
        print()
        spinner("Compiling findings", 1.0)

        scope     = rt.get("target","target.local")
        items     = rt.get("report_items", [])
        loot      = rt.get("loot", [])
        exploited = rt.get("exploited", False)

        risk = "CRITICAL" if exploited and rt.get("privesc_done") else \
               "HIGH" if exploited else "MEDIUM"
        risk_col = sev(risk)

        print(f"""
  {'━'*60}
  PENETRATION TEST REPORT
  {'━'*60}
  Target     : {scope}
  Date       : {time.strftime('%Y-%m-%d')}
  Assessor   : {self.s.get('username','analyst')}
  Risk Rating: {risk_col}
  {'━'*60}

  EXECUTIVE SUMMARY
  {'─'*40}
  Testing revealed {len(items)} significant finding(s).
  {'Root access was obtained.' if rt.get('privesc_done') else 'User-level access was obtained.' if exploited else 'No shells obtained (recon phase only).'}
  {len(loot)} piece(s) of sensitive data were accessed.

  FINDINGS TIMELINE
  {'─'*40}""")

        for i, item in enumerate(items, 1):
            phase = item.split(":")[0]
            desc  = item.split(":",1)[1].strip() if ":" in item else item
            col   = BRED if "EXPLOIT" in phase else (BYELLOW if "POST" in phase else BCYAN)
            print(f"  {i:>3}. {col}{phase}{R}  {desc}")

        if loot:
            print(f"\n  LOOT / EVIDENCE\n  {'─'*40}")
            for l in loot:
                print(f"  {warn('→')} {l}")

        print(f"""
  RECOMMENDATIONS
  {'─'*40}
  1. Patch all identified CVEs immediately
  2. Enforce strong password policy and MFA
  3. Disable SMBv1 and legacy protocols
  4. Segment network — limit lateral movement paths
  5. Enable centralised logging (SIEM)
  6. Conduct regular security awareness training
  {'━'*60}
  Report saved: {ok(output)}""")

        self._xp(35, "engagement report")
        rt["phase"] = "report"
        if self.s.grant_achievement("report_writer","Generated a full pentest report"):
            print(f"\n  {BYELLOW}{B}🏆 Achievement: Report Writer!{R}")

    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS / HELP
    # ═══════════════════════════════════════════════════════════════════════════

    def kill_chain_status(self):
        """Show current kill chain progress."""
        rt     = self._rt()
        phases = ["recon","weaponize","deliver","exploit","post","report"]
        colors = {
            "recon":BCYAN,"weaponize":BYELLOW,"deliver":BMAGENTA,
            "exploit":BRED,"post":f"{BG_RED}{BYELLOW}","report":BGREEN,
        }
        current = rt.get("phase","recon")
        print()
        print(f"  {BRED}{B}RED TEAM KILL CHAIN{R}")
        print(dim("  " + "─" * 50))
        for ph in phases:
            done    = phases.index(ph) < phases.index(current)
            active  = ph == current
            col     = colors.get(ph, "")
            icon    = ok("✓") if done else (f"{BRED}{B}▶{R}" if active else dim("○"))
            name    = f"{col}{B}{ph.upper()}{R}" if active else (ok(ph.upper()) if done else dim(ph.upper()))
            print(f"    {icon}  {name}")
        print()
        print(f"  Target    : {cyan(rt.get('target','(not set)'))}")
        print(f"  Exploited : {ok('yes') if rt['exploited'] else dim('no')}")
        print(f"  Root      : {ok('yes') if rt.get('privesc_done') else dim('no')}")
        print(f"  Loot      : {BYELLOW}{len(rt['loot'])}{R} item(s)")
        print(f"  Sessions  : {BYELLOW}{len(rt['sessions'])}{R} active")
        print()

    def help(self):
        lines = [
            f"  {bold('// RECON')}",
            f"  {cyan('theHarvester -d <domain> -b all')}   OSINT emails + subdomains",
            f"  {cyan('amass enum -d <domain>')}            subdomain enumeration",
            f"  {cyan('dnsenum <domain>')}                  DNS records + zone transfer",
            f"  {cyan('whois <domain>')}                    registrar info",
            f"  {cyan('nmap -sV -O <target>')}              (from cybersec module)",
            "",
            f"  {bold('// WEAPONIZE')}",
            f"  {cyan('searchsploit <service version>')}    find exploits",
            f"  {cyan('msfvenom -p <payload> LHOST=<ip> LPORT=<port> -f elf -o shell')}",
            "",
            f"  {bold('// EXPLOIT')}",
            f"  {cyan('msfconsole')}                        Metasploit Framework console",
            f"    {dim('search / use / set / show options / run')}",
            f"    {dim('sessions / sessions -i <id>')}",
            f"  {cyan('sqlmap -u <url> --dbs --dump')}      SQL injection",
            "",
            f"  {bold('// POST EXPLOITATION')}",
            f"  {cyan('linpeas')}                           Linux privesc enumeration",
            f"  {cyan('pspy')}                              Process monitor (no root needed)",
            f"  {cyan('enum4linux -a <target>')}            SMB/Windows enumeration",
            f"  {cyan('crackmapexec smb <ip> -u user -p pass')} credential testing",
            f"  {cyan('responder -I eth0')}                 LLMNR/NBT-NS poisoning",
            "",
            f"  {bold('// REPORT')}",
            f"  {cyan('report [output.md]')}                generate engagement report",
            f"  {cyan('killchain')}                         show kill chain progress",
            "",
            f"  {dim('⚠ All tools are simulated — educational use only')}",
            f"  {dim('⚠ Only test systems you own or have written permission to test')}",
        ]
        box("Red Team Module — Reference", lines, border_color=BRED, width=74)
