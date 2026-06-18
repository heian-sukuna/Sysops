"""
scenarios/engine.py — Scenario runner, progress tracker, quick challenges
"""

import time
from core.ui import *
from core.save import LEVEL_TITLES, level_for_xp, DIFF_NAMES
from scenarios.missions import SCENARIOS, QUICK_CHALLENGES, get_scenario

class ScenarioEngine:
    def __init__(self, world, save):
        self.w = world
        self.s = save
        self.active    = None
        self.step_idx  = 0

    # ─── Public interface ─────────────────────────────────────────────────────

    def list_all(self, filter_cat=None, show_all=False):
        """Display missions. When a focus module is active, show only that module's missions.
        Pass show_all=True (or 'missions all') to override the focus filter."""
        scenarios = SCENARIOS
        if filter_cat:
            scenarios = [sc for sc in scenarios if filter_cat.lower() in sc["category"].lower()]

        completed = set(self.s.get("completed_scenarios", []))
        focus     = self.s.get("focus_module")
        th        = get_theme()

        if focus and not show_all and not filter_cat:
            display = [sc for sc in scenarios if self._focus_matches(sc, focus)]
            f_done  = len([s for s in display if s["id"] in completed])
            section("Available Missions", BRED)
            print(f"  {th['accent']}{B}★  FOCUS: {focus.upper()}  —  "
                  f"{f_done}/{len(display)} completed{R}\n")
            for sc in display:
                self._print_sc(sc, completed, dimmed=False)
            print(dim(f"  {f_done}/{len(display)} completed in {focus}"))
            print(dim("  Run: mission <id>  to start  |  missions all  to see every mission"))
        else:
            section("Available Missions", BRED)
            for sc in scenarios:
                self._print_sc(sc, completed, dimmed=False)
            print(dim(f"  {len(completed)}/{len(SCENARIOS)} completed"))
            print(dim("  Run: mission <id>  to start  (e.g. mission ts01)"))

    def _print_sc(self, sc, completed, dimmed=False):
        """Render a single mission row."""
        done    = sc["id"] in completed
        prefix  = ok("✓ ") if done else "  "
        tag_str = " ".join(tag(t) for t in sc["tags"])
        locked  = sc["id"] not in self._unlocked_ids() and not done

        if dimmed:
            id_col    = f"{DIM}[{sc['id']}]{R}"
            title_col = dim(sc["title"])
        else:
            id_col    = f"{BWHITE}{B}[{sc['id']}]{R}"
            title_col = cyan(sc["title"])

        print(f"  {prefix}{id_col}  {title_col}  "
              f"{tag_str}  {dim('+'+str(sc['xp_reward'])+' XP')}")
        print(f"         {dim(sc['category'])}")
        if locked:
            print(f"         {warn('🔒 Complete easier missions first')}")
        print()

    def _focus_matches(self, sc, focus):
        """True if the scenario belongs to the given focus module.

        Combo missions (category starts with 'combo:') only match when
        focus == 'combo', so they don't inflate single-tool focus groups.
        """
        cat  = sc["category"].lower()
        tags = sc.get("tags", [])

        # Combo focus: match category or COMBO tag
        if focus == "combo":
            return "combo" in cat or "COMBO" in tags

        # All other focus modules: only match if category is NOT a combo category
        if cat.startswith("combo"):
            return False

        kw_map = {
            "rsync":      ["rsync"],
            "tailscale":  ["tailscale"],
            "docker":     ["docker"],
            "nginx":      ["nginx"],
            "networking": ["networking"],
            "cybersec":   ["cybersec", "cyber"],
            "git":        ["git"],
            "redteam":    ["redteam"],
            "ssh":        ["ssh"],
        }
        kws = kw_map.get(focus, [focus])
        return any(k in cat for k in kws)

    def combo_guide(self):
        """Interactive combo missions screen — show status and allow launch."""
        completed = set(self.s.get("completed_scenarios", []))
        th        = get_theme()

        combo_scs = [sc for sc in SCENARIOS
                     if "combo" in sc["category"].lower()
                     or "COMBO" in sc.get("tags", [])]

        clear()
        section("COMBO MISSIONS — Multi-Tool Workflows")
        print(f"  {DIM}Chain multiple tools together. Complete prereqs first.{R}\n")

        COMBO_META = {
            "combo01": {"tools": ["tailscale","docker","nginx","rsync"],
                        "prereqs": ["ts01","dk01","dk02","nx01"]},
            "combo02": {"tools": ["tailscale","docker","cybersec"],
                        "prereqs": ["dk01","cy01","cy02","cy03"]},
            "git05":   {"tools": ["git","docker"],
                        "prereqs": ["git01","dk01","dk03"]},
            "rt06":    {"tools": ["full red-team"],
                        "prereqs": ["rt01","rt02","rt03","rt04","rt05"]},
        }

        available = []
        for sc in combo_scs:
            done   = sc["id"] in completed
            locked = sc["id"] not in self._unlocked_ids() and not done
            meta   = COMBO_META.get(sc["id"], {})
            tools  = meta.get("tools", [])
            pre    = meta.get("prereqs", [])

            status = ok("[DONE]  ") if done else (warn("[LOCKED]") if locked else info("[READY] "))
            icon   = ok("✓ ") if done else ("🔒 " if locked else f"{th['accent']}▶{R} ")

            print(f"  {icon}{th['accent']}{B}[{sc['id']}]{R}  "
                  f"{BWHITE}{B}{sc['title']}{R}  {status}  "
                  f"{dim('+'+str(sc['xp_reward'])+' XP')}")
            print(f"       {DIM}{sc['category']}{R}")

            if tools:
                tool_str = " + ".join(f"{th['cmd']}{t}{R}" for t in tools)
                print(f"       Tools   : {tool_str}")

            pre_done = [p for p in pre if p in completed]
            if pre:
                pre_str = " · ".join(
                    f"{ok(p)}" if p in completed else f"{warn(p)}"
                    for p in pre
                )
                print(f"       Prereqs : {pre_str}  "
                      f"{DIM}({len(pre_done)}/{len(pre)} done){R}")

            print()
            if not done and not locked:
                available.append(sc["id"])

        if available:
            print(dim(f"  Available to start: {', '.join(available)}"))
        print()
        try:
            raw = input(f"  {th['accent']}Enter mission ID to start (or Enter to skip):{R} ").strip()
            if raw:
                self.start(raw)
        except (EOFError, KeyboardInterrupt):
            pass

    def start(self, mission_id):
        """Start a specific mission by ID."""
        sc = get_scenario(mission_id)
        if not sc:
            print(err(f"  Mission '{mission_id}' not found."))
            print(dim("  Run: missions  to see all available missions"))
            return False

        completed = set(self.s.get("completed_scenarios", []))
        if mission_id in completed:
            print(warn(f"  Mission '{sc['title']}' already completed!"))
            choice = input(dim("  Replay it? (y/N): ")).strip().lower()
            if choice != "y": return False

        self.active   = sc
        self.step_idx = 0
        self.w.cmd_log.clear()   # scope command-verification to this attempt

        clear()
        self._draw_mission_header(sc)

        steps = sc["steps"]
        print(f"  {bold('Steps to complete:')}\n")
        for i, (desc, _, hint) in enumerate(steps, 1):
            print(f"    {BRED}{B}{i}.{R} {desc}")
            if self.s.difficulty_hints():
                print(f"       {dim('→ '+hint)}")
            print()

        print(f"  {BYELLOW}XP Reward: +{sc['xp_reward']}{R}")
        print()
        self._show_current_step()
        return True

    def check_after_command(self):
        """Called after every command to auto-advance active mission."""
        if not self.active: return
        steps = self.active["steps"]
        if self.step_idx >= len(steps):
            return
        _, check_fn, _ = steps[self.step_idx]
        try:
            if check_fn(self.w, self.s):
                print(ok(f"\n  ✓ Step {self.step_idx+1} complete!"))
                self.step_idx += 1
                if self.step_idx >= len(steps):
                    self._complete_mission()
                else:
                    self._show_current_step()
        except Exception:
            pass

    def abandon(self):
        if self.active:
            print(warn(f"  Mission '{self.active['title']}' abandoned."))
            self.active = None

    # ─── Quick challenges ─────────────────────────────────────────────────────

    def quick_challenge(self):
        """Interactive single-question drill."""
        import random
        completed = set(self.s.get("completed_missions", []))
        remaining = [q for q in QUICK_CHALLENGES if q["id"] not in completed]
        if not remaining:
            print(ok("  🏆 All quick challenges completed!"))
            print(dim("  More coming soon — keep grinding."))
            return

        q = random.choice(remaining)
        section("Quick Challenge", BCYAN)
        print(f"  {bold(q['prompt'])}\n")

        for attempt in range(3):
            try:
                ans = input(f"  {BCYAN}>{R} ").strip()
            except (EOFError, KeyboardInterrupt):
                return

            correct = any(a.lower() in ans.lower() or ans.lower() in a.lower()
                         for a in q["answers"])
            if correct:
                print(ok(f"\n  ✓ Correct!"))
                print(info(f"  Explanation: {q['explanation']}"))
                self.s.complete_mission(q["id"])
                lvl = self.s.add_xp(q["xp"], "quick challenge")
                xp_flash(q["xp"], "quick challenge")
                if lvl > 0:
                    print(f"\n  {BYELLOW}{B}★ LEVEL UP → {self.s.get('level')}{R}")
                return
            else:
                remaining_attempts = 2 - attempt
                if remaining_attempts > 0:
                    print(warn(f"  Not quite. {remaining_attempts} attempt(s) left."))
                    if self.s.difficulty_hints() and attempt == 1:
                        print(dim(f"  Hint: starts with '{q['answers'][0][:8]}...'"))
                else:
                    print(err("  ✗ Incorrect."))
                    print(info(f"  Answer: {ok(q['answers'][0])}"))
                    print(dim(f"  Explanation: {q['explanation']}"))

    # ─── Status panel ─────────────────────────────────────────────────────────

    def status_panel(self):
        if not self.active:
            print(info("  No active mission. Run: missions | mission <id>"))
            return
        sc = self.active
        steps = sc["steps"]
        print()
        print(info(f"  Active mission: {bold(sc['title'])}  {dim(sc['category'])}"))
        print()
        for i, (desc, _, hint) in enumerate(steps):
            if i < self.step_idx:
                icon = ok("✓")
            elif i == self.step_idx:
                icon = f"{BCYAN}{B}▶{R}"
            else:
                icon = dim("○")
            print(f"    {icon}  {desc if i < self.step_idx else (bold(desc) if i == self.step_idx else dim(desc))}")
        print()
        pct = int(self.step_idx / len(steps) * 100)
        bar = f"{BGREEN}{'█' * (pct//5)}{DIM}{'░' * (20 - pct//5)}{R}"
        print(f"  Progress: [{bar}] {pct}%")

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _draw_mission_header(self, sc):
        diff_names = {k: v.upper() for k, v in DIFF_NAMES.items()}
        diff_colors = {1:BGREEN,2:BYELLOW,3:BRED,4:f"{BG_RED}{B}{BYELLOW}"}
        d = sc["difficulty"]

        print()
        hr_red()
        print(f"  {BRED}{B}MISSION  {sc['id'].upper()}{R}   {diff_colors.get(d,BRED)}{diff_names.get(d,'?')}{R}   {dim(sc['category'])}")
        print(f"  {BWHITE}{B}{sc['title']}{R}")
        hr_red()
        print()
        slow_print(f"  {sc['story']}\n", delay=0.010)

    def _show_current_step(self):
        if not self.active: return
        steps = self.active["steps"]
        if self.step_idx >= len(steps): return
        desc, _, hint = steps[self.step_idx]
        n = self.step_idx + 1
        total = len(steps)
        print(f"\n  {BCYAN}{B}▶ Step {n}/{total}:{R} {bold(desc)}")
        if self.s.difficulty_hints():
            print(f"  {dim('Hint: '+hint)}\n")

    def _complete_mission(self):
        sc = self.active
        self.s.complete_scenario(sc["id"])
        lvl = self.s.add_xp(sc["xp_reward"], f"mission {sc['id']}")

        print()
        hr_red()
        slow_print(f"  {BYELLOW}{B}★  MISSION COMPLETE: {sc['title']}  ★{R}", delay=0.015)
        hr_red()
        print(f"\n  {ok('+'+str(sc['xp_reward'])+' XP')}  {dim('Total: '+str(self.s.get('xp',0)))}")

        if lvl > 0:
            from core.save import LEVEL_TITLES
            lvl_num = self.s.get("level",1)
            title   = LEVEL_TITLES[min(lvl_num, len(LEVEL_TITLES)-1)]
            print(f"\n  {BYELLOW}{B}★★ LEVEL UP!  Level {lvl_num} — {title}  ★★{R}")

        # Unlock next module if needed
        completed = set(self.s.get("completed_scenarios",[]))
        if len([s for s in SCENARIOS if s.get("category","").startswith("docker") and s["id"] in completed]) >= 2:
            self.s.unlock_module("cybersec")
            print(info("\n  🔓 Module unlocked: Cybersecurity"))

        print()
        self.active = None
        self._check_focus_complete()

    def _check_focus_complete(self):
        """If all missions in the current focus module are done, prompt for a new focus."""
        focus = self.s.get("focus_module")
        if not focus:
            return
        focus_scs  = [sc for sc in SCENARIOS if self._focus_matches(sc, focus)]
        if not focus_scs:
            return
        completed  = set(self.s.get("completed_scenarios", []))
        focus_done = [sc for sc in focus_scs if sc["id"] in completed]
        if len(focus_done) < len(focus_scs):
            return

        th = get_theme()
        print()
        print(f"  {BYELLOW}{B}★★  FOCUS MODULE COMPLETE: {focus.upper()}  ★★{R}")
        print(f"  {ok('All '+str(len(focus_scs))+' missions in '+focus+' finished!')}\n")
        self._prompt_new_focus()

    def _prompt_new_focus(self):
        """Ask the player to pick a new focus module."""
        th        = get_theme()
        completed = set(self.s.get("completed_scenarios", []))
        current   = self.s.get("focus_module")

        all_modules = [
            ("rsync",      "File transfers — rsync, partial resume"),
            ("tailscale",  "Mesh networking — peers, direct vs relay"),
            ("docker",     "Containers — run, compose, build, network"),
            ("nginx",      "Web server — reverse proxy, SSL, headers"),
            ("networking", "Fundamentals — ss, ip, dig, traceroute"),
            ("cybersec",   "Security — nmap, tshark, gobuster, lynis"),
            ("git",        "Version control — branch, rebase, bisect"),
            ("redteam",    "Red team — recon, exploit, post, report"),
            ("combo",      "Full-stack — multi-tool challenge missions"),
        ]

        choices = []
        for mod, desc in all_modules:
            if mod == current:
                continue
            mod_scs  = [sc for sc in SCENARIOS if self._focus_matches(sc, mod)]
            mod_done = len([sc for sc in mod_scs if sc["id"] in completed])
            if mod_scs and mod_done < len(mod_scs):
                choices.append((mod, desc, mod_done, len(mod_scs)))

        if not choices:
            print(f"  {ok('🏆 All modules complete — you are a SYSOPS Master!')}")
            return

        section("CHOOSE YOUR NEXT FOCUS MODULE")
        for i, (mod, desc, done, total) in enumerate(choices, 1):
            bar = ok("█" * done) + dim("░" * (total - done))
            print(f"  {th['accent']}{B}[{i}]{R}  {th['cmd']}{B}{mod:<14}{R}  "
                  f"{DIM}{desc}{R}  [{bar}{DIM}] {done}/{total}{R}")
        print()

        try:
            raw = input(f"  {th['accent']}▶ New focus:{R} ").strip()
            new_mod = choices[int(raw) - 1][0]
            self.s.data["focus_module"] = new_mod
            self.s.save()
            print(ok(f"\n  ✓ New focus: {new_mod}  — type 'missions' to see your next challenges."))
        except (ValueError, IndexError, EOFError, KeyboardInterrupt):
            print(dim("  (focus unchanged — set it any time in Options)"))

    def _unlocked_ids(self):
        """IDs that are unlocked based on progression."""
        completed = set(self.s.get("completed_scenarios",[]))
        diff = self.s.get("difficulty",2)
        unlocked = set()
        for sc in SCENARIOS:
            if diff == 1:  # easy — everything unlocked
                unlocked.add(sc["id"])
            elif sc["difficulty"] <= 2:
                unlocked.add(sc["id"])
            elif sc["difficulty"] == 3 and len(completed) >= 3:
                unlocked.add(sc["id"])
            elif sc["difficulty"] == 4 and len(completed) >= 6:
                unlocked.add(sc["id"])
        return unlocked
