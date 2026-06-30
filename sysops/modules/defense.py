"""
modules/defense.py — Blue-team / SOC analyst tools (all simulated)

The defender's side of the house. Where the red-team module attacks a target,
these tools investigate an intrusion that already happened on YOUR host:

    journalctl   read systemd service logs (sshd, nginx, sudo, …)
    grep         search the raw log files for indicators
    last / who   review login sessions
    siem         alert queue — dashboard, investigate, acknowledge, escalate
    ioc          collect indicators of compromise (IPs, users, hashes, domains)
    incident     incident-response workflow — timeline, contain, report

The whole thing reads ONE consistent intrusion baked into world.logs /
world.siem_alerts (see VirtualWorld._build_soc_environment): an external host
brute-forces SSH, lands on the 'deploy' account, escalates via sudo, and scans
the web app. Detection → triage → containment → reporting is the loop, and it's
the actual day-job of a SOC analyst.

ALL SIMULATED — educational only. No real logs are read and nothing is blocked.
"""

import time
from core.ui import *
from core.world import BREACHED_USER

# IR phases, in order — mirrors NIST SP 800-61 (Detection through Post-Incident).
IR_PHASES = ["detect", "triage", "contain", "eradicate", "recover", "report"]

PRIO_COLOR = {
    "emerg": BRED, "alert": BRED, "crit": BRED, "err": BRED,
    "warning": BYELLOW, "notice": BCYAN, "info": DIM, "debug": DIM,
}

# Syslog identifier (with a stable PID) shown per unit, like real journalctl.
IDENTIFIERS = {
    "sshd": "sshd[2211]", "sudo": "sudo", "nginx": "nginx",
    "kernel": "kernel", "cron": "CRON[8800]",
}


