"""
core/ui.py  —  SYSOPS Visual Engine v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pixel-perfect box drawing, gradient ASCII art, full theme system.
Every box boundary is computed from VISIBLE character width only —
ANSI escape codes are stripped before any padding calculation.
"""

import os, sys, re, time, random, shutil, textwrap

# ── ANSI primitives ───────────────────────────────────────────────────────────
R   = "\033[0m"
B   = "\033[1m"
DIM = "\033[2m"
IT  = "\033[3m"
UL  = "\033[4m"

BLACK   = "\033[30m";  RED     = "\033[31m";  GREEN   = "\033[32m"
YELLOW  = "\033[33m";  BLUE    = "\033[34m";  MAGENTA = "\033[35m"
CYAN    = "\033[36m";  WHITE   = "\033[37m"
BRED    = "\033[91m";  BGREEN  = "\033[92m";  BYELLOW = "\033[93m"
BBLUE   = "\033[94m";  BMAGENTA= "\033[95m";  BCYAN   = "\033[96m"
BWHITE  = "\033[97m"
BG_BLACK= "\033[40m";  BG_RED  = "\033[41m";  BG_GREEN= "\033[42m"
BG_DARK = "\033[48;5;232m"
BG_CARD = "\033[48;5;234m"

def fg256(n, t=""):
    return f"\033[38;5;{n}m{t}{R}" if t else f"\033[38;5;{n}m"

def bg256(n, t=""):
    return f"\033[48;5;{n}m{t}{R}" if t else f"\033[48;5;{n}m"

# ── ANSI-aware string width ───────────────────────────────────────────────────
_ANSI_RE = re.compile(r'\033\[[0-9;]*m')

def strip_ansi(s):
    return _ANSI_RE.sub('', s)

def vlen(s):
    """Visible length — ignores all ANSI escape codes."""
    return len(strip_ansi(s))

def vpad(s, width, char=' '):
    """Right-pad s to visible `width`."""
    return s + char * max(0, width - vlen(s))

# ── Colour shortcuts ──────────────────────────────────────────────────────────
def _c(code, t): return f"{code}{t}{R}"
def bold(t):     return _c(B,        t)
def dim(t):      return _c(DIM,      t)
def red(t):      return _c(BRED,     t)
def green(t):    return _c(BGREEN,   t)
def yellow(t):   return _c(BYELLOW,  t)
def blue(t):     return _c(BBLUE,    t)
def magenta(t):  return _c(BMAGENTA, t)
def cyan(t):     return _c(BCYAN,    t)
def white(t):    return _c(BWHITE,   t)
def ok(t):       return _c(BGREEN,   t)
def err(t):      return _c(BRED,     t)
def warn(t):     return _c(BYELLOW,  t)
def info(t):     return _c(BCYAN,    t)
def accent(t):   return f"{BRED}{B}{t}{R}"

def tag(name):
    TAG_MAP = {
        "HARD":      (88,  15), "MEDIUM":    (130, 15), "EASY":      (28,  15),
        "SECURITY":  (88,  15), "NETWORKING":(17,  15), "DOCKER":    (24,  15),
        "TAILSCALE": (53,  15), "RSYNC":     (22,  15), "SSH":       (94,  15),
        "NGINX":     (28,  15), "CYBER":     (88,  15), "COMBO":     (55,  15),
        "GIT":       (136, 0),  "REDTEAM":   (196, 15), "NIGHTMARE": (196, 11),
    }
    bg_n, fg_n = TAG_MAP.get(name.upper(), (238, 15))
    return f"{bg256(bg_n)}{fg256(fg_n)}{B} {name.upper()} {R}"

def diff_badge(level):
    MAP = {1:(28,"EASY"), 2:(130,"MEDIUM"), 3:(88,"HARD"), 4:(196,"NIGHTMARE")}
    bg_n, name = MAP.get(level, (238,"?"))
    return f"{bg256(bg_n)}{B}{BWHITE} {name} {R}"

def sev(s):
    SEV_COLORS = {
        "CRITICAL": (196, 15), "HIGH": (202, 15),
        "MEDIUM":   (220, 0),  "LOW":  (39,  15), "INFO": (240, 15),
    }
    bg_n, fg_n = SEV_COLORS.get(s.upper(), (238, 15))
    return f"{bg256(bg_n)}{fg256(fg_n)}{B} {s:<8} {R}"

# ── Terminal helpers ──────────────────────────────────────────────────────────
def term_width():
    return min(shutil.get_terminal_size((80, 24)).columns, 120)

