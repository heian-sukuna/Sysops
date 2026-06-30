"""
scenarios/soc_missions.py — Blue-team / SOC analyst mission pillar.

The defensive counterpart to the red-team pillar. Where rt01–rt06 attack a
target, these run the SOC day-job against an intrusion already sitting in the
host logs (see VirtualWorld._build_soc_environment): detect it in the logs,
triage the SIEM queue, build IOCs + a timeline, contain the attacker, and
write the incident report — the NIST SP 800-61 loop end to end.

All commands here are handled by modules/defense.py (journalctl, grep, siem,
ioc, incident) with firewall/audit support from modules/cybersec.py (ufw,
lynis). Step checks follow the project convention: verify real world state
where a command changes it (defense_state), otherwise confirm the command
actually ran via scenarios.checks — never `lambda w, s: True`.
"""

from scenarios.checks import ran, ran_any, ran_re, either


def _ip_ioc(w, s):
    return any(i.get("type") == "ipv4" for i in w.defense_state.get("iocs", []))


SOC_MISSIONS = [
    {
        "id": "soc01",
        "title": "Catch the Brute Force",
        "category": "blue team: SOC — detection",
        "difficulty": 2,
        "tags": ["BLUE TEAM", "DEFENSIVE", "SOC", "MEDIUM"],
        "story": (
            "It's 09:00 and the overnight alerts are stacked up. Something hit "
            "the server's SSH while you slept. Open the logs, prove it was a "
            "brute force, pin down the source IP, and slam the door — before "
            "whoever it is comes back. Read first, confirm, then act."
        ),
        "steps": [
            ("Read the SSH service logs and spot the failed-then-accepted pattern",
             either(ran("journalctl", "sshd"), ran("grep", "auth")),
             "journalctl -u sshd"),
            ("Filter the auth log down to the failed password attempts",
             ran_re(r"(grep.+fail|journalctl.+-g)"),
             "grep \"Failed password\" /var/log/auth.log"),
            ("Confirm the attacker's source IP via the SIEM",
             lambda w, s: bool(w.defense_state.get("attacker_ip")),
             "siem alerts   then   siem investigate 1"),
            ("Block the attacker IP at the firewall",
             either(lambda w, s: bool(w.defense_state.get("blocked_ips")),
                    ran("ufw", "deny")),
             "incident contain <attacker-ip>   (or: ufw deny from <ip>)"),
        ],
        "xp_reward": 90,
    },
    {
        "id": "soc02",
        "title": "Triage the Queue",
        "category": "blue team: SOC — triage",
        "difficulty": 2,
        "tags": ["BLUE TEAM", "DEFENSIVE", "SOC", "MEDIUM"],
        "story": (
            "Five alerts, one analyst, and a manager who wants the queue clean "
            "by lunch. Not everything is an emergency — some of it is the "
            "nightly backup. Work the SIEM like a pro: size up the board, dig "
            "into the worst one, clear the noise, and escalate what's real. "
            "Triage is judgement, not clicking everything red."
        ),
        "steps": [
            ("Open the SIEM dashboard to size up the queue",
             ran("siem"),
             "siem dashboard   (then: siem alerts)"),
            ("Investigate the most severe alert",
             lambda w, s: len(w.defense_state.get("alerts_investigated", [])) > 0,
             "siem investigate 1"),
            ("Close a benign / false-positive alert",
             lambda w, s: len(w.defense_state.get("alerts_acked", [])) > 0,
             "siem ack 5   (the scheduled backup is benign)"),
            ("Escalate the confirmed intrusion to an incident",
             lambda w, s: bool(w.defense_state.get("incident_open")),
             "siem escalate 1"),
        ],
        "xp_reward": 100,
    },
    {
        "id": "soc03",
        "title": "Reconstruct the Kill Chain",
        "category": "blue team: SOC — threat intel",
        "difficulty": 3,
        "tags": ["BLUE TEAM", "DEFENSIVE", "SOC", "HARD"],
        "story": (
            "The incident is open — now turn raw logs into intelligence. Pull "
            "out the indicators of compromise, lay the events on a timeline so "
            "the story reads start-to-finish, and package the IOCs so the rest "
            "of the team (and the next victim) can hunt for the same actor. "
            "Good threat intel is what stops the second breach."
        ),
        "steps": [
            ("Record the attacker's IP as an IOC",
             _ip_ioc,
             "ioc add <attacker-ip>"),
            ("Record the breached account as a second IOC",
             lambda w, s: len(w.defense_state.get("iocs", [])) >= 2,
             "ioc add deploy  compromised-account"),
            ("Reconstruct the attack timeline (at least 2 events)",
             lambda w, s: len(w.defense_state.get("timeline", [])) >= 2,
             'incident add "02:11 SSH brute force from attacker"'),
            ("Export your indicators for the threat-intel platform",
             ran("ioc", "export"),
             "ioc export"),
        ],
        "xp_reward": 120,
    },
    {
        "id": "soc04",
        "title": "Write the Incident Report",
        "category": "blue team: SOC — incident response",
        "difficulty": 3,
        "tags": ["BLUE TEAM", "DEFENSIVE", "SOC", "HARD"],
        "story": (
            "The fire's out — but it didn't happen until it's written down. "
            "Confirm containment, record what you did, generate the incident "
            "report management will actually read, then re-audit the box to "
            "prove it's harder than it was this morning. Detection to recovery, "
            "the full loop. This is the job."
        ),
        "steps": [
            ("Confirm the attacker is contained",
             either(lambda w, s: bool(w.defense_state.get("blocked_ips")),
                    ran("ufw", "deny")),
             "incident contain <attacker-ip>"),
            ("Capture your response actions in the timeline",
             lambda w, s: len(w.defense_state.get("timeline", [])) > 0,
             'incident add "03:00 blocked attacker, reset deploy account"'),
            ("Generate the incident report",
             lambda w, s: bool(w.defense_state.get("report_done")),
             "incident report"),
            ("Re-audit the host to verify it's hardened",
             ran("lynis"),
             "lynis audit system"),
        ],
        "xp_reward": 140,
    },
]