class DefenseModule:
    def __init__(self, world, save):
        self.w = world
        self.s = save
        # Older saves won't have defense_state; make sure it's present + complete.
        d = getattr(self.w, "defense_state", None) or {}
        for k, v in {
            "incident_open": False, "attacker_ip": None,
            "alerts_investigated": [], "alerts_acked": [], "alerts_escalated": [],
            "iocs": [], "timeline": [], "blocked_ips": [], "report_done": False,
        }.items():
            d.setdefault(k, v)
        self.w.defense_state = d

    # ── helpers ───────────────────────────────────────────────────────────────

    def _d(self):
        return self.w.defense_state

    def _xp(self, pts, reason):
        lvl = self.s.add_xp(pts, reason)
        xp_flash(pts, reason)
        if lvl > 0:
            from core.save import level_for_xp
            lv = level_for_xp(self.s.get("xp", 0))
            print(f"\n  {BYELLOW}{B}★ LEVEL UP → Level {lv}{R}\n")

    # ════════════════════════════════════════════════════════════════════════
    # journalctl — systemd service logs
    # ════════════════════════════════════════════════════════════════════════

    def journalctl(self, args):
        if not args or args[0] in ("-h", "--help"):
            self._journalctl_help(); return

        unit = None
        grep = None
        prio = None
        lines = None
        follow = "-f" in args or "--follow" in args

        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-u", "--unit") and i + 1 < len(args):
                unit = args[i + 1].replace(".service", ""); i += 1
            elif a.startswith("-u"):
                unit = a[2:].replace(".service", "")
            elif a in ("-g", "--grep") and i + 1 < len(args):
                grep = args[i + 1]; i += 1
            elif a in ("-p", "--priority") and i + 1 < len(args):
                prio = args[i + 1]; i += 1
            elif a in ("-n", "--lines") and i + 1 < len(args):
                try: lines = int(args[i + 1])
                except ValueError: pass
                i += 1
            i += 1

        units = [unit] if unit else list(self.w.logs.keys())
        rows = []
        for u in units:
            for ts, lp, msg in self.w.logs.get(u, []):
                rows.append((ts, lp, u, msg))

        if not rows:
            print(dim(f"  -- no entries for unit '{unit}' --")); return

        # Priority filter: keep entries at or above the requested level.
        if prio:
            order = ["emerg", "alert", "crit", "err", "warning", "notice", "info", "debug"]
            keep = set(order[:order.index(prio) + 1]) if prio in order else None
            if keep:
                rows = [r for r in rows if r[1] in keep]
        if grep:
            rows = [r for r in rows if grep.lower() in r[3].lower()]
        if lines:
            rows = rows[-lines:]

        print()
        print(dim(f"  -- Logs begin, {len(rows)} entries --"))
        for ts, lp, u, msg in rows:
            col = PRIO_COLOR.get(lp, DIM)
            host = self.s.get("hostname", "server")
            ident = IDENTIFIERS.get(u, u)
            print(f"  {DIM}{ts}{R} {host} {col}{ident}{R}: {msg}")
        print(dim("  -- Logs end --"))
        if follow:
            print(dim("  (live follow simulated — Ctrl-C to stop)"))

        # Nudge the analyst toward the story when they hit the SSH log.
        if (unit == "sshd" or grep) and any("Accepted password" in r[3] for r in rows):
            print(info(f"\n  ⚠ Note the {warn('Accepted password')} after a run of failures — "
                       f"the brute force {err('succeeded')}."))
            print(dim("  Next: siem alerts  ·  grep 'Failed password' /var/log/auth.log"))
        self.s.add_xp(8, "log review"); xp_flash(8, "log review")

    def _journalctl_help(self):
        lines = [
            f"  {cyan('journalctl -u sshd')}            logs for one unit (sshd/nginx/sudo/cron)",
            f"  {cyan('journalctl -u sshd -n 20')}      last 20 lines",
            f"  {cyan('journalctl -p err')}             priority filter (err/warning/notice…)",
            f"  {cyan('journalctl -g \"Failed\"')}        grep within the journal",
            f"  {cyan('journalctl -f')}                 follow live (simulated)",
            "",
            dim("  Units available: " + ", ".join(self.w.logs.keys())),
        ]
        box("journalctl — systemd journal", lines, width=66, style="round")

    # ════════════════════════════════════════════════════════════════════════
    # grep — search the raw log files
    # ════════════════════════════════════════════════════════════════════════

    # Map the friendly /var/log paths players will type to log units.
    _LOGFILES = {
        "auth.log": "sshd", "auth": "sshd", "secure": "sshd",
        "syslog": None, "messages": None,
        "access.log": "nginx", "nginx": "nginx",
        "sudo.log": "sudo",
    }

    def grep(self, args):
        if len(args) < 1:
            print(warn("  usage: grep [-i] <pattern> <file>")); return
        ignore_case = "-i" in args
        count_only = "-c" in args
        toks = [a for a in args if not a.startswith("-")]
        if not toks:
            print(warn("  usage: grep [-i] <pattern> <file>")); return
        pattern = toks[0].strip("'\"")
        target = toks[1] if len(toks) > 1 else ""

        # Which log unit(s) to search.
        unit = None
        for name, u in self._LOGFILES.items():
            if name in target:
                unit = u; break
        units = [unit] if unit else list(self.w.logs.keys())

        needle = pattern.lower() if ignore_case else pattern
        matches = []
        for u in units:
            for ts, lp, msg in self.w.logs.get(u, []):
                hay = msg.lower() if ignore_case else msg
                if needle in hay:
                    matches.append((ts, u, msg))

        if count_only:
            print(f"  {len(matches)}"); return
        if not matches:
            print(dim(f"  (no matches for '{pattern}')")); return

        print()
        for ts, u, msg in matches:
            hl = msg.replace(pattern, f"{BYELLOW}{B}{pattern}{R}{DIM}") if not ignore_case else msg
            print(f"  {DIM}{ts} {IDENTIFIERS.get(u, u)}: {hl}{R}")
        print(dim(f"\n  {len(matches)} match(es)."))
        if any("Failed password" in m[2] or "Accepted password" in m[2] for m in matches):
            print(info(f"  💡 Same source IP across these? That's your attacker — "
                       f"record it: {cyan('ioc add <ip>')}"))

    # ════════════════════════════════════════════════════════════════════════
    # last / who — login sessions
    # ════════════════════════════════════════════════════════════════════════

    def last(self, args):
        atk = self.w.attacker_ip
        rows = [
            (self.s.get("username", "user"), "pts/0", "192.168.1.50", "today 08:14", "still logged in"),
            (BREACHED_USER, "pts/1", atk, "today 02:12", "02:12 - 03:40 (01:28)"),
            ("root", "pts/1", atk, "today 02:13", "02:13 - 03:40 (01:27)"),
            ("root", "console", "-", "today 00:01", "boot"),
        ]
        print()
        for u, tty, host, start, dur in rows:
            sus = err("⚠") if host == atk else " "
            uc = warn(u) if host == atk else cyan(u)
            print(f"  {sus} {uc:<22} {tty:<8} {dim(host):<28} {DIM}{start:<14} {dur}{R}")
        print(dim(f"\n  wtmp begins {time.strftime('%a %b %d')}."))
        print(info(f"  ⚠ '{BREACHED_USER}' and 'root' logged in from {warn(atk)} — "
                   f"not an internal address."))

    def who(self, args):
        print()
        print(f"  {cyan(self.s.get('username','user')):<16} pts/0    {dim('192.168.1.50')}")
        print(f"  {warn(BREACHED_USER):<16} pts/1    {warn(self.w.attacker_ip)}  {err('← suspicious')}")

    # ════════════════════════════════════════════════════════════════════════
    # siem — alert queue: dashboard / alerts / investigate / ack / escalate
    # ════════════════════════════════════════════════════════════════════════

    def siem(self, args):
        sub = args[0].lower() if args else "dashboard"

        if sub in ("dashboard", "dash", "overview", "status"):
            self._siem_dashboard()
        elif sub in ("alerts", "list", "queue", "ls"):
            self._siem_alerts()
        elif sub in ("investigate", "show", "view", "open") and len(args) > 1:
            self._siem_investigate(args[1])
        elif sub in ("ack", "acknowledge", "close") and len(args) > 1:
            self._siem_ack(args[1])
        elif sub in ("escalate", "raise") and len(args) > 1:
            self._siem_escalate(args[1])
        else:
            print(warn("  usage: siem dashboard | alerts | investigate <id> | "
                       "ack <id> | escalate <id>"))

    def _sev_counts(self):
        c = {}
        for a in self.w.siem_alerts:
            if self.w.alert_status(a["id"]) in ("CLOSED",):
                continue
            c[a["severity"]] = c.get(a["severity"], 0) + 1
        return c

    def _siem_dashboard(self):
        d = self._d()
        total = len(self.w.siem_alerts)
        open_n = sum(1 for a in self.w.siem_alerts
                     if self.w.alert_status(a["id"]) != "CLOSED")
        counts = self._sev_counts()
        lines = [
            f"  {bold('Open alerts')}   {warn(str(open_n))}{DIM}/{total}{R}",
            "",
            f"  {sev('CRITICAL')} {counts.get('CRITICAL',0)}    "
            f"{sev('HIGH')} {counts.get('HIGH',0)}    "
            f"{sev('MEDIUM')} {counts.get('MEDIUM',0)}",
            f"  {sev('LOW')} {counts.get('LOW',0)}    "
            f"{sev('INFO')} {counts.get('INFO',0)}",
            "",
            f"  Investigated  {ok(str(len(d['alerts_investigated'])))}",
            f"  Escalated     {err(str(len(d['alerts_escalated'])))}",
            f"  Incident open {err('YES') if d['incident_open'] else dim('no')}",
        ]
        box("SOC — Alert Dashboard", lines, width=58, style="heavy")
        print(dim("  siem alerts  to see the queue  ·  siem investigate <id>"))

    def _siem_alerts(self):
        section("SIEM ALERT QUEUE", BCYAN)
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        for a in sorted(self.w.siem_alerts, key=lambda x: order.get(x["severity"], 9)):
            st = self.w.alert_status(a["id"])
            st_col = {"NEW": warn, "INVESTIGATING": info,
                      "ESCALATED": err, "CLOSED": dim}.get(st, dim)
            print(f"  {sev(a['severity'])} {BWHITE}{B}#{a['id']}{R}  {a['rule']}")
            print(f"        src {cyan(a['src'])}  {DIM}→ {a['host']}{R}  "
                  f"{DIM}{a['time']}{R}  [{st_col(st)}]")
        print()
        print(dim("  siem investigate <id>   open a case   ·   siem ack <id>   close benign"))

    def _siem_investigate(self, aid):
        a = self.w.alert_by_id(aid)
        if not a:
            print(err(f"  No alert #{aid}.")); return
        d = self._d()
        if a["id"] not in d["alerts_investigated"]:
            d["alerts_investigated"].append(a["id"])
        # Investigating a malicious external alert confirms the attacker IP.
        if a["src"] not in (self.s.get("hostname", "server"), "localhost"):
            d["attacker_ip"] = a["src"]

        print()
        hr_red()
        print(f"  {sev(a['severity'])} {BWHITE}{B}ALERT #{a['id']}{R}  {a['rule']}")
        hr_red()
        print(f"  Source     : {cyan(a['src'])}")
        print(f"  Host       : {a['host']}")
        print(f"  First seen : {a['time']}")
        print(f"  ATT&CK     : {warn(a['mitre'])}")
        print(f"\n  {bold('What happened')}")
        for seg in wrap_ansi("  " + a["detail"], 74):
            print(dim(seg))
        print(f"\n  {bold('Recommended action')}")
        for seg in wrap_ansi("  " + a["recommend"], 74):
            print(info(seg))
        print()
        if d["attacker_ip"]:
            print(ok(f"  ✓ Attacker IP confirmed: {warn(d['attacker_ip'])}  "
                     f"{dim('(record it: ioc add ' + d['attacker_ip'] + ')')}"))
        self._xp(12, f"investigated alert #{a['id']}")
        if self.s.grant_achievement("alert_triage", "Investigated a SIEM alert"):
            print(f"\n  {BYELLOW}{B}🏆 Achievement: First Responder!{R}")

    def _siem_ack(self, aid):
        a = self.w.alert_by_id(aid)
        if not a:
            print(err(f"  No alert #{aid}.")); return
        d = self._d()
        if a["id"] not in d["alerts_acked"]:
            d["alerts_acked"].append(a["id"])
        if a["severity"] in ("CRITICAL", "HIGH"):
            print(warn(f"  ⚠ Closed #{a['id']} ({a['severity']}). "
                       f"Acknowledging a real threat without containing it is how "
                       f"breaches get missed — be sure this is benign."))
        else:
            print(ok(f"  ✓ Alert #{a['id']} acknowledged and closed (benign)."))
        self.s.add_xp(6, "alert triage"); xp_flash(6, "alert triage")

    def _siem_escalate(self, aid):
        a = self.w.alert_by_id(aid)
        if not a:
            print(err(f"  No alert #{aid}.")); return
        d = self._d()
        if a["id"] not in d["alerts_escalated"]:
            d["alerts_escalated"].append(a["id"])
        d["incident_open"] = True
        if a["src"] not in (self.s.get("hostname", "server"), "localhost"):
            d["attacker_ip"] = a["src"]
        print()
        print(err(f"  🚨 Alert #{a['id']} escalated — INCIDENT OPENED"))
        print(dim(f"     {a['rule']}  ({a['severity']})"))
        print(info("  Move to incident response:  incident status  ·  ioc add <indicator>"))
        self._xp(15, "escalated to incident")

    # ════════════════════════════════════════════════════════════════════════
    # ioc — indicators of compromise
    # ════════════════════════════════════════════════════════════════════════

    def ioc(self, args):
        sub = args[0].lower() if args else "list"
        if sub in ("list", "ls", "show"):
            self._ioc_list()
        elif sub == "add" and len(args) > 1:
            self._ioc_add(args[1:])
        elif sub in ("export", "save"):
            self._ioc_export()
        else:
            print(warn("  usage: ioc list | ioc add <indicator> [note] | ioc export"))

    @staticmethod
    def _classify(value):
        v = value.strip()
        if v.count(".") == 3 and all(p.isdigit() for p in v.split(".")):
            return "ipv4"
        if len(v) in (32, 40, 64) and all(c in "0123456789abcdefABCDEF" for c in v):
            return {32: "md5", 40: "sha1", 64: "sha256"}[len(v)]
        if "@" in v:
            return "email"
        if "." in v and "/" not in v:
            return "domain"
        if "/" in v or v.startswith("http"):
            return "url"
        return "username" if v.isalnum() else "string"

    def _ioc_add(self, parts):
        value = parts[0]
        note = " ".join(parts[1:]) if len(parts) > 1 else ""
        d = self._d()
        kind = self._classify(value)
        if any(i["value"] == value for i in d["iocs"]):
            print(dim(f"  {value} already recorded.")); return
        d["iocs"].append({"type": kind, "value": value, "note": note})
        print(ok(f"  ✓ IOC recorded  [{warn(kind)}]  {cyan(value)}"
                 f"{('  — ' + note) if note else ''}"))
        if kind == "ipv4" and value == self.w.attacker_ip:
            print(info("  ✦ That's the confirmed attacker IP — good catch."))
        if len(d["iocs"]) >= 2 and self.s.grant_achievement(
                "ioc_collector", "Collected 2+ indicators of compromise"):
            print(f"\n  {BYELLOW}{B}🏆 Achievement: Threat Tracker!{R}")
        self.s.add_xp(8, "recorded IOC"); xp_flash(8, "recorded IOC")

    def _ioc_list(self):
        d = self._d()
        if not d["iocs"]:
            print(dim("  No IOCs yet.  ioc add <ip|hash|domain|user>")); return
        section("INDICATORS OF COMPROMISE", BCYAN)
        for i in d["iocs"]:
            print(f"  {warn('['+i['type']+']'):<14} {cyan(i['value'])}"
                  f"{('  '+dim(i['note'])) if i['note'] else ''}")
        print()

    def _ioc_export(self):
        d = self._d()
        if not d["iocs"]:
            print(dim("  Nothing to export — record IOCs first.")); return
        print()
        print(dim("  # iocs.csv  (share with your threat-intel platform / MISP)"))
        print(f"  {DIM}type,value,note{R}")
        for i in d["iocs"]:
            print(f"  {i['type']},{i['value']},{i['note']}")
        print(ok(f"\n  ✓ Exported {len(d['iocs'])} indicator(s) → iocs.csv"))
        self.s.add_xp(10, "exported IOCs"); xp_flash(10, "exported IOCs")

    # ════════════════════════════════════════════════════════════════════════
    # incident — IR workflow: status / timeline / add / contain / report
    # ════════════════════════════════════════════════════════════════════════

    def incident(self, args):
        sub = args[0].lower() if args else "status"
        if sub in ("status", "state", ""):
            self._incident_status()
        elif sub in ("timeline", "tl"):
            self._incident_timeline()
        elif sub == "add" and len(args) > 1:
            self._incident_add(" ".join(args[1:]))
        elif sub in ("contain", "block") and len(args) > 1:
            self._incident_contain(args[1])
        elif sub == "report":
            self._incident_report(args[1:])
        else:
            print(warn("  usage: incident status | timeline | add <event> | "
                       "contain <ip> | report"))

    def _ir_phase(self):
        """Derive the current IR phase from recorded progress."""
        d = self._d()
        if d["report_done"]:                  return "report"
        if d["blocked_ips"]:                  return "recover"
        if d["incident_open"] or d["attacker_ip"]: return "contain"
        if d["alerts_investigated"]:          return "triage"
        return "detect"

    def _incident_status(self):
        d = self._d()
        cur = self._ir_phase()
        print()
        print(f"  {BCYAN}{B}INCIDENT RESPONSE{R}   {dim('NIST SP 800-61 lifecycle')}")
        print(dim("  " + "─" * 52))
        for ph in IR_PHASES:
            done = IR_PHASES.index(ph) < IR_PHASES.index(cur)
            active = ph == cur
            icon = ok("✓") if done else (f"{BCYAN}{B}▶{R}" if active else dim("○"))
            name = f"{BCYAN}{B}{ph.upper()}{R}" if active else (
                ok(ph.upper()) if done else dim(ph.upper()))
            print(f"    {icon}  {name}")
        print()
        print(f"  Attacker IP : {warn(d['attacker_ip']) if d['attacker_ip'] else dim('(not confirmed)')}")
        print(f"  IOCs        : {BYELLOW}{len(d['iocs'])}{R}")
        print(f"  Timeline    : {BYELLOW}{len(d['timeline'])}{R} event(s)")
        print(f"  Contained   : {ok('yes') if d['blocked_ips'] else dim('no')}"
              f"{('  '+dim(', '.join(d['blocked_ips']))) if d['blocked_ips'] else ''}")
        print(f"  Report      : {ok('done') if d['report_done'] else dim('pending')}")
        print()

    def _incident_timeline(self):
        d = self._d()
        if not d["timeline"]:
            print(dim('  Timeline empty.  incident add "02:12 SSH brute force succeeded"')); return
        section("INCIDENT TIMELINE", BCYAN)
        for ev in d["timeline"]:
            print(f"  {cyan('•')} {ev}")
        print()

    def _incident_add(self, event):
        d = self._d()
        d["timeline"].append(event)
        d["timeline"].sort()
        print(ok(f"  ✓ Timeline +1  →  {event}"))
        self.s.add_xp(6, "timeline event"); xp_flash(6, "timeline event")

    def _incident_contain(self, ip):
        d = self._d()
        if ip not in d["blocked_ips"]:
            d["blocked_ips"].append(ip)
        d["incident_open"] = True
        print()
        spinner(f"Pushing firewall drop rule for {ip}", 0.8)
        print(ok(f"  ✓ {cyan(ip)} blocked at the host firewall (ufw deny from {ip})"))
        if ip == self.w.attacker_ip:
            print(info("  ✦ Attacker contained. Now reset the breached account and "
                       "preserve evidence before eradication."))
        else:
            print(warn(f"  ⚠ {ip} isn't the confirmed attacker — double-check the IOC."))
        self._xp(14, "contained host")
        if self.s.grant_achievement("first_contain", "Contained an active intrusion"):
            print(f"\n  {BYELLOW}{B}🏆 Achievement: Containment!{R}")

    def _incident_report(self, args):
        d = self._d()
        output = next((a for a in args if not a.startswith("-")), "incident-report.md")
        host = self.s.get("hostname", "server")
        atk = d["attacker_ip"] or self.w.attacker_ip

        print()
        spinner("Compiling incident report", 1.0)
        sev_rating = "CRITICAL" if d["incident_open"] else "MEDIUM"
        print(f"""
  {'━'*60}
  SECURITY INCIDENT REPORT
  {'━'*60}
  Incident : Unauthorized access via SSH brute force
  Host     : {host}
  Date     : {time.strftime('%Y-%m-%d')}
  Analyst  : {self.s.get('username','analyst')}
  Severity : {sev(sev_rating)}
  {'━'*60}

  SUMMARY
  {'─'*40}
  External host {atk} brute-forced SSH and authenticated as the
  service account '{BREACHED_USER}', then escalated to root via sudo.
  Web path-scanning from the same IP preceded the login.

  TIMELINE
  {'─'*40}""")
        if d["timeline"]:
            for ev in d["timeline"]:
                print(f"  • {ev}")
        else:
            print(dim("  (no timeline recorded — incident add \"<event>\")"))

        print(f"\n  INDICATORS OF COMPROMISE\n  {'─'*40}")
        if d["iocs"]:
            for i in d["iocs"]:
                print(f"  {warn('['+i['type']+']'):<14} {i['value']}")
        else:
            print(dim("  (none recorded — ioc add <indicator>)"))

        print(f"\n  CONTAINMENT\n  {'─'*40}")
        if d["blocked_ips"]:
            for ip in d["blocked_ips"]:
                print(f"  {ok('✓')} Blocked {ip} at the firewall")
        else:
            print(warn("  ⚠ Host NOT contained — block the attacker IP first."))

        print(f"""
  RECOMMENDATIONS
  {'─'*40}
  1. Reset '{BREACHED_USER}' + rotate all keys/secrets on the host
  2. Enforce key-only SSH and disable password auth
  3. Deploy fail2ban + rate-limit SSH at the firewall
  4. Audit sudoers — remove the NOPASSWD/shell escape
  5. Forward logs to the SIEM and alert on auth failures→success
  {'━'*60}
  Report saved: {ok(output)}""")

        d["report_done"] = True
        self._xp(30, "incident report")
        if self.s.grant_achievement("incident_handler", "Wrote a full incident report"):
            print(f"\n  {BYELLOW}{B}🏆 Achievement: Incident Handler!{R}")

    # ════════════════════════════════════════════════════════════════════════
    # help
    # ════════════════════════════════════════════════════════════════════════

    def help(self):
        lines = [
            f"  {bold('// DETECT — read the logs')}",
            f"  {cyan('journalctl -u sshd')}              service logs (sshd/nginx/sudo/cron)",
            f"  {cyan('journalctl -p err -u nginx')}       filter by priority",
            f"  {cyan('grep \"Failed password\" auth.log')}  search raw logs",
            f"  {cyan('last')} / {cyan('who')}                      login sessions",
            "",
            f"  {bold('// TRIAGE — work the SIEM queue')}",
            f"  {cyan('siem dashboard')}                  severity / status overview",
            f"  {cyan('siem alerts')}                     the alert queue",
            f"  {cyan('siem investigate <id>')}           open a case (confirms the IP)",
            f"  {cyan('siem ack <id>')}                   close a benign alert",
            f"  {cyan('siem escalate <id>')}              raise a real threat to incident",
            "",
            f"  {bold('// RESPOND — IOCs + incident handling')}",
            f"  {cyan('ioc add <ip|hash|domain|user>')}   record an indicator",
            f"  {cyan('ioc list')} / {cyan('ioc export')}            review / export to CSV",
            f"  {cyan('incident status')}                 IR lifecycle (NIST 800-61)",
            f"  {cyan('incident add \"<event>\"')}          build the timeline",
            f"  {cyan('incident contain <ip>')}           block the attacker",
            f"  {cyan('incident report')}                 generate the report",
            "",
            f"  {dim('Story: an external host brute-forced SSH, landed on a service')}",
            f"  {dim('account, escalated via sudo, and scanned the web app. Find it,')}",
            f"  {dim('triage it, contain it, and write it up. That loop IS the job.')}",
        ]
        box("Blue Team / SOC — Reference", lines, border_color=BCYAN, width=74)
