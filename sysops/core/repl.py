"""
core/repl.py — SYSOPS Main Game REPL
Uses v3 UI engine: help_box, xp_panel, gradient rules, theme/font live switching.
"""

import shlex, time, random, os
from core.ui import *
from core.save import LEVEL_TITLES, level_for_xp, XP_PER_LEVEL, DIFF_NAMES

# Command vocabulary for tab-completion.
COMMANDS = sorted({
    "help", "save", "xp", "stats", "status", "missions", "mission", "challenge",
    "abandon", "achievements", "theme", "font", "speed", "clear", "history", "quit", "exit",
    "tailscale", "ssh", "ssh-keygen", "ssh-copy-id", "rsync", "ping",
    "docker", "docker-compose", "compose", "nginx",
    "netstat", "ss", "ip", "ifconfig", "traceroute", "dig", "nslookup", "curl",
    "wget", "arp", "nload", "iftop", "route",
    "nmap", "scan", "tshark", "wireshark", "tcpdump", "gobuster", "dirb", "nikto",
    "hydra", "hashcat", "john", "nc", "netcat", "openssl", "ufw",
    "fail2ban-client", "lynis", "shodan", "git",
    "theharvester", "amass", "dnsenum", "whois", "searchsploit", "msfvenom",
    "msfconsole", "linpeas", "pspy", "enum4linux", "crackmapexec", "responder",
    "sqlmap", "report", "killchain",
    "terraform", "tf", "diagram",
    "journalctl", "grep", "siem", "alerts", "ioc", "incident", "last", "who",
    "ls", "cd", "pwd", "whoami", "hostname", "df", "free", "uname", "cat",
    "mkdir", "touch", "rm", "cp", "mv", "top", "htop", "ps", "man", "which",
    "echo", "env", "date", "uptime", "sudo",
})

HELP_TOPICS = sorted({
    "rsync", "docker", "compose", "nginx", "nmap", "tailscale", "ssh",
    "networking", "cybersec", "combo", "git", "redteam",
    "architecture", "terraform", "diagram",
    "defense", "soc", "blueteam", "siem", "incident",
})