def clear():
    sys.stdout.write("\033[H\033[2J\033[3J")
    sys.stdout.flush()

# ══════════════════════════════════════════════════════════════════════════════
# THEME SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

THEMES = {
    "cyberpunk": {
        "name":       "Cyberpunk",
        "box_border": BRED,
        "box_title":  BYELLOW,
        "accent":     BRED,
        "cmd":        BCYAN,
        "section_fg": BRED,
        "banner_cols":[196, 160, 124, 88, 52],
        "tag_line":   f"{fg256(240)}// terminal command simulator{R}",
    },
    "matrix": {
        "name":       "Matrix",
        "box_border": BGREEN,
        "box_title":  BGREEN,
        "accent":     BGREEN,
        "cmd":        GREEN,
        "section_fg": BGREEN,
        "banner_cols":[46, 40, 34, 28, 22],
        "tag_line":   f"{fg256(240)}// follow the white rabbit{R}",
    },
    "stealth": {
        "name":       "Stealth",
        "box_border": BBLUE,
        "box_title":  BCYAN,
        "accent":     BBLUE,
        "cmd":        BCYAN,
        "section_fg": BBLUE,
        "banner_cols":[21, 27, 33, 39, 45],
        "tag_line":   f"{fg256(240)}// ghost in the machine{R}",
    },
    "blood": {
        "name":       "Blood",
        "box_border": fg256(196),
        "box_title":  fg256(214),
        "accent":     fg256(196),
        "cmd":        fg256(208),
        "section_fg": fg256(196),
        "banner_cols":[196, 202, 208, 214, 220],
        "tag_line":   f"{fg256(240)}// curse technique: domain expansion{R}",
    },
    "void": {
        "name":       "Void",
        "box_border": BMAGENTA,
        "box_title":  BWHITE,
        "accent":     BMAGENTA,
        "cmd":        BMAGENTA,
        "section_fg": BMAGENTA,
        "banner_cols":[55, 91, 127, 163, 199],
        "tag_line":   f"{fg256(240)}// the void stares back{R}",
    },
}

_ACTIVE_THEME = "cyberpunk"
_ACTIVE_FONT  = "block"

def set_theme(name):
    global _ACTIVE_THEME
    if name in THEMES:
        _ACTIVE_THEME = name

def set_font(name):
    global _ACTIVE_FONT
    if name in BANNER_FONTS:
        _ACTIVE_FONT = name

def get_theme():
    return THEMES.get(_ACTIVE_THEME, THEMES["cyberpunk"])

def T(key):
    return get_theme().get(key, "")

# ══════════════════════════════════════════════════════════════════════════════
# ASCII BANNER FONTS
# ══════════════════════════════════════════════════════════════════════════════

BANNER_BLOCK = [
    r" ██████╗ ██╗   ██╗███████╗ ██████╗ ██████╗ ███████╗",
    r"██╔════╝ ╚██╗ ██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝",
    r"╚█████╗   ╚████╔╝ ███████╗██║   ██║██████╔╝███████╗",
    r" ╚═══██╗   ╚██╔╝  ╚════██║██║   ██║██╔═══╝ ╚════██║",
    r"██████╔╝    ██║   ███████║╚██████╔╝██║     ███████║",
    r"╚═════╝     ╚═╝   ╚══════╝ ╚═════╝ ╚═╝     ╚══════╝",
]

BANNER_GHOST = [
    r"  ██████  ██    ██ ███████  ██████  ██████  ███████",
    r" ██       ██    ██ ██      ██    ██ ██   ██ ██     ",
    r"  ██████  ██    ██ ███████ ██    ██ ██████  ███████",
    r"       ██  ██  ██       ██ ██    ██ ██           ██",
    r"  ██████    ████   ███████  ██████  ██      ███████",
]

BANNER_SHARP = [
    r"  ____ _  _ ____ ____ ____  ____",
    r"  [__  |  | [__  |  | |__]  [__ ",
    r"  ___] |\/ ___] |__| |     ___]",
]

