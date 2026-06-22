# Contributing to SYSOPS

Thanks for wanting to make SYSOPS better! It's pure-Python, zero-dependency,
and easy to extend. This guide covers the two most common contributions:
adding a **mission** and adding a **command**.

## Ground rules

- **Standard library only.** No `pip` dependencies — ever. The "zero
  dependencies" promise is a feature.
- **Nothing touches the real system.** Every command is *simulated*. Don't add
  code that runs real subprocesses, opens sockets, or sends network traffic.
- **Keep red-team tools fictional.** Offensive commands (`nmap`, `hydra`,
  `sqlmap`, …) print realistic-but-fake output for learning syntax/concepts.
- Run the tests before opening a PR (see below). CI runs them on Python
  3.8–3.13.

## Setup

```bash
git clone https://github.com/heian-sukuna/Sysops.git
cd Sysops
python3 -m sysops                 # play it
python3 -m unittest discover -s tests -v   # run the suite
```

No virtualenv or install needed.

## Architecture in one breath

One-directional: **REPL → Modules → World/Save**.

- `sysops/core/repl.py` — reads input, dispatches commands.
- `sysops/modules/*.py` — one file per tool family; methods mutate the world.
- `sysops/core/world.py` — all simulated state.
- `sysops/core/save.py` — XP, levels, persistence (`~/.sysops/save.json`).
- `sysops/scenarios/*` — missions and the engine that checks them.

See [`CLAUDE.md`](CLAUDE.md) for the full data contracts.

## Adding a mission

Missions are plain dicts. Pillar missions live in their own file
(`git_redteam_missions.py`, `architecture_missions.py`, `blueteam_missions.py`);
core ones live in `missions.py`. To add a new pillar, create a file that
exports a list and append it in `missions.py`:

```python
from scenarios.your_missions import YOUR_MISSIONS
SCENARIOS = SCENARIOS + ... + YOUR_MISSIONS
```

A mission:

```python
{
    "id": "bt03",                         # unique, lowercase
    "title": "Catch the Intruder",
    "category": "blue team: detection",
    "difficulty": 3,                      # 1 Easy .. 4 Nightmare
    "tags": ["BLUE TEAM", "HARD"],
    "story": "What the player is trying to do, in-world.",
    "steps": [
        ("Description shown to the player", check_fn, "hint text"),
    ],
    "xp_reward": 100,
}
```

**Verify the player actually ran the command.** Don't use `lambda w, s: True`.
Use the helpers in [`scenarios/checks.py`](sysops/scenarios/checks.py):

```python
from scenarios.checks import ran, ran_any, ran_re, either

("Block the port at the firewall", ran("ufw", "deny"), "ufw deny 3306"),
```

If a step changes real world state, check that instead:

```python
("Provision the infra", lambda w, s: len(w.tf_state.get("applied", [])) > 0, "terraform apply"),
```

Then make sure your hints reference commands the simulator actually handles
(grep the relevant `modules/*.py`).

## Adding a command

1. Add a method to the right `modules/*.py` that reads/mutates `self.w`
   (the `VirtualWorld`) and awards XP via `self.s.add_xp(...)` if warranted.
2. Wire the command name to it in `GameREPL._dispatch()` in `core/repl.py`.
3. Add a help entry in `GameREPL._full_help()` and to the `COMMANDS`
   completion list.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Add or update tests in `tests/test_sysops.py` for new save/world/UI logic.
For missions, a quick local check is enough:

```python
from scenarios.missions import get_scenario
class W: cmd_log = ["ufw deny 3306"]
m = get_scenario("bt03")
assert m["steps"][0][1](W(), None)
```

Open a PR with a clear description. Happy hacking! 🛡️
