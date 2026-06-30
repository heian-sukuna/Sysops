"""
core/save.py — Persistent save system for SYSOPS
Stores everything in ~/.sysops/save.json
"""

import os, json, time, hashlib, copy
from pathlib import Path

SAVE_DIR  = Path.home() / ".sysops"
SAVE_FILE = SAVE_DIR / "save.json"
LOG_FILE  = SAVE_DIR / "session.log"

DEFAULT_PROFILE = {
    "version": 3,
    "created": 0,
    "last_played": 0,
    "playtime_seconds": 0,

    # Identity
    "username": "user",
    "hostname": "server",
    "prompt_style": "user@host",   # or host@user or custom
    "prompt_custom": "",

    # Progress
    "xp": 0,
    "level": 1,
    "total_commands": 0,
    "total_mistakes": 0,
    "completed_scenarios": [],
    "completed_missions": [],
    "unlocked_modules": ["basics", "rsync", "tailscale", "ssh"],

    # Settings
    "difficulty": 2,              # 1=easy 2=medium 3=hard 4=nightmare
    "hints_enabled": True,
    "anim_speed": "cinematic",    # cinematic | fast | instant
    "color_theme": "cyberpunk",
    "banner_font": "block",

    # World state (persisted between sessions)
    "world": {
        "tailscale_up": False,
        "ssh_key_exists": False,
        "ssh_keys_copied": [],
        "docker_images": [],
        "docker_containers": {},
        "docker_networks": ["bridge", "host", "none"],
        "docker_volumes": [],
        "nginx_configs": {},
        "known_hosts": {},          # from nmap scans
        "captured_packets": [],     # from wireshark sessions
        "attacker_ip": None,        # SOC: fixed intruder IP for the host logs
        "defense_state": {},        # SOC: triage / IOC / IR progress
    },

    # Achievement flags
    "achievements": [],

    # Focus module (last selected in Options)
    "focus_module": None,

    # Command history (last 100)
    "history": [],
}

DIFF_NAMES = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Nightmare"}

XP_PER_LEVEL = [0, 100, 250, 500, 900, 1400, 2100, 3000, 4200, 6000, 9999]
LEVEL_TITLES = [
    "", "Initiate", "Script Kiddie", "Sysadmin Cadet", "Net Engineer",
    "Security Analyst", "Red Team Operator", "Network Architect",
    "Threat Hunter", "Elite Operator", "SYSOPS Master"
]

def level_for_xp(xp):
    for i, threshold in enumerate(XP_PER_LEVEL):
        if xp < threshold:
            return max(1, i)
    return len(XP_PER_LEVEL)

def xp_to_next(xp):
    lvl = level_for_xp(xp)
    if lvl >= len(XP_PER_LEVEL):
        return 0
    return XP_PER_LEVEL[lvl] - xp