BANNER_CYBER = [
    r"  ▄████████ ▄██   ▄      ▄████████  ▄██████▄     ▄███████▄    ▄████████",
    r" ███    ███ ███   ██▄   ███    ███ ███    ███   ███    ███   ███    ███",
    r" ███    █▀  ███▄▄▄███   ███    █▀  ███    ███   ███    ███   ███    █▀ ",
    r" ███        ▀▀▀▀▀▀███   ███        ███    ███   ███    ███   ███       ",
    r" ███        ▄██   ███ ▀███████████ ███    ███ ▀█████████▀  ▀███████████",
    r" ███    █▄  ███   ███          ███ ███    ███   ███                 ███",
    r" ███    ███ ███   ███    ▄█    ███ ███    ███   ███          ▄█    ███",
    r" ████████▀   ▀█████▀   ▄████████▀  ▀██████▀   ▄████▀       ▄████████▀ ",
]

BANNER_FONTS = {
    "block": BANNER_BLOCK,
    "ghost": BANNER_GHOST,
    "sharp": BANNER_SHARP,
    "cyber": BANNER_CYBER,
}

def _gradient_line(text, colors):
    if not colors:
        return text
    chars = list(text)
    n     = max(len(chars), 1)
    out   = []
    for i, ch in enumerate(chars):
        if ch == ' ':
            out.append(ch)
        else:
            bucket = min(int(i / n * len(colors)), len(colors)-1)
            out.append(f"{fg256(colors[bucket])}{ch}")
    return "".join(out) + R

def draw_banner(font=None, theme=None):
    th    = THEMES.get(theme or _ACTIVE_THEME, THEMES["cyberpunk"])
    cols  = th["banner_cols"]
    lines = BANNER_FONTS.get(font or _ACTIVE_FONT, BANNER_BLOCK)
    out   = ["\n"]
    for line in lines:
        out.append("  " + _gradient_line(line, cols))
    out.append("")
    out.append(f"  {th['tag_line']}   {fg256(240)}v3.0  ·  theme: {th['name']}{R}")
    out.append("")
    return "\n".join(out)

# ══════════════════════════════════════════════════════════════════════════════
# BOX DRAWING ENGINE  —  pixel-perfect, ANSI-safe
# ══════════════════════════════════════════════════════════════════════════════

STYLES = {
    "double": dict(tl="╔",tr="╗",bl="╚",br="╝",h="═",v="║",tl2="╠",tr2="╣"),
    "round":  dict(tl="╭",tr="╮",bl="╰",br="╯",h="─",v="│",tl2="├",tr2="┤"),
    "heavy":  dict(tl="┏",tr="┓",bl="┗",br="┛",h="━",v="┃",tl2="┣",tr2="┫"),
    "thin":   dict(tl="┌",tr="┐",bl="└",br="┘",h="─",v="│",tl2="├",tr2="┤"),
    "ascii":  dict(tl="+",tr="+",bl="+",br="+",h="-",v="|",tl2="+",tr2="+"),
}

def wrap_ansi(line, width):
    """Word-wrap a (possibly ANSI-styled) line to `width` visible columns.

    Returns a list of styled rows. Handles the common case of a uniform
    style wrapper plus leading indentation (e.g. "  \\033[2m…text…\\033[0m").
    Lines with complex mid-line colour that overflow degrade gracefully to a
    single-style wrap rather than clipping mid-word.
    """
    if width < 1 or vlen(line) <= width:
        return [line]

    # Split the leading run of spaces + ANSI codes into (indent, style).
    i = 0
    style = ""
    indent_n = 0
    while i < len(line):
        m = _ANSI_RE.match(line, i)
        if m:
            style += m.group(0)
            i = m.end()
            continue
        if line[i] == " ":
            indent_n += 1
            i += 1
            continue
        break

    body = strip_ansi(line[i:])
    pieces = textwrap.wrap(body, width=max(1, width - indent_n)) or [body]
    pad = " " * indent_n
    return [f"{pad}{style}{p}{R}" for p in pieces]


def _hrule(st, w, lc, rc, bc):
    return f"{bc}{lc}{st['h']*(w-2)}{rc}{R}"

def _content_row(st, content, w, bc, pad=2):
    """
    Render one box content row.
    w   = total box width in VISIBLE chars
    pad = spaces on each side inside the border
    """
    inner = w - 2 - pad*2          # visible chars available for content
    vis   = vlen(content)
    if vis > inner:
        # Truncate to inner width using visible chars only
        raw   = strip_ansi(content)
        content = raw[:inner]
        vis   = inner
    rp = " " * (inner - vis)
    ls = " " * pad
    rs = " " * pad
    return f"{bc}{st['v']}{R}{ls}{content}{rp}{rs}{bc}{st['v']}{R}"

