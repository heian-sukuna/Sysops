# Changelog

All notable changes to SYSOPS are documented here.
The format is loosely based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Blue-team / SOC module** (`modules/defense.py`): a full defensive analyst
  toolkit, the counterpart to the red-team module. New simulated commands —
  - `journalctl` (service-log review with `-u`/`-p`/`-g`/`-n`/`-f`),
  - `grep` over the simulated `/var/log` files, `last`, `who`,
  - `siem` — an alert queue with `dashboard`/`alerts`/`investigate`/`ack`/`escalate`,
  - `ioc` — indicator collection (`add`/`list`/`export`, auto-classifies
    ip/hash/domain/email/user),
  - `incident` — NIST 800-61 workflow (`status`/`timeline`/`add`/`contain`/`report`).
- **SOC mission pillar** (`scenarios/soc_missions.py`): four detection-and-response
  missions over one self-consistent intrusion baked into the host logs (an
  external host brute-forces SSH, lands on the `deploy` account, escalates via
  `sudo`, and scans the web app) —
  - `soc01` *Catch the Brute Force* — find it in the logs, confirm the IP, block it.
  - `soc02` *Triage the Queue* — work the SIEM, close benign, escalate the real one.
  - `soc03` *Reconstruct the Kill Chain* — build IOCs + an attack timeline, export.
  - `soc04` *Write the Incident Report* — contain, report, re-audit.
- **`defense` focus module** — selectable in the new-game wizard and Options, with
  its own mission filter, cheatsheet, and `help defense` reference card.
- Three SIEM/IR achievements (First Responder, Threat Tracker, Containment) plus
  Incident Handler, and 10 new unit tests (`TestDefense`, `TestSocMissions`).

- **Blue-team mission pillar** (`scenarios/blueteam_missions.py`): two new
  defensive missions —
  - `bt01` *Harden the Box* — audit → firewall → fail2ban hardening loop
    (`lynis`, `ufw allow/deny/enable`, `fail2ban-client`).
  - `bt02` *Attacker's-Eye View* — self-scan, traffic capture, close exposed
    ports, re-audit (`nmap`, `tshark`, `ufw`, `lynis`).
- **Continuous integration** (`.github/workflows/ci.yml`): runs the unittest
  suite plus a package smoke-import and a mission-schema/duplicate-id check on
  Python 3.8 – 3.13.
- `CONTRIBUTING.md` with the add-a-mission / add-a-command workflow.
- This `CHANGELOG.md`.

### Performance
- **Snappier Tab completion** (`core/repl.py`): the readline completer now builds
  its candidate list once per Tab press and caches it, instead of rebuilding,
  re-importing `SCENARIOS`, re-scanning the simulated filesystem, and re-sorting
  on every `state` call readline makes. The static mission-id list is memoized.
- **Faster `missions` / `missions all` / combo screen** (`scenarios/engine.py`):
  `_unlocked_ids()` (which scans every scenario) was being recomputed once per
  rendered row — O(n²) in the mission count. It is now computed a single time and
  passed down, making the listings O(n).

### Changed
- README: mission count updated (32 → **36**), folded the **Blue team / SOC**
  tooling into command coverage, and listed `defense.py` / `soc_missions.py`
  in the project structure.
- `CLAUDE.md`: documented the `architecture` module and the
  `architecture_missions` / `blueteam_missions` / `soc_missions` files, plus the
  `defense` module and its `defense_state` world contract.

### Removed
- Stray empty directories left over from a failed `mkdir` brace expansion
  (`sysops/{core,modules,scenarios,data}`, `sysops/{modules,scenarios,data}`,
  empty `sysops/data`).

### Notes
- Total content: **36 missions** across the Transfer, Containers/Web,
  Networking, Security, Git, Red-team, Architecture, and Blue-team/SOC pillars,
  plus **8 quick-challenge** drills. All 37 unit tests pass.