class GameREPL:
    def __init__(self, world, save, scenario_engine):
        self.w  = world
        self.s  = save
        self.sc = scenario_engine

        # Apply saved theme/font/speed on startup
        saved_theme = self.s.get("color_theme", "cyberpunk")
        saved_font  = self.s.get("banner_font",  "block")
        saved_speed = self.s.get("anim_speed",   "cinematic")
        set_theme(saved_theme)
        set_font(saved_font)
        set_speed(saved_speed)

        from modules.transfer   import TransferModule
        from modules.containers import ContainerModule
        from modules.networking import NetworkingModule
        from modules.cybersec   import CyberSecModule
        from modules.git        import GitModule
        from modules.redteam    import RedTeamModule
        from modules.architecture import ArchitectureModule
        from modules.defense    import DefenseModule

        self.transfer     = TransferModule(world, save)
        self.containers   = ContainerModule(world, save)
        self.networking   = NetworkingModule(world, save)
        self.cybersec     = CyberSecModule(world, save)
        self.git_mod      = GitModule(world, save)
        self.redteam      = RedTeamModule(world, save)
        self.architecture = ArchitectureModule(world, save)
        self.defense      = DefenseModule(world, save)

        self._session_cmds    = 0
        self._challenge_timer = 0
        self._readline = None
        self._histfile = None
        self._completions = []      # cached matches for the active Tab cycle
        self._mission_ids = None    # memoized sorted mission-id list (static)

    # ── Readline: arrow-key history + tab completion ──────────────────────────

    def _setup_readline(self):
        try:
            import readline
        except ImportError:
            return   # not available on this platform — game still works
        self._readline = readline
        self._histfile = os.path.expanduser("~/.sysops/history")
        try:
            readline.read_history_file(self._histfile)
        except (FileNotFoundError, OSError):
            pass
        readline.set_history_length(1000)
        readline.set_completer(self._completer)
        readline.set_completer_delims(" \t\n")
        if "libedit" in (readline.__doc__ or ""):
            readline.parse_and_bind("bind ^I rl_complete")   # macOS libedit
        else:
            readline.parse_and_bind("tab: complete")

    def _save_history(self):
        if self._readline and self._histfile:
            try:
                self._readline.write_history_file(self._histfile)
            except OSError:
                pass

    def _completer(self, text, state):
        # readline invokes this repeatedly (state 0, 1, 2, …) to pull matches one
        # at a time for a single Tab press. Build the candidate list once, on the
        # first call of the cycle, then just index into it — instead of rebuilding,
        # re-importing, re-scanning the filesystem, and re-sorting on every call.
        if state == 0:
            self._completions = self._compute_completions(text)
        try:
            return self._completions[state]
        except IndexError:
            return None

    def _compute_completions(self, text):
        rl   = self._readline
        head = rl.get_line_buffer()[:rl.get_begidx()].split()
        if not head:
            options = [c for c in COMMANDS if c.startswith(text)]
        else:
            cmd = head[0].lower()
            if cmd in ("mission", "missions"):
                options = [m for m in self._mission_id_list() if m.startswith(text)]
            elif cmd in ("help", "man"):
                options = [t for t in HELP_TOPICS if t.startswith(text)]
            elif cmd in ("cd", "ls", "cat", "rm", "cp", "mv", "less", "more"):
                options = [p for p in self._path_options() if p.startswith(text)]
            else:
                options = [c for c in COMMANDS if c.startswith(text)]
        return sorted(set(options))

    def _mission_id_list(self):
        """Sorted mission IDs for tab-completion (memoized — SCENARIOS is static)."""
        if self._mission_ids is None:
            from scenarios.missions import SCENARIOS
            self._mission_ids = sorted(sc["id"] for sc in SCENARIOS)
        return self._mission_ids

    def _path_options(self):
        """Child names under the current directory (dirs get a trailing /)."""
        kids = self.w.children(self.w.cwd)
        return [name + "/" if is_dir else name for name, is_dir in kids.items()]

    # ── Prompt ────────────────────────────────────────────────────────────────

    def _prompt(self):
        th    = get_theme()
        pu    = th.get("prompt_user", BGREEN)
        ph    = th.get("prompt_host", BCYAN)
        u     = self.s.get("username", "user")
        h     = self.s.get("hostname", "host")
        style = self.s.get("prompt_style", "user@host")
        cp    = self.s.get("prompt_custom", "")

        if style == "user@host":
            core = f"{pu}{u}{R}{DIM}@{R}{ph}{h}{R}"
        elif style == "host@user":
            core = f"{ph}{h}{R}{DIM}@{R}{pu}{u}{R}"
        elif style == "custom" and cp:
            core = f"{th['accent']}{cp}{R}"
        else:
            core = f"{pu}{u}{R}{DIM}@{R}{ph}{h}{R}"

        return f"{core}{DIM}:{self.w.cwd}${R} "

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        self._setup_readline()
        self._welcome()
        while True:
            try:
                raw = input(self._prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self._do_quit()
                break

            if not raw:
                continue

            try:
                tokens = shlex.split(raw)
            except ValueError:
                tokens = raw.split()

            cmd  = tokens[0].lower()
            args = tokens[1:]

            self.s.add_command(raw)
            self.w.cmd_log.append(raw)
            if len(self.w.cmd_log) > 100:
                self.w.cmd_log.pop(0)
            self._session_cmds   += 1
            self._challenge_timer += 1

            try:
                cont = self._dispatch(cmd, args, raw)
                if cont is False:
                    break
            except KeyboardInterrupt:
                print(dim("\n  (interrupted)"))
            except Exception as ex:
                print(err(f"  [simulator error] {ex}"))
                import traceback; traceback.print_exc()

            self.sc.check_after_command()

            if self._challenge_timer % 15 == 0 and random.random() > 0.5:
                th = get_theme()
                print(info(f"\n  💡 Ready for a drill?  {th['cmd']}challenge{R}"))

            if self._session_cmds % 10 == 0:
                self._sync_world()
                self.s.save()

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch(self, cmd, args, raw):

        # ── Meta ──────────────────────────────────────────────────────────────
        if cmd in ("quit","exit","q"):
            self._do_quit(); return False

        elif cmd == "clear" or cmd == "cls":
            clear()

        elif cmd == "help":
            self._help(args)

        elif cmd == "save":
            self._sync_world(); self.s.save()
            print(ok("  ✓ Progress saved."))

        elif cmd in ("xp","stats"):
            self._show_xp()

        elif cmd == "status":
            self.sc.status_panel()

        elif cmd in ("missions","mission") and not args:
            self.sc.list_all()

        elif cmd in ("missions","mission") and args:
            if args[0].lower() == "all":
                self.sc.list_all(show_all=True)
            else:
                self.sc.start(args[0])

        elif cmd == "challenge":
            self.sc.quick_challenge()

        elif cmd == "abandon":
            self.sc.abandon()

        elif cmd == "achievements":
            from core.menu import _show_achievements
            _show_achievements(self.s)

        # Live theme / font switching
        elif cmd == "theme":
            chosen = theme_picker()
            self.s.data["color_theme"] = chosen
            self.s.save()
            print(ok(f"  ✓ Theme: {THEMES[chosen]['name']}"))

        elif cmd == "font":
            chosen = font_picker()
            self.s.data["banner_font"] = chosen
            self.s.save()
            print(ok(f"  ✓ Font: {chosen}"))

        elif cmd == "speed":
            chosen = speed_picker()
            self.s.data["anim_speed"] = chosen
            self.s.save()
            print(ok(f"  ✓ Animation speed: {chosen}"))

        # ── Tailscale ─────────────────────────────────────────────────────────
        elif cmd == "tailscale":
            self.transfer.tailscale(args)

        # ── SSH ───────────────────────────────────────────────────────────────
        elif cmd == "ssh":
            self.transfer.ssh(args)
        elif cmd == "ssh-keygen":
            self.transfer.ssh_keygen(args)
        elif cmd == "ssh-copy-id":
            self.transfer.ssh_copy_id(args)

        # ── rsync ─────────────────────────────────────────────────────────────
        elif cmd == "rsync":
            self.transfer.rsync(args)

        # ── ping ──────────────────────────────────────────────────────────────
        elif cmd == "ping":
            self.transfer.ping(args)

        # ── Docker ────────────────────────────────────────────────────────────
        elif cmd == "docker":
            self.containers.docker(args)
        elif cmd in ("docker-compose","compose"):
            self.containers.docker_compose(args)

        # ── Nginx ─────────────────────────────────────────────────────────────
        elif cmd == "nginx":
            self.containers.nginx(args)

        # ── Networking ────────────────────────────────────────────────────────
        elif cmd == "netstat":
            self.networking.netstat(args)
        elif cmd == "ss":
            self.networking.ss(args)
        elif cmd == "ip":
            self.networking.ip(args)
        elif cmd == "ifconfig":
            self.networking.ifconfig(args)
        elif cmd in ("traceroute","tracepath"):
            self.networking.traceroute(args)
        elif cmd == "dig":
            self.networking.dig(args)
        elif cmd == "nslookup":
            self.networking.nslookup(args)
        elif cmd == "curl":
            self.networking.curl(args)
        elif cmd == "wget":
            self.networking.wget(args)
        elif cmd == "arp":
            self.networking.arp(args)
        elif cmd == "nload":
            self.networking.nload(args)
        elif cmd == "iftop":
            self.networking.iftop(args)
        elif cmd == "route":
            self.networking.netstat(["-r"])

        # ── Cybersecurity ─────────────────────────────────────────────────────
        elif cmd == "nmap":
            self.cybersec.nmap(args)
        elif cmd == "scan":
            self.cybersec.nmap(["-sV", args[0] if args else "100.64.1.20"])
        elif cmd == "tshark":
            self.cybersec.tshark(args)
        elif cmd in ("wireshark","tcpdump"):
            self.cybersec.wireshark(args)
        elif cmd == "gobuster":
            self.cybersec.gobuster(args)
        elif cmd == "dirb":
            self.cybersec.dirb(args)
        elif cmd == "nikto":
            self.cybersec.nikto(args)
        elif cmd == "hydra":
            self.cybersec.hydra(args)
        elif cmd == "hashcat":
            self.cybersec.hashcat(args)
        elif cmd in ("john","john-the-ripper"):
            self.cybersec.john(args)
        elif cmd in ("nc","netcat","ncat"):
            self.cybersec.nc(args)
        elif cmd == "openssl":
            self.cybersec.openssl(args)
        elif cmd == "ufw":
            self.cybersec.ufw(args)
        elif cmd in ("fail2ban-client","fail2ban"):
            self.cybersec.fail2ban(args)
        elif cmd == "lynis":
            self.cybersec.lynis(args)
        elif cmd == "shodan":
            self.cybersec.shodan(args)

        # ── Git ───────────────────────────────────────────────────────────────
        elif cmd == "git":
            self.git_mod.git(args)

        # ── Red Team ──────────────────────────────────────────────────────────
        elif cmd == "theharvester":
            self.redteam.theHarvester(args)
        elif cmd == "amass":
            self.redteam.amass(args)
        elif cmd == "dnsenum":
            self.redteam.dnsenum(args)
        elif cmd == "whois":
            self.redteam.whois(args)
        elif cmd == "searchsploit":
            self.redteam.searchsploit(args)
        elif cmd == "msfvenom":
            self.redteam.msfvenom(args)
        elif cmd == "msfconsole":
            self.redteam.msfconsole(args)
        elif cmd == "linpeas":
            self.redteam.linpeas(args)
        elif cmd == "pspy":
            self.redteam.pspy(args)
        elif cmd == "enum4linux":
            self.redteam.enum4linux(args)
        elif cmd in ("crackmapexec","cme"):
            self.redteam.crackmapexec(args)
        elif cmd == "responder":
            self.redteam.responder(args)
        elif cmd == "sqlmap":
            self.redteam.sqlmap(args)
        elif cmd == "report":
            self.redteam.report(args)
        elif cmd == "killchain":
            self.redteam.kill_chain_status()

        # ── Architecture (IaC & design) ────────────────────────────────────────
        elif cmd in ("terraform", "tf"):
            self.architecture.terraform(args)
        elif cmd == "diagram":
            self.architecture.diagram(args)

        # ── Blue Team / SOC (defensive) ──────────────────────────────────────────
        elif cmd in ("journalctl", "journal"):
            self.defense.journalctl(args)
        elif cmd == "grep":
            self.defense.grep(args)
        elif cmd == "siem":
            self.defense.siem(args)
        elif cmd == "alerts":
            self.defense.siem(["alerts"])
        elif cmd == "ioc":
            self.defense.ioc(args)
        elif cmd in ("incident", "ir"):
            self.defense.incident(args)
        elif cmd == "last":
            self.defense.last(args)
        elif cmd == "who":
            self.defense.who(args)

        # ── System / filesystem ───────────────────────────────────────────────
        elif cmd == "ls":
            self._ls(args)
        elif cmd in ("ll","la"):
            self._ls(["-la"] + args)
        elif cmd == "cd":
            self._cd(args)
        elif cmd == "pwd":
            print(f"  {self._expand(self.w.cwd)}")
        elif cmd == "whoami":
            print(f"  {self.s.get('username','user')}")
        elif cmd == "hostname":
            print(f"  {self.s.get('hostname','laptop')}")
        elif cmd == "df":
            self._df()
        elif cmd == "free":
            self._free()
        elif cmd == "uname":
            print(f"  Linux {self.s.get('hostname','laptop')} 6.8.0-arch1-1 #1 SMP PREEMPT_DYNAMIC x86_64 GNU/Linux")
        elif cmd in ("cat","less","more","head","tail"):
            self._cat(args)
        elif cmd == "mkdir":
            path = args[0] if args else "newdir"
            self.w.fs.setdefault("laptop",{})[path] = {"size_mb":0,"type":"dir"}
            print(ok(f"  ✓ {path}"))
        elif cmd == "touch":
            path = args[0] if args else "newfile"
            self.w.fs.setdefault("laptop",{})[path] = {"size_mb":0,"type":"file"}
        elif cmd == "rm":
            path = args[-1] if args else ""
            fs = self.w.fs.get("laptop",{})
            if path in fs:
                del fs[path]; print(ok(f"  removed '{path}'"))
            else:
                print(dim(f"  rm: {path}: No such file or directory"))
        elif cmd == "cp":
            if len(args) >= 2:
                src_c = self.w.fs.get("laptop",{}).get(args[0],{"size_mb":1,"type":"file"})
                self.w.fs.setdefault("laptop",{})[args[1]] = src_c
                print(ok(f"  ✓ {args[0]} → {args[1]}"))
        elif cmd == "mv":
            if len(args) >= 2:
                fs = self.w.fs.setdefault("laptop",{})
                content = fs.pop(args[0],{"size_mb":1,"type":"file"})
                fs[args[1]] = content
                print(ok(f"  ✓ {args[0]} → {args[1]}"))
        elif cmd in ("top","htop"):
            self._htop()
        elif cmd == "ps":
            self._ps()
        elif cmd == "history":
            self._history()
        elif cmd in ("man","info"):
            self._help([args[0]] if args else [])
        elif cmd == "which":
            tool = args[0] if args else ""
            paths = {"rsync":"/usr/bin/rsync","docker":"/usr/bin/docker",
                     "nmap":"/usr/bin/nmap","ssh":"/usr/bin/ssh",
                     "tailscale":"/usr/bin/tailscale","nginx":"/usr/sbin/nginx",
                     "git":"/usr/bin/git"}
            print(f"  {paths.get(tool,'/usr/bin/'+tool)}")
        elif cmd == "echo":
            print("  " + " ".join(args))
        elif cmd == "env":
            u = self.s.get("username","user")
            print(f"  USER={u}\n  HOME=/home/{u}\n  PATH=/usr/local/bin:/usr/bin:/bin\n  SHELL=/bin/zsh\n  TERM=xterm-256color")
        elif cmd == "date":
            print(f"  {time.strftime('%a %b %d %H:%M:%S %Z %Y')}")
        elif cmd == "uptime":
            print(f"  {time.strftime('%H:%M:%S')} up 3 days, 14:22,  2 users,  load average: 0.42, 0.38, 0.35")
        elif cmd in ("reboot","shutdown"):
            print(warn("  ⚠ Simulated — no real reboot."))
        elif cmd == "sudo":
            if args:
                return self._dispatch(args[0], args[1:], " ".join(args))
            print(warn("  sudo: no command given"))
        elif cmd == "!!":
            hist = self.s.get("history",[])
            if len(hist) >= 2:
                last = hist[-2]
                print(dim(f"  {last}"))
                try:
                    t2 = shlex.split(last)
                    return self._dispatch(t2[0].lower(), t2[1:], last)
                except Exception:
                    pass
        else:
            th = get_theme()
            print(warn(f"  bash: {cmd}: command not found"))
            print(dim(f"  Type {th['cmd']}help{R} to see available commands."))
            self.s.data["total_mistakes"] = self.s.data.get("total_mistakes",0) + 1

    # ── Help ──────────────────────────────────────────────────────────────────

    def _help(self, args):
        topic = args[0].lower() if args else None
        th    = get_theme()

        if topic == "rsync":
            self.transfer._rsync_help()
        elif topic in ("docker","compose"):
            self.containers._docker_help()
        elif topic == "nginx":
            self.containers._nginx_help()
        elif topic == "nmap":
            self.cybersec._nmap_help()
        elif topic == "tailscale":
            self.transfer._ts_help()
        elif topic in ("ssh","ssh-keygen","ssh-copy-id"):
            self._ssh_help()
        elif topic in ("networking","netstat","ss","ip"):
            self._networking_help()
        elif topic in ("cybersec","security","cyber"):
            self._cybersec_help()
        elif topic == "combo":
            self.sc.combo_guide()
        elif topic == "git":
            self.git_mod._help()
        elif topic in ("redteam","red","pentest","rt"):
            self.redteam.help()
        elif topic in ("architecture","arch","terraform","tf","iac","diagram"):
            self.architecture.help()
        elif topic in ("defense","soc","blueteam","blue","siem","journalctl",
                       "incident","ioc","ir"):
            self.defense.help()
        else:
            self._full_help()

    def _full_help(self):
        sections = [
            ("Transfer & Connectivity", [
                ("tailscale",      "up|down|status|ping|ip|netcheck"),
                ("rsync",          "[flags] <src> <dst>"),
                ("ssh",            "user@host"),
                ("ssh-keygen",     "generate RSA key pair"),
                ("ssh-copy-id",    "user@host — install key on remote"),
                ("ping",           "[-c n] <host>"),
            ]),
            ("Containers & Web", [
                ("docker ps/images/pull/run/stop/rm", "container lifecycle"),
                ("docker logs/exec/build/inspect/stats", "inspection & debugging"),
                ("docker compose up/down/logs",      "multi-service control"),
                ("docker network/volume",            "networking & storage"),
                ("nginx status/reload/test",         "web server control"),
                ("nginx config create/enable/ssl",   "site configuration"),
            ]),
            ("Networking", [
                ("netstat -tulnp",   "listening ports + PIDs"),
                ("ss -tulnp",        "modern netstat replacement"),
                ("ip addr/route/link","interface info & routing"),
                ("ifconfig",         "classic interface tool"),
                ("dig <domain> A",   "DNS lookup"),
                ("traceroute",       "network path tracing"),
                ("curl -v <url>",    "HTTP client with verbose mode"),
                ("nload / iftop",    "live bandwidth monitors"),
            ]),
            ("Cybersecurity  (all simulated)", [
                ("nmap -sV -O -A --script vuln", "port scan + vuln detection"),
                ("tshark -i eth0 -c 50 -w f",   "packet capture"),
                ("gobuster dir -u <url> -w wl",  "directory brute-force"),
                ("nikto -h <host>",              "web vulnerability scanner"),
                ("hydra -l user -P wl host ssh", "credential brute-force"),
                ("hashcat -m 0 hashes wl",       "password cracking"),
                ("ufw / fail2ban / lynis",        "host hardening"),
                ("shodan host/search",            "OSINT lookup"),
            ]),
            ("Git", [
                ("git init/clone/status/add",     "repo basics"),
                ("git commit/push/pull/fetch",     "history & remote sync"),
                ("git branch/checkout/switch",     "branching"),
                ("git merge/rebase [-i]",          "integrating changes"),
                ("git stash/reset/revert/clean",   "undo & shelving"),
                ("git log/diff/show/blame",        "inspection"),
                ("git tag/bisect/submodule",       "advanced"),
            ]),
            ("Red Team  (educational simulations)", [
                ("theHarvester -d <domain> -b all","OSINT email/subdomain harvest"),
                ("amass enum -d <domain>",         "subdomain enumeration"),
                ("searchsploit <term>",            "exploit-db search"),
                ("msfvenom -p <payload> …",        "payload generation"),
                ("msfconsole",                     "full Metasploit console"),
                ("sqlmap -u <url> --dump",         "SQL injection"),
                ("linpeas / pspy",                 "post-exploit enumeration"),
                ("enum4linux / crackmapexec",      "SMB / lateral movement"),
                ("responder -I eth0",              "NTLMv2 hash capture"),
                ("report [file.md]",               "generate engagement report"),
                ("killchain",                      "kill chain phase tracker"),
            ]),
            ("Architecture  (IaC & design)", [
                ("terraform init/plan/apply",   "infrastructure as code workflow"),
                ("terraform show/output/destroy","inspect & tear down"),
                ("diagram",                     "visualize your live infrastructure"),
                ("diagram web/k8s/vpc",          "reference system-design topologies"),
            ]),
            ("Blue Team / SOC  (defensive)", [
                ("journalctl -u sshd",          "read systemd service logs"),
                ("grep <pat> auth.log",          "search the raw log files"),
                ("last / who",                   "review login sessions"),
                ("siem dashboard/alerts",        "the SIEM alert queue"),
                ("siem investigate/ack/escalate","triage an alert"),
                ("ioc add/list/export",          "indicators of compromise"),
                ("incident status/timeline",     "incident-response workflow"),
                ("incident contain/report",      "block the attacker · write it up"),
            ]),
            ("Game", [
                ("missions",        "list all missions"),
                ("mission <id>",    "start a mission  e.g. mission ts01"),
                ("challenge",       "quick single-command drill"),
                ("status",          "active mission progress"),
                ("xp",              "XP, level, stats"),
                ("theme",           "change colour palette live"),
                ("font",            "change banner font live"),
                ("speed",           "animation speed: cinematic/fast/instant"),
                ("achievements",    "earned badges"),
                ("save",            "manual save"),
                ("help <module>",   "deep-dive reference  (git · docker · rsync…)"),
            ]),
        ]
        help_box(sections, width=76, style="double")

    def _ssh_help(self):
        th = get_theme()
        lines = [
            f"  {cyan('ssh user@host')}              connect to remote host",
            f"  {cyan('ssh -p 2222 user@host')}      custom port",
            f"  {cyan('ssh-keygen')}                 generate RSA 4096-bit key pair",
            f"  {cyan('ssh-copy-id user@host')}      install public key on remote",
            "",
            dim("  Workflow:"),
            dim("  1. ssh-keygen"),
            dim("  2. ssh-copy-id user@host"),
            dim("  3. ssh user@host  ← passwordless"),
        ]
        box("SSH Reference", lines, width=60, style="round",
            border_color=th["box_border"])

    def _networking_help(self):
        th = get_theme()
        lines = [
            f"  {cyan('ss -tulnp')}            TCP+UDP listening ports + PIDs",
            f"  {cyan('netstat -tulnp')}        same (older tool)",
            f"  {cyan('netstat -an')}           all connections numeric",
            f"  {cyan('ip addr')}               interface addresses",
            f"  {cyan('ip route')}              routing table",
            f"  {cyan('ip link show')}          link state",
            f"  {cyan('ifconfig')}              classic interface info",
            f"  {cyan('dig domain A')}          DNS A record",
            f"  {cyan('dig domain MX')}         MX records",
            f"  {cyan('traceroute host')}        hop-by-hop path",
            f"  {cyan('curl -v https://host')}  full HTTP + headers",
            f"  {cyan('curl -I https://host')}  headers only",
            f"  {cyan('wget <url>')}            download file",
            f"  {cyan('nload eth0')}            live bandwidth",
            f"  {cyan('iftop')}                per-connection bandwidth",
            f"  {cyan('arp -n')}               ARP table",
        ]
        box("Networking Reference", lines, width=66, style="round",
            border_color=th["box_border"])

    def _cybersec_help(self):
        th = get_theme()
        lines = [
            f"  {bold('Scanning & Recon')}",
            f"  {cyan('nmap -sV -O <host>')}                version + OS detection",
            f"  {cyan('nmap -A --script vuln <host>')}       aggressive + vuln scan",
            f"  {cyan('nmap -sS -p- <host>')}               all ports SYN scan",
            f"  {cyan('nmap <subnet>/24')}                  subnet host discovery",
            f"  {cyan('shodan host <ip>')}                  OSINT host lookup",
            "",
            f"  {bold('Web')}",
            f"  {cyan('gobuster dir -u <url> -w <wl>')}     directory brute-force",
            f"  {cyan('nikto -h <host>')}                   web vuln scanner",
            "",
            f"  {bold('Traffic')}",
            f"  {cyan('tshark -i eth0 -c 50')}              capture 50 packets",
            f"  {cyan('tshark -f \"tcp port 80\"')}           BPF capture filter",
            f"  {cyan('tshark -w file.pcap')}               save capture",
            f"  {cyan('tshark -r file.pcap')}               read capture",
            "",
            f"  {bold('Passwords')}",
            f"  {cyan('hashcat -m 0 hashes.txt rockyou')}   MD5 crack",
            f"  {cyan('hashcat -m 5600')}                   NTLMv2",
            f"  {cyan('john shadow.txt')}                   auto-detect + crack",
            f"  {cyan('hydra -l u -P list host ssh')}       SSH brute-force",
            "",
            f"  {bold('Hardening')}",
            f"  {cyan('lynis audit system')}                full security audit",
            f"  {cyan('ufw enable && ufw allow 22')}        firewall setup",
            f"  {cyan('fail2ban-client status sshd')}       banned IPs",
        ]
        box("Cybersecurity Reference", lines, width=68, style="double",
            border_color=th["box_border"])

    # ── System commands ───────────────────────────────────────────────────────

    def _expand(self, path):
        """Render a '~'-relative path as an absolute /home path for display."""
        u = self.s.get("username", "user")
        if path == "~":
            return f"/home/{u}"
        if path.startswith("~/"):
            return f"/home/{u}/{path[2:]}"
        return path

    def _cd(self, args):
        target = args[0] if args else "~"
        dest = self.w.resolve_path(target)
        if self.w.dir_exists(dest):
            self.w.cwd = dest
        else:
            print(err(f"  cd: {target}: No such file or directory"))

    def _ls(self, args):
        long_fmt = any(a in ("-l","-la","-al","-a","--all") for a in args)
        path_arg = next((a for a in args if not a.startswith("-")), None)
        target   = self.w.resolve_path(path_arg) if path_arg else self.w.cwd

        if not self.w.dir_exists(target):
            print(dim(f"  ls: cannot access '{path_arg or target}': "
                      f"No such file or directory"))
            return

        kids = self.w.children(target)
        if not kids:
            return   # empty directory

        u  = self.s.get("username", "user")
        fs = self.w._laptop_fs()
        for name in sorted(kids):
            is_dir = kids[name]
            if long_fmt:
                full = target.rstrip("/") + "/" + name
                conf = fs.get(full) or fs.get(full + "/") or {}
                mb   = conf.get("size_mb", 0)
                perm = "drwxr-xr-x" if is_dir else "-rw-r--r--"
                sz   = f"{mb:>8.1f}M" if mb >= 1 else f"{int(mb*1024):>8}K"
                dt   = time.strftime("%b %d %H:%M")
                disp = cyan(name + "/") if is_dir else white(name)
                print(f"  {DIM}{perm}  1 {u} {u}{R}  {sz}  {DIM}{dt}{R}  {disp}")
            else:
                print(f"  {cyan(name + '/') if is_dir else name}")

    def _df(self):
        th = get_theme()
        lines = [
            f"  {th['cmd']}{'Filesystem':<20}{R} {'Size':>7} {'Used':>7} {'Avail':>7}  Use%  Mounted",
            f"  {DIM}{'─'*60}{R}",
            f"  /dev/sda1           {'500G':>7} {'120G':>7} {'380G':>7}  24%   /",
            f"  /dev/sdb1           {'2.0T':>7} {'800G':>7} {'1.2T':>7}  40%   /mnt/storage",
            f"  tmpfs               {'8.0G':>7} {'12M':>7}  {'8.0G':>7}  1%    /tmp",
        ]
        print()
        for l in lines: print(l)
        print()

    def _free(self):
        print()
        print(info(f"  {'':>14}{'total':>10}{'used':>10}{'free':>10}{'available':>12}"))
        print(f"  {'Mem:':<14}{'15Gi':>10}{'4.2Gi':>10}{'8.1Gi':>10}{'10Gi':>12}")
        print(f"  {'Swap:':<14}{'2.0Gi':>10}{'0B':>10}{'2.0Gi':>10}")
        print()

    def _htop(self):
        print(info("\n  [simulated top/htop]\n"))
        print(f"  {'PID':>6}  {'USER':<10} {'CPU%':>5}  {'MEM%':>5}  COMMAND")
        print(dim("  " + "─"*45))
        procs = [
            (1,    "root",    0.0, 0.1, "systemd"),
            (1234, "root",    0.0, 0.2, "sshd"),
            (5678, "www-data",0.3, 1.2, "nginx: worker"),
            (9012, self.s.get("username","user"), 2.1, 3.5, "node server.js"),
            (9100, "prometheus", 0.8, 2.1, "prometheus"),
        ]
        for pid, user, cpu, mem, cmd in procs:
            print(f"  {pid:>6}  {user:<10} {cpu:>5.1f}  {mem:>5.1f}  {dim(cmd)}")
        print()

    def _ps(self):
        print(info(f"\n  {'PID':>6}  {'TTY':<8}  {'TIME':<10}  CMD"))
        print(dim("  " + "─"*38))
        print(f"  {os.getpid():>6}  pts/0     00:00:01  sysops")
        print(f"  {'1234':>6}  ?         00:00:00  sshd")
        print(f"  {'5678':>6}  pts/1     00:00:02  zsh")
        print()

    def _cat(self, args):
        path = args[0] if args else None
        if not path:
            print(warn("  cat: missing file operand")); return
        for name, conf in self.w.nginx_configs.items():
            if name in path or path.endswith(name):
                print(dim(conf)); return
        if "access.log" in path:
            self.containers._nginx_logs("access"); return
        if "error.log" in path:
            self.containers._nginx_logs("error"); return
        fs = self.w.fs.get("laptop",{})
        for k in fs:
            if path in k or k.endswith(path.lstrip("~/")):
                print(dim(f"  [binary or empty file: {path}]")); return
        print(err(f"  cat: {path}: No such file or directory"))

    def _history(self):
        hist = self.s.get("history",[])
        for i, c in enumerate(hist[-20:], max(1, len(hist)-19)):
            print(f"  {DIM}{i:>5}{R}  {c}")

    # ── XP panel ──────────────────────────────────────────────────────────────

    def _show_xp(self):
        xp     = self.s.get("xp",0)
        lvl    = level_for_xp(xp)
        title  = LEVEL_TITLES[min(lvl, len(LEVEL_TITLES)-1)]
        to_nxt = 0
        for t in XP_PER_LEVEL:
            if xp < t:
                to_nxt = t - xp; break
        diff   = DIFF_NAMES.get(self.s.get("difficulty",2),"?")
        done   = len(self.s.get("completed_scenarios",[]))
        from scenarios.missions import SCENARIOS
        total  = len(SCENARIOS)
        cmds   = self.s.get("total_commands",0)
        achs   = len(self.s.get("achievements",[]))
        u      = self.s.get("username","user")
        h      = self.s.get("hostname","host")
        print()
        xp_panel(xp, lvl, title, to_nxt, diff, done, total, cmds, achs, u, h)
        print()

    # ── Welcome ───────────────────────────────────────────────────────────────

    def _welcome(self):
        th    = get_theme()
        u     = self.s.get("username","user")
        h     = self.s.get("hostname","host")
        lvl   = level_for_xp(self.s.get("xp",0))
        title = LEVEL_TITLES[min(lvl, len(LEVEL_TITLES)-1)]
        focus = self.s.get("focus_module","rsync")
        diff  = DIFF_NAMES.get(self.s.get("difficulty",2),"?")
        bc    = th["banner_cols"]
        col   = fg256(bc[0]) if bc else BYELLOW

        print()
        hr_accent()
        print(f"  {ok('Welcome back,')} {cyan(u+'@'+h)}  "
              f"{DIM}│{R}  {col}{B}Level {lvl} — {title}{R}  "
              f"{DIM}│{R}  {warn(diff)}")
        print(f"  Focus: {th['cmd']}{B}{focus}{R}   "
              f"{DIM}│{R}   Type {th['cmd']}help{R} to see all commands   "
              f"{DIM}│{R}   {th['cmd']}theme{R} {DIM}to restyle{R}")
        if self.sc.active:
            print(f"  {BCYAN}Active mission: {self.sc.active['title']}{R}  "
                  f"{DIM}(type status){R}")
        else:
            from scenarios.missions import SCENARIOS
            remaining = len(SCENARIOS) - len(self.s.get("completed_scenarios",[]))
            if remaining:
                print(f"  {DIM}{remaining} missions remaining — {th['cmd']}missions{R}{DIM} to list{R}")
        hr_accent()
        print()

    # ── Quit ─────────────────────────────────────────────────────────────────

    def _do_quit(self):
        self._sync_world()
        self.s.save()
        self._save_history()
        th  = get_theme()
        col = fg256(th["banner_cols"][0]) if th["banner_cols"] else BYELLOW
        print()
        print(f"  {DIM}Progress saved.{R}")
        print(f"  {DIM}Final XP:{R} {col}{B}{self.s.get('xp',0):,}{R}  "
              f"{DIM}Level:{R} {self.s.get('level',1)}")
        print(f"  {DIM}See you next time,{R} {cyan(self.s.get('username','operator'))}{DIM}.{R}")
        print()

    # ── World sync ────────────────────────────────────────────────────────────

    def _sync_world(self):
        if self.s.data:
            self.s.data["world"] = self.w.to_dict()