def box(title, lines, width=74, style="double",
        border_color=None, title_color=None, pad=2):
    """
    Draw a perfectly aligned box.

    title        : header text (ANSI ok)
    lines        : list of content strings (ANSI ok). Empty string = blank row.
    width        : total visible box width
    style        : double / round / heavy / thin / ascii
    border_color : ANSI code (defaults to theme)
    title_color  : ANSI code (defaults to theme)
    pad          : spaces inside each border side
    """
    th = get_theme()
    bc = border_color or th["box_border"]
    tc = title_color  or th["box_title"]
    st = STYLES.get(style, STYLES["double"])
    w  = width

    # Top
    print(_hrule(st, w, st["tl"], st["tr"], bc))

    # Title — centred with decorators
    vt   = vlen(title)
    deco = 4                       # "╡ " + " ╞"
    fill = max(0, w - 2 - vt - deco)
    fl   = fill // 2
    fr   = fill - fl
    print(f"{bc}{st['tl2']}{st['h']*fl}╡{R} {tc}{B}{title}{R} {bc}╞{st['h']*fr}{st['tr2']}{R}")

    # Separator
    print(_hrule(st, w, st["tl2"], st["tr2"], bc))

    # Content (long lines word-wrap instead of clipping mid-word)
    inner = w - 2 - pad * 2
    for line in lines:
        if line == "":
            print(_content_row(st, "", w, bc, pad))
            continue
        for seg in wrap_ansi(line, inner):
            print(_content_row(st, seg, w, bc, pad))

    # Bottom
    print(_hrule(st, w, st["bl"], st["br"], bc))


# ══════════════════════════════════════════════════════════════════════════════
# HELP BOX  —  two-column command/description layout, pixel-perfect
# ══════════════════════════════════════════════════════════════════════════════

