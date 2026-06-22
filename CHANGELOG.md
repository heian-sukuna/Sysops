# Changelog

All notable changes to SYSOPS are documented here.
The format is loosely based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
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

### Changed
- README: mission count corrected (28 → **32**), added the **Architecture**
  (`terraform`, `diagram`) and **Blue team** rows to command coverage, and
  listed the per-pillar mission files in the project structure.
- `CLAUDE.md`: documented the `architecture` module and the
  `architecture_missions` / `blueteam_missions` files.

### Removed
- Stray empty directories left over from a failed `mkdir` brace expansion
  (`sysops/{core,modules,scenarios,data}`, `sysops/{modules,scenarios,data}`,
  empty `sysops/data`).

### Notes
- Total content: **32 missions** across the Transfer, Containers/Web,
  Networking, Security, Git, Red-team, Architecture, and Blue-team pillars,
  plus **8 quick-challenge** drills. All 27 unit tests pass.
