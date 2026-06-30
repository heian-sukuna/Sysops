# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

SYSOPS is a terminal-based sysadmin/cybersecurity training game. The player types simulated Linux commands in a REPL — none touch the real system. Missions guide them through tools like rsync, docker, nmap, and git. Progress is saved between sessions.

## Running the Game

```bash
# From the project root (no install needed)
python3 -m sysops

# Or install a launcher to ~/.local/bin first
python3 install.py
sysops
```

No external dependencies — stdlib only.

## Architecture

The game has three layers that communicate in one direction: **REPL → Modules → World/Save**.

```
sysops/__main__.py       Entry point; wires up SaveManager, VirtualWorld, ScenarioEngine, GameREPL
core/repl.py             GameREPL — main input loop, dispatches typed commands
core/world.py            VirtualWorld — all mutable simulated state (network, fs, docker, etc.)
core/save.py             SaveManager — reads/writes ~/.sysops/save.json; owns XP/level logic
core/ui.py               Visual engine — ANSI colors, box drawing, themes, ASCII banner fonts
core/menu.py             Pre-game screens: main menu, new-game wizard, options, achievements

modules/transfer.py      ssh, rsync, tailscale, ping
modules/containers.py    docker, docker-compose, nginx
modules/networking.py    netstat, ss, ip, ifconfig, dig, curl, traceroute, arp, nload, iftop
modules/cybersec.py      nmap, tshark, gobuster, nikto, hydra, hashcat, ufw, fail2ban, lynis, shodan
modules/git.py           git (full subcommand coverage)
modules/redteam.py       theHarvester, amass, searchsploit, msfvenom, msfconsole, sqlmap, linpeas, etc.
modules/architecture.py  terraform/tf, diagram (IaC workflow + topology visualization)
modules/defense.py       journalctl, grep, last, who, siem, ioc, incident (blue-team/SOC analyst tools)

scenarios/missions.py              SCENARIOS list + QUICK_CHALLENGES; imports & appends the pillar files below
scenarios/git_redteam_missions.py  Git and red-team pillar missions (GIT_MISSIONS, REDTEAM_MISSIONS)
scenarios/architecture_missions.py Architecture/IaC pillar missions (ARCH_MISSIONS)
scenarios/blueteam_missions.py     Blue-team/hardening pillar missions (BLUETEAM_MISSIONS)
scenarios/soc_missions.py          Blue-team/SOC detection & IR pillar missions (SOC_MISSIONS)
scenarios/checks.py                Step-check predicate helpers (ran/ran_any/ran_re/either)
scenarios/engine.py                ScenarioEngine — runs missions, checks step completion, awards XP
```

New pillar missions are added in their own `*_missions.py` file and appended to
`SCENARIOS` at the bottom of `missions.py`. Step checks must verify the player
actually ran the command (use `scenarios/checks.py`) — never `lambda w, s: True`.

### Key data contracts

**VirtualWorld** holds all runtime state. It is constructed from `save.data["world"]` at startup and serialized back via `world.to_dict()` before every save. Modules receive `(world, save)` at construction and mutate `world` to reflect command effects.

The blue-team/SOC simulation lives in `world.defense_state` (persisted IR progress: confirmed attacker IP, triaged/acked/escalated alert ids, IOCs, timeline, blocked IPs, report flag) plus `world.logs` and `world.siem_alerts` (regenerated each session from the persisted `attacker_ip` by `_build_soc_environment`, like `listening_ports`). The DefenseModule reads the logs/alerts and writes player progress into `defense_state`; SOC mission steps verify that progress. Keep the logs, the SIEM alerts, and the IOCs telling **one** consistent intrusion story.

**Missions** are plain dicts:
```python
{
    "id": "ts01",
    "title": "...",
    "category": "tailscale + rsync",
    "difficulty": 1,        # 1–4
    "tags": ["TAILSCALE"],
    "story": "...",
    "steps": [
        ("Description", lambda w, s: <bool check>, "hint text"),
    ],
    "xp_reward": 60,
}
```
`ScenarioEngine.check_after_command()` is called after every REPL command; it evaluates the current step's lambda against `(world, save)` to auto-advance.

**Save file** is `~/.sysops/save.json` — a flat dict merged over `DEFAULT_PROFILE` on load. The nested `"world"` key is merged separately to preserve defaults for new fields.

### Adding a new command

1. Pick the appropriate module in `modules/`.
2. Add a method there that reads/mutates `self.w` (VirtualWorld) and calls `self.s.add_xp(...)` if warranted.
3. Wire the command name → method call in `GameREPL._dispatch()` in `core/repl.py`.
4. Add a help entry to `GameREPL._full_help()`.

### Adding a new mission

Add a dict to `SCENARIOS` in `scenarios/missions.py` (or `git_redteam_missions.py` for git/red-team). Step check functions receive `(world: VirtualWorld, save: SaveManager)` and must return bool without side effects.
