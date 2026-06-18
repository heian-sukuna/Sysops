"""
tests/test_sysops.py — Safety-net unit tests for SYSOPS (stdlib unittest).

Run from the project root:
    python3 -m unittest discover -s tests -v
    python3 tests/test_sysops.py

These cover the pure logic that the rest of the game depends on: XP/levels,
world serialization, ANSI-aware UI width math, the mission command-verification
predicates, and the integrity of every mission definition.
"""

import os
import sys
import unittest

# Make the sysops package importable when run from the project root.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "sysops"))

from core.save import (level_for_xp, xp_to_next, XP_PER_LEVEL, LEVEL_TITLES,
                       DIFF_NAMES, SaveManager)

# Redirect all save I/O to a throwaway temp dir so tests NEVER touch the
# player's real ~/.sysops/save.json.
import tempfile
import core.save as _save_mod
from pathlib import Path
_TMP = Path(tempfile.mkdtemp(prefix="sysops_test_"))
_save_mod.SAVE_DIR = _TMP
_save_mod.SAVE_FILE = _TMP / "save.json"
_save_mod.LOG_FILE = _TMP / "session.log"
from core.world import VirtualWorld
from core import ui
from scenarios.checks import ran, ran_any, ran_re, either
from scenarios.missions import SCENARIOS, QUICK_CHALLENGES, get_scenario


def _fresh_save():
    s = SaveManager()
    s.new_game("tester", "box", "user@host", 2)
    return s


def _rich_world():
    """A world with essentially every state flag set / artifact present, used to
    prove mission step-checks actually respond to world state (and aren't
    constant-true placeholders)."""
    w = VirtualWorld({})
    w.bring_tailscale_up()
    w.ssh_key_exists = True
    w.ssh_keys_copied = {"server", "nas", "pi"}
    w.docker_images = ["nginx", "sysops-app:v1", "sysops-app"]
    w.docker_containers = {
        "webserver": {"image": "nginx", "status": "running"},
        "nginx":     {"image": "nginx", "status": "running"},
        "frontend":  {"image": "frontend", "status": "running"},
        "backend":   {"image": "backend", "status": "running"},
        "target":    {"image": "nginx", "status": "running"},
        "myapp":     {"image": "sysops-app:v1", "status": "running"},
    }
    w.nginx_running = True
    w.nginx_configs = {"sukuna-portfolio": "server { }"}
    w.generate_scan("100.64.1.20")
    w.captured_packets = [{"n": i} for i in range(30)]
    w.git_repos = {
        "sukuna-portfolio": {
            "branch": "main",
            "branches": ["main", "feature/navbar"],
            "staged": True,
            "remotes": {"origin": "git@github.com:x/y.git"},
            "tags": ["v1.0.0"],
            "stashes": ["WIP"],
            "commits": [
                {"msg": "initial commit", "pushed": True},
                {"msg": "Merge feature/navbar", "pushed": True},
                {"msg": "Revert bad", "pushed": True},
                {"msg": "chore: update Dockerfile for production", "pushed": True},
            ],
        }
    }
    w.fs.setdefault("server", {}).update({
        "/etc/nginx/sites-enabled/sukuna-portfolio": {"size_mb": 0, "type": "file"},
        "/home/user/backups/report.pdf": {"size_mb": 2.4, "type": "file"},
        "/mnt/storage/demo.mp4": {"size_mb": 850, "type": "file"},
        "/mnt/storage/archive.tar.gz": {"size_mb": 3200, "type": "file"},
    })
    w.rt_state.update({
        "emails": ["admin@sukuna-corp.local"],
        "subdomains": [f"s{i}.sukuna-corp.local" for i in range(6)],
        "loot": ["/etc/shadow (hashdump)", "NTLMv2 hash: admin",
                 "Database dump: users table"],
        "exploited": True,
        "privesc_done": True,
        "listener_up": True,
    })
    return w


