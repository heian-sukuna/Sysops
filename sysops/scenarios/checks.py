"""
scenarios/checks.py — Step-check predicate helpers for missions.

Mission steps are (description, check_fn(world, save) -> bool, hint). Many
steps don't change persistent world state (running `docker logs`, `nikto`,
`git log` …), so they used to be written as `lambda w, s: True`, which let a
step pass on *any* command. These helpers verify the player actually ran the
right command by inspecting `world.cmd_log` — the list of raw commands typed
during the current mission attempt (reset when a mission starts).

Usage in a mission step:

    ("View the container logs", ran("docker", "logs"), "docker logs webserver")
    ("Enumerate web directories", ran("gobuster"), "gobuster dir -u ..."),
"""

import re


def _norm(s):
    """Lowercase + collapse whitespace so 'git   log' == 'git log'."""
    return " ".join(str(s).lower().split())


def ran(*needles):
    """Pass once the player has run a command containing ALL the given
    substrings (case-insensitive, whitespace-normalized) in one command.

        ran("docker", "logs")  → matches  "docker logs webserver"
        ran("nginx test")      → matches  "nginx test"
    """
    wants = [_norm(n) for n in needles]

    def check(w, s):
        for raw in getattr(w, "cmd_log", []):
            c = _norm(raw)
            if all(n in c for n in wants):
                return True
        return False

    return check


def ran_any(*needles):
    """Pass if ANY one of the given substrings appears in any run command."""
    wants = [_norm(n) for n in needles]

    def check(w, s):
        for raw in getattr(w, "cmd_log", []):
            c = _norm(raw)
            if any(n in c for n in wants):
                return True
        return False

    return check


def ran_re(pattern):
    """Pass if any run command matches the given regular expression."""
    rx = re.compile(pattern, re.IGNORECASE)

    def check(w, s):
        return any(rx.search(raw) for raw in getattr(w, "cmd_log", []))

    return check


def either(*checks):
    """Pass if any of the given check functions passes (compose predicates)."""
    def check(w, s):
        return any(fn(w, s) for fn in checks)

    return check