def help_box(sections_data, width=76, style="double"):
    """
    Render the all-commands help screen.

    sections_data : list of (section_title, list of (cmd_str, desc_str))
    """
    th    = get_theme()
    bc    = th["box_border"]
    tc    = th["box_title"]
    cc    = th["cmd"]
    st    = STYLES.get(style, STYLES["double"])
    w     = width
    pad   = 2
    inner = w - 2 - pad*2          # visible chars for content

    CMD_COL = 26    # visible width reserved for the command name column

    def rule(lc, rc):
        return f"{bc}{lc}{st['h']*(w-2)}{rc}{R}"

    def row(content):
        vis = vlen(content)
        rp  = " " * max(0, inner - vis)
        ls  = " " * pad; rs = " " * pad
        return f"{bc}{st['v']}{R}{ls}{content}{rp}{rs}{bc}{st['v']}{R}"

    def sec_row(title):
        dash_avail = inner - vlen(title) - 2
        ld = max(0, int(dash_avail * 0.12))
        rd = max(0, dash_avail - ld)
        content = (f"{bc}{st['h']*ld}{R} "
                   f"{tc}{B}{title}{R} "
                   f"{bc}{st['h']*rd}{R}")
        return row(content)

    def cmd_row(cmd, desc):
        cmd_col  = f"  {cc}{B}{cmd}{R}"
        gap      = max(1, CMD_COL - vlen(cmd) - 2)
        desc_col = f"{DIM}{desc}{R}"
        content  = cmd_col + " "*gap + desc_col
        # guard: if combined overflows, truncate desc
        max_desc = inner - CMD_COL - 2
        if vlen(desc) > max_desc:
            desc_col = f"{DIM}{strip_ansi(desc)[:max_desc-1]}…{R}"
            content  = cmd_col + " "*gap + desc_col
        return row(content)

    # ── Print ─────────────────────────────────────────────────────────────────
    print(rule(st["tl"], st["tr"]))

    # Title centred
    title_s = "SYSOPS — All Commands"
    vt = vlen(title_s)
    fl = max(0, (w - 2 - vt - 4) // 2)
    fr = max(0, w - 2 - vt - 4 - fl)
    print(f"{bc}{st['tl2']}{st['h']*fl}╡{R} {tc}{B}{title_s}{R} {bc}╞{st['h']*fr}{st['tr2']}{R}")
    print(rule(st["tl2"], st["tr2"]))

    for sec_title, cmds in sections_data:
        print(row(""))
        print(sec_row(sec_title))
        print(row(""))
        for cmd, desc in cmds:
            print(cmd_row(cmd, desc))

    print(row(""))
    print(rule(st["bl"], st["br"]))


# ══════════════════════════════════════════════════════════════════════════════
# RULES / SECTION HEADERS
# ══════════════════════════════════════════════════════════════════════════════

def hr(char="─", color=None, width=None):
    th = get_theme()
    c  = color or th["accent"]
    w  = width or min(term_width(), 80)
    print(f"{c}{char*w}{R}")

def hr_accent(width=None):
    th   = get_theme()
    cols = th["banner_cols"]
    w    = width or min(term_width(), 80)
    out  = []
    for i in range(w):
        bucket = min(int(i/w*len(cols)), len(cols)-1)
        out.append(f"{fg256(cols[bucket])}━")
    print("".join(out) + R)

def hr_red(width=None):
    w = width or min(term_width(), 80)
    print(f"{BRED}{'─'*w}{R}")

def slow_print(text, delay=0.012):
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    if not text.endswith("\n"):
        print()

def section(title, color=None):
    th = get_theme()
    c  = color or th["section_fg"]
    w  = min(term_width(), 80)
    print()
    print(f"{c}{B}// {title.upper()}{R}")
    print(f"{DIM}{'─'*w}{R}")


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESS BAR
# ══════════════════════════════════════════════════════════════════════════════

def progress_bar(label, total_mb, speed_mb=80, bar_width=36):
    th    = get_theme()
    bc    = th["banner_cols"]
    steps = 35
    chunk = total_mb / max(steps, 1)
    elapsed = 0.0
    label_s = label[:18]

    print()
    for i in range(steps + 1):
        pct  = i / steps
        done = int(pct * bar_width)
        rest = bar_width - done

        bar_chars = []
        for j in range(done):
            bucket = min(int(j/bar_width*len(bc)), len(bc)-1)
            bar_chars.append(f"{fg256(bc[bucket])}█")
        bar_chars.append(DIM + "░"*rest + R)
        bar_str = "".join(bar_chars)

        sent    = chunk * i
        elapsed += chunk / max(speed_mb, 1)
        eta     = max(0, (total_mb - sent) / max(speed_mb, 1))
        rate_c  = BGREEN if speed_mb > 50 else BYELLOW

        sys.stdout.write(
            f"\r  {BCYAN}{label_s:<18}{R}  [{bar_str}]  "
            f"{BYELLOW}{pct*100:5.1f}%{R}  "
            f"{rate_c}{speed_mb:.0f} MB/s{R}  "
            f"{DIM}ETA {eta:.0f}s{R}"
        )
        sys.stdout.flush()
        time.sleep(0.032)

    print(f"\n\n  {ok('✓ Transfer complete!')}  "
          f"{DIM}{total_mb:.0f} MB in {elapsed:.0f}s{R}\n")


# ══════════════════════════════════════════════════════════════════════════════
# SPINNER
# ══════════════════════════════════════════════════════════════════════════════

def spinner(label, duration=1.2):
    th     = get_theme()
    ac     = th["accent"]
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    end    = time.time() + duration
    i      = 0
    while time.time() < end:
        sys.stdout.write(f"\r  {ac}{B}{frames[i%len(frames)]}{R}  {label}")
        sys.stdout.flush()
        time.sleep(0.07)
        i += 1
    sys.stdout.write(f"\r  {BGREEN}✓{R}  {label}{' '*14}\n")
    sys.stdout.flush()


# ══════════════════════════════════════════════════════════════════════════════
# XP FLASH
# ══════════════════════════════════════════════════════════════════════════════

def xp_flash(pts, reason=""):
    th  = get_theme()
    bc  = th["banner_cols"]
    col = fg256(bc[0]) if bc else BYELLOW
    r   = f"  {DIM}{reason}{R}" if reason else ""
    print(f"  {col}{B}✦ +{pts} XP{R}{r}")


# ══════════════════════════════════════════════════════════════════════════════
# XP STATS PANEL
# ══════════════════════════════════════════════════════════════════════════════

def xp_panel(xp, level, title, to_next, diff, done, total, cmds, achs,
             username, hostname):
    from core.save import XP_PER_LEVEL
    th   = get_theme()
    bc   = th["banner_cols"]

    prev_t = XP_PER_LEVEL[max(0, level-1)] if level > 0 else 0
    next_t = XP_PER_LEVEL[min(level, len(XP_PER_LEVEL)-1)]
    span   = max(1, next_t - prev_t)
    pct    = min(1.0, (xp - prev_t) / span)
    bw     = 30
    filled = int(pct * bw)

    bar_chars = []
    for j in range(filled):
        bucket = min(int(j/bw*len(bc)), len(bc)-1)
        bar_chars.append(f"{fg256(bc[bucket])}█")
    bar_chars.append(DIM + "░"*(bw-filled) + R)
    bar = "".join(bar_chars)

    col = fg256(bc[0]) if bc else BYELLOW
    lines = [
        f"{col}{B}Level {level}  —  {title}{R}",
        f"XP       {BYELLOW}{xp:,}{R}   {DIM}next in {to_next:,} XP{R}",
        f"[{bar}]  {DIM}{int(pct*100)}%{R}",
        "",
        f"Difficulty   {warn(diff)}",
        f"Missions     {ok(str(done))}{DIM}/{total}{R}",
        f"Commands     {DIM}{cmds:,}{R}",
        f"Achievements {BYELLOW}{achs}{R}",
        f"Player       {cyan(username+'@'+hostname)}",
    ]
    box("Your Stats", lines, width=52, style="heavy",
        border_color=col)


# ══════════════════════════════════════════════════════════════════════════════
# MISSION HEADER
# ══════════════════════════════════════════════════════════════════════════════

def mission_header(sc):
    w = min(term_width(), 80)
    print()
    hr_accent(w)
    print(f"  {get_theme()['accent']}{B}MISSION {sc['id'].upper()}{R}   "
          f"{diff_badge(sc['difficulty'])}   {DIM}{sc['category']}{R}")
    print(f"  {BWHITE}{B}{sc['title']}{R}")
    hr_accent(w)
    print()


# ══════════════════════════════════════════════════════════════════════════════
# THEME / FONT PICKERS
# ══════════════════════════════════════════════════════════════════════════════

def theme_picker():
    clear()
    th_cur = get_theme()
    print(f"\n  {BWHITE}{B}COLOUR THEME{R}\n")
    for i, (name, th) in enumerate(THEMES.items(), 1):
        bc   = th["banner_cols"]
        samp = "".join(f"{fg256(c)}█{R}" for c in bc)
        cur  = ok(" ← current") if name == _ACTIVE_THEME else ""
        tl   = strip_ansi(th["tag_line"]).replace("//","").strip()
        print(f"  {th['accent']}{B}[{i}]{R}  {BWHITE}{B}{th['name']:<12}{R}  "
              f"{samp}  {DIM}{tl}{R}{cur}")
    print()
    raw = input(f"  {th_cur['accent']}>{R} ").strip()
    names = list(THEMES.keys())
    try:
        chosen = names[int(raw)-1]
        set_theme(chosen)
        return chosen
    except (ValueError, IndexError):
        return _ACTIVE_THEME

def font_picker():
    clear()
    th = get_theme()
    print(f"\n  {BWHITE}{B}BANNER FONT{R}\n")
    for i, (fname, flines) in enumerate(BANNER_FONTS.items(), 1):
        cur = ok("  ← current") if fname == _ACTIVE_FONT else ""
        print(f"  {th['accent']}{B}[{i}] {fname.upper()}{R}{cur}")
        for line in flines[:2]:                  # preview: first 2 rows
            print("      " + _gradient_line(line, th["banner_cols"]))
        print()
    raw = input(f"  {th['accent']}>{R} ").strip()
    fonts = list(BANNER_FONTS.keys())
    try:
        chosen = fonts[int(raw)-1]
        set_font(chosen)
        return chosen
    except (ValueError, IndexError):
        return _ACTIVE_FONT


# ══════════════════════════════════════════════════════════════════════════════
# SCAN ANIMATION
# ══════════════════════════════════════════════════════════════════════════════

def scan_animation(host_ip, duration=2.0):
    from core.world import SERVICES
    ports = random.sample(list(SERVICES.keys()), min(14, len(SERVICES)))
    ports.sort()
    open_ports = []
    end = time.time() + duration
    i   = 0
    while time.time() < end and i < len(ports):
        p      = ports[i]
        status = random.choice(["open","open","open","closed","filtered"])
        svc, _ = SERVICES.get(p, ("unknown",""))
        col    = BGREEN if status=="open" else (DIM if status=="closed" else BYELLOW)
        sys.stdout.write(
            f"\r  {DIM}scanning{R} {host_ip}:{BYELLOW}{p:<6}{R}  "
            f"{col}{status:<10}{R}  {DIM}{svc}{R}"
        )
        sys.stdout.flush()
        if status == "open":
            open_ports.append((p, svc))
        time.sleep(0.07)
        i += 1
    print()
    return open_ports