class SaveManager:
    def __init__(self):
        self.data = None
        self._session_start = time.time()

    def exists(self):
        return SAVE_FILE.exists()

    def new_game(self, username, hostname, prompt_style, difficulty):
        self.data = copy.deepcopy(DEFAULT_PROFILE)
        self.data["created"] = int(time.time())
        self.data["last_played"] = int(time.time())
        self.data["username"] = username
        self.data["hostname"] = hostname
        self.data["prompt_style"] = prompt_style
        self.data["difficulty"] = difficulty
        # difficulty adjusts starting unlocks
        if difficulty <= 1:
            self.data["hints_enabled"] = True
            self.data["unlocked_modules"] = [
                "basics","rsync","tailscale","ssh","docker",
                "networking","nginx","cybersec","combo"
            ]
        self.save()

    def load(self):
        try:
            with open(SAVE_FILE) as f:
                saved = json.load(f)
            self.data = copy.deepcopy(DEFAULT_PROFILE)
            self.data.update(saved)
            # merge nested world
            world = copy.deepcopy(DEFAULT_PROFILE["world"])
            world.update(saved.get("world", {}))
            self.data["world"] = world
            self.data["last_played"] = int(time.time())
            return True
        except Exception as e:
            return False

    def save(self):
        SAVE_DIR.mkdir(exist_ok=True)
        if self.data:
            elapsed = int(time.time() - self._session_start)
            self.data["playtime_seconds"] = self.data.get("playtime_seconds", 0) + elapsed
            self._session_start = time.time()
            self.data["last_played"] = int(time.time())
            # update level
            self.data["level"] = level_for_xp(self.data["xp"])
            with open(SAVE_FILE, "w") as f:
                json.dump(self.data, f, indent=2)

    def delete(self):
        if SAVE_FILE.exists():
            SAVE_FILE.unlink()
        self.data = None

    # ── Convenience accessors ─────────────────────────────────────────────

    def get(self, key, default=None):
        return self.data.get(key, default) if self.data else default

    def set(self, key, value):
        if self.data:
            self.data[key] = value

    def world(self):
        return self.data["world"] if self.data else {}

    def add_xp(self, pts, reason=""):
        if not self.data: return 0
        old_level = level_for_xp(self.data["xp"])
        self.data["xp"] += pts
        new_level = level_for_xp(self.data["xp"])
        self.log(f"XP +{pts} ({reason})")
        return new_level - old_level   # >0 means levelled up

    def add_command(self, cmd):
        if not self.data: return
        self.data["total_commands"] += 1
        h = self.data.setdefault("history", [])
        h.append(cmd)
        if len(h) > 100:
            h.pop(0)

    def complete_scenario(self, sid):
        if not self.data: return
        if sid not in self.data["completed_scenarios"]:
            self.data["completed_scenarios"].append(sid)

    def complete_mission(self, mid):
        if not self.data: return
        if mid not in self.data["completed_missions"]:
            self.data["completed_missions"].append(mid)

    def unlock_module(self, mod):
        if not self.data: return
        mods = self.data.setdefault("unlocked_modules", [])
        if mod not in mods:
            mods.append(mod)

    def grant_achievement(self, name, desc):
        if not self.data: return False
        achs = self.data.setdefault("achievements", [])
        if name not in [a["name"] for a in achs]:
            achs.append({"name": name, "desc": desc, "ts": int(time.time())})
            return True
        return False

    def prompt_str(self):
        if not self.data:
            return "user@host:~$ "
        u = self.data["username"]
        h = self.data["hostname"]
        style = self.data["prompt_style"]
        custom = self.data.get("prompt_custom", "")
        if style == "user@host":
            return f"{u}@{h}"
        elif style == "host@user":
            return f"{h}@{u}"
        elif style == "custom" and custom:
            return custom
        return f"{u}@{h}"

    def difficulty_hints(self):
        """Return True if hints should be shown."""
        if not self.data: return True
        d = self.data.get("difficulty", 2)
        if d == 1: return True    # easy: always on
        if d == 4: return False   # nightmare: always off
        return self.data.get("hints_enabled", True)  # medium/hard: respects toggle

    def log(self, msg):
        SAVE_DIR.mkdir(exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(LOG_FILE, "a") as f:
                f.write(f"[{ts}] {msg}\n")
        except:
            pass

    # ── Summary stats ─────────────────────────────────────────────────────

    def stats_lines(self):
        if not self.data: return []
        lvl   = level_for_xp(self.data["xp"])
        title = LEVEL_TITLES[min(lvl, len(LEVEL_TITLES)-1)]
        hrs   = self.data.get("playtime_seconds", 0) // 3600
        mins  = (self.data.get("playtime_seconds", 0) % 3600) // 60
        diff  = DIFF_NAMES.get(self.data.get("difficulty",2),"?")
        return [
            f"Player     : {self.data['username']}@{self.data['hostname']}",
            f"Level      : {lvl} — {title}",
            f"XP         : {self.data['xp']}  (next level in {xp_to_next(self.data['xp'])} XP)",
            f"Difficulty : {diff}",
            f"Commands   : {self.data['total_commands']}",
            f"Scenarios  : {len(self.data['completed_scenarios'])} completed",
            f"Missions   : {len(self.data['completed_missions'])} completed",
            f"Achievements: {len(self.data.get('achievements', []))}",
            f"Play time  : {hrs}h {mins}m",
        ]