class TestSave(unittest.TestCase):
    def test_level_for_xp_boundaries(self):
        self.assertEqual(level_for_xp(0), 1)
        self.assertEqual(level_for_xp(99), 1)
        self.assertEqual(level_for_xp(100), 2)
        self.assertEqual(level_for_xp(249), 2)
        self.assertEqual(level_for_xp(250), 3)
        self.assertEqual(level_for_xp(10_000_000), len(XP_PER_LEVEL))

    def test_level_titles_cover_all_levels(self):
        for xp in (0, 100, 250, 9999, 999999):
            lvl = level_for_xp(xp)
            # min(lvl, len-1) is how the game indexes — must not IndexError
            LEVEL_TITLES[min(lvl, len(LEVEL_TITLES) - 1)]

    def test_xp_to_next_decreases(self):
        self.assertEqual(xp_to_next(0), 100)
        self.assertEqual(xp_to_next(60), 40)

    def test_add_xp_returns_level_delta(self):
        s = _fresh_save()
        self.assertEqual(s.get("xp"), 0)
        self.assertEqual(s.add_xp(50, "t"), 0)      # no level up yet
        self.assertEqual(s.add_xp(60, "t"), 1)      # crossed 100 -> level 2
        self.assertEqual(s.get("xp"), 110)

    def test_diff_names(self):
        self.assertEqual(DIFF_NAMES[1], "Easy")
        self.assertEqual(DIFF_NAMES[4], "Nightmare")

    def test_complete_scenario_dedups(self):
        s = _fresh_save()
        s.complete_scenario("ts01")
        s.complete_scenario("ts01")
        self.assertEqual(s.get("completed_scenarios").count("ts01"), 1)

    def test_grant_achievement_once(self):
        s = _fresh_save()
        self.assertTrue(s.grant_achievement("a", "desc"))
        self.assertFalse(s.grant_achievement("a", "desc"))


class TestWorld(unittest.TestCase):
    def test_to_dict_roundtrip(self):
        w = VirtualWorld({})
        w.tailscale_up = True
        w.docker_images.append("nginx")
        d = w.to_dict()
        w2 = VirtualWorld({"world": d})
        self.assertTrue(w2.tailscale_up)
        self.assertIn("nginx", w2.docker_images)

    def test_cmd_log_exists_and_not_serialized(self):
        w = VirtualWorld({})
        self.assertEqual(w.cmd_log, [])
        w.cmd_log.append("nmap -sV x")
        self.assertNotIn("cmd_log", w.to_dict())   # session-only

    def test_generate_scan_structure(self):
        w = VirtualWorld({})
        r = w.generate_scan("100.64.1.20")
        self.assertEqual(r["ip"], "100.64.1.20")
        self.assertTrue(r["ports"])
        self.assertIn("100.64.1.20", w.known_hosts)

    def test_peer_online(self):
        w = VirtualWorld({})
        self.assertFalse(w.peer_online("server"))
        w.bring_tailscale_up()
        self.assertTrue(w.peer_online("server"))


class TestUI(unittest.TestCase):
    def test_strip_and_vlen(self):
        s = ui.cyan("hello")
        self.assertEqual(ui.strip_ansi(s), "hello")
        self.assertEqual(ui.vlen(s), 5)

    def test_wrap_ansi_no_overflow(self):
        line = "  " + ui.DIM + ("word " * 40).strip() + ui.R
        for seg in ui.wrap_ansi(line, 50):
            self.assertLessEqual(ui.vlen(seg), 50)

    def test_wrap_ansi_preserves_style_and_indent(self):
        line = "  " + ui.DIM + ("alpha " * 30).strip() + ui.R
        segs = ui.wrap_ansi(line, 40)
        self.assertGreater(len(segs), 1)
        self.assertTrue(segs[0].startswith("  "))       # indent kept
        self.assertIn(ui.DIM, segs[0])                  # style kept

    def test_wrap_ansi_short_line_untouched(self):
        line = ui.cyan("short")
        self.assertEqual(ui.wrap_ansi(line, 40), [line])


