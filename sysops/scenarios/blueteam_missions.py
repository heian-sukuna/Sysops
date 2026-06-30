"""
scenarios/blueteam_missions.py — Blue-team / defensive missions.

Host hardening, firewalling, brute-force protection, and seeing your own box
the way an attacker does. Step checks follow the project convention: verify
real world state where it changes, otherwise confirm the command actually ran
via scenarios.checks (never `lambda w, s: True`).

All commands used here are handled by modules/cybersec.py:
    ufw {status,allow,deny,enable,reload}, fail2ban-client status <jail>,
    lynis audit system, nmap, tshark.
"""

from scenarios.checks import ran, ran_any

BLUETEAM_MISSIONS = [
    {
        "id": "bt01",
        "title": "Harden the Box",
        "category": "blue team: hardening",
        "difficulty": 2,
        "tags": ["BLUE TEAM", "HARDENING", "FIREWALL", "MEDIUM"],
        "story": (
            "You just inherited a fresh Ubuntu server that's wide open to the "
            "internet. Before it gets popped, lock it down: audit it to see "
            "where it's weak, allow only the traffic you actually need, drop "
            "the legacy junk, switch the firewall on, and confirm brute-force "
            "protection is watching SSH. Audit first, fix, then re-verify — "
            "that loop is the whole job."
        ),
        "steps": [
            ("Run a baseline security audit to find the weak spots",
             ran("lynis"),
             "lynis audit system"),
            ("Allow inbound SSH so you don't lock yourself out",
             ran("ufw", "allow"),
             "ufw allow 22"),
            ("Deny legacy Telnet (port 23) — it's plaintext and must die",
             ran("ufw", "deny"),
             "ufw deny 23"),
            ("Turn the firewall on",
             ran("ufw", "enable"),
             "ufw enable"),
            ("Confirm fail2ban is actively guarding the sshd jail",
             ran("fail2ban", "status"),
             "fail2ban-client status sshd"),
        ],
        "xp_reward": 90,
    },
    {
        "id": "bt02",
        "title": "Attacker's-Eye View",
        "category": "blue team: detection",
        "difficulty": 2,
        "tags": ["BLUE TEAM", "RECON", "DETECTION", "MEDIUM"],
        "story": (
            "You can't defend what you can't see. Scan your own host the way an "
            "outsider would to find exposed services, watch the wire for "
            "anything noisy, slam the door on a port that has no business being "
            "open, then re-audit to prove the hardening index actually moved."
        ),
        "steps": [
            ("Scan your own host to see what services are exposed",
             ran("nmap"),
             "nmap -sV localhost"),
            ("Capture live traffic to spot suspicious chatter",
             ran_any("tshark", "wireshark", "tcpdump"),
             "tshark -c 50"),
            ("Block an exposed database port (MySQL/3306) at the firewall",
             ran("ufw", "deny"),
             "ufw deny 3306"),
            ("Re-run the audit and confirm the box is harder than before",
             ran("lynis"),
             "lynis audit system"),
        ],
        "xp_reward": 80,
    },
]