class TestChecks(unittest.TestCase):
    def setUp(self):
        self.w = VirtualWorld({})
        self.s = _fresh_save()

    def test_ran_requires_all_substrings(self):
        check = ran("docker", "logs")
        self.assertFalse(check(self.w, self.s))
        self.w.cmd_log.append("docker ps")
        self.assertFalse(check(self.w, self.s))     # missing "logs"
        self.w.cmd_log.append("docker logs web")
        self.assertTrue(check(self.w, self.s))

    def test_ran_is_whitespace_insensitive(self):
        self.w.cmd_log.append("git    log   --oneline")
        self.assertTrue(ran("git log")(self.w, self.s))

    def test_ran_does_not_falsely_pass_on_other_command(self):
        self.w.cmd_log.append("ls -la")
        self.assertFalse(ran("nikto")(self.w, self.s))

    def test_ran_any(self):
        check = ran_any("ss", "netstat")
        self.w.cmd_log.append("netstat -tulnp")
        self.assertTrue(check(self.w, self.s))

    def test_ran_re(self):
        check = ran_re(r"tshark.*-r")
        self.w.cmd_log.append("tshark -r http.pcap")
        self.assertTrue(check(self.w, self.s))

    def test_either(self):
        check = either(ran("foo"), ran("bar"))
        self.w.cmd_log.append("bar baz")
        self.assertTrue(check(self.w, self.s))


class TestMissions(unittest.TestCase):
    def test_unique_ids(self):
        ids = [sc["id"] for sc in SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)), "duplicate mission ids")

    def test_required_fields(self):
        for sc in SCENARIOS:
            for key in ("id", "title", "category", "difficulty", "steps", "xp_reward"):
                self.assertIn(key, sc, f"{sc.get('id')} missing {key}")
            self.assertIn(sc["difficulty"], (1, 2, 3, 4))
            self.assertGreater(sc["xp_reward"], 0)

    def test_all_step_checks_callable_and_safe(self):
        """Every step check must be callable and not raise / mutate on a fresh world."""
        for sc in SCENARIOS:
            w = VirtualWorld({})
            s = _fresh_save()
            for desc, fn, hint in sc["steps"]:
                self.assertTrue(callable(fn), f"{sc['id']}: {desc} not callable")
                result = fn(w, s)
                self.assertIn(result, (True, False), f"{sc['id']}: {desc} non-bool")

    def test_no_constant_true_steps(self):
        """No step check may be a constant 'lambda: True' placeholder (the
        teaching-loop fix). A genuine check distinguishes *some* world state —
        it returns True on a richly-populated world but False on an empty one,
        OR vice-versa for legitimate negative/removal checks. A check that is
        True on BOTH an empty world and a fully-populated one ignores the
        player entirely and is leaky."""
        rich_log = [hint for sc in SCENARIOS for _, _, hint in sc["steps"]]
        leaky = []
        for sc in SCENARIOS:
            for desc, fn, hint in sc["steps"]:
                empty = VirtualWorld({})
                rich = _rich_world()
                rich.cmd_log = list(rich_log)          # every hint "typed"
                if fn(empty, _fresh_save()) is True and fn(rich, _fresh_save()) is True:
                    leaky.append(f"{sc['id']}: {desc!r}")
        self.assertEqual(leaky, [], "constant-true (leaky) steps remain:\n" + "\n".join(leaky))

    def test_quick_challenges_wellformed(self):
        for q in QUICK_CHALLENGES:
            self.assertTrue(q["answers"])
            self.assertGreater(q["xp"], 0)


class TestEngineAdvance(unittest.TestCase):
    def test_check_after_command_advances_and_completes(self):
        from scenarios.engine import ScenarioEngine
        w = VirtualWorld({})
        s = _fresh_save()
        eng = ScenarioEngine(w, s)
        # Synthetic 1-step mission verified by a real command.
        eng.active = {
            "id": "zzz_test", "title": "T", "category": "test",
            "difficulty": 1, "tags": [], "story": "",
            "steps": [("run nmap", ran("nmap"), "nmap x")],
            "xp_reward": 10,
        }
        eng.step_idx = 0
        eng.check_after_command()                 # nothing run yet
        self.assertEqual(eng.step_idx, 0)
        w.cmd_log.append("nmap -sV 100.64.1.20")
        eng.check_after_command()                 # satisfied -> completes
        self.assertIsNone(eng.active)
        self.assertIn("zzz_test", s.get("completed_scenarios"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
