#!/usr/bin/env python3
"""Design checks for UI code. Stdlib only, no network, bounded output.

  design.py tokens [PATH]                 existing design tokens (CSS variables, Tailwind config) + hard-coded colors worth tokenizing
  design.py audit [PATH ...] [--changed]  contrast, focus, labels, alt text, spacing/type scale drift, motion, responsive, AI-default tells
  design.py contrast FG BG [--large]      WCAG ratio for two colors, plus the nearest passing foreground
  design.py scale [--base 16 --ratio 1.25] starter type, spacing, and radius tokens as CSS variables

audit --strict exits 1 when any error is found, so it can back a ledger fact:
  ledger.py fact "design audit clean" --run "python design.py audit --strict" --proves <req id>
"""
import argparse
import colorsys
import hashlib
import json
import math
import random
import os
import re
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "dist", "build", "out", "coverage", "__pycache__", ".venv", "venv",
             ".next", ".nuxt", ".svelte-kit", ".astro", "target", ".idea", ".turbo", "vendor", "storybook-static", "public/build"}
STYLE_EXT = {".css", ".scss", ".sass", ".less", ".pcss"}
MARKUP_EXT = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".js", ".ts"}
MAX_FILES = 3000
MAX_BYTES = 400_000
TOKEN_FILE = re.compile(r"(token|theme|variables|vars|palette|colors|tailwind\.config|design-system)", re.I)

NAMED = {"white": "#ffffff", "black": "#000000", "red": "#ff0000", "green": "#008000", "blue": "#0000ff", "gray": "#808080",
         "grey": "#808080", "silver": "#c0c0c0", "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080",
         "navy": "#000080", "teal": "#008080", "maroon": "#800000", "lightgray": "#d3d3d3", "lightgrey": "#d3d3d3",
         "darkgray": "#a9a9a9", "darkgrey": "#a9a9a9", "whitesmoke": "#f5f5f5", "gainsboro": "#dcdcdc", "dimgray": "#696969"}
HEX = r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b"
FUNC = r"(?:rgba?|hsla?)\([^()]*\)"
COLOR_RX = re.compile(rf"{HEX}|{FUNC}")
VAR_RX = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\)[^()]*)*))?\)")
DECL_RX = re.compile(r"(--[\w-]+|[a-zA-Z-]+)\s*:\s*([^;{}]+)")
BLOCK_RX = re.compile(r"([^{}]*)\{([^{}]*)\}")
SPACING_PROPS = re.compile(r"^(?:margin|padding|gap|row-gap|column-gap|inset)(?:-[a-z-]+)?$")
TW_SPACE = re.compile(r"\b-?(?:p|m|px|py|pt|pb|pl|pr|ps|pe|mx|my|mt|mb|ml|mr|ms|me|gap|gap-x|gap-y|space-x|space-y)-\[(-?\d*\.?\d+)(px|rem)\]")
TW_TEXT_SIZE = re.compile(r"\btext-\[(\d*\.?\d+)(px|rem)\]")
TW_COLOR = re.compile(r"\b(text|bg)-(\[(?:#[0-9a-fA-F]{3,8}|(?:rgb|hsl)a?\([^\]]*\))\]|white|black)(?:/(\d{1,3}))?(?![\w-])")
TW_SLOP = re.compile(r"\b(?:from|via)-(?:purple|violet|indigo|fuchsia)-\d{3}\b[^\"'`]*\bto-(?:purple|violet|indigo|fuchsia|pink|blue)-\d{3}\b")
CLASS_ATTR = re.compile(r"\bclass(?:Name)?\s*=\s*(?:\{\s*)?([\"'`])(.*?)\1", re.S)
STYLE_OBJ = re.compile(r"style\s*=\s*\{\{(.*?)\}\}", re.S)
STYLE_ATTR = re.compile(r"style\s*=\s*\"([^\"]*)\"")

SEVERITY = {"error": 0, "warn": 1}


def rel(path, base):
    try:
        return Path(path).resolve().relative_to(base).as_posix()
    except ValueError:
        return Path(path).as_posix()


def git_files(root):
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=5)
        if top.returncode != 0:
            return None
        git_root = Path(top.stdout.strip()).resolve()
        out = subprocess.run(["git", "-c", "core.quotePath=false", "-C", str(git_root), "ls-files", "--cached", "--others",
                              "--exclude-standard", "-z"], capture_output=True, timeout=20)
        if out.returncode != 0:
            return None
        return [git_root / n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
    except (OSError, subprocess.SubprocessError):
        return None


def changed_files(root):
    names = set()
    for args in (["diff", "--name-only", "-z", "HEAD"], ["ls-files", "--others", "--exclude-standard", "-z"]):
        try:
            out = subprocess.run(["git", "-c", "core.quotePath=false", "-C", str(root), *args], capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            raise SystemExit("--changed needs git")
        if out.returncode != 0:
            raise SystemExit("--changed needs a git repository with at least one commit")
        names.update(n for n in out.stdout.decode("utf-8", "replace").split("\0") if n)
    top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=5).stdout.strip()
    return [Path(top) / n for n in sorted(names)]


def ui_file(path):
    ext = path.suffix.lower()
    if ext not in STYLE_EXT and ext not in MARKUP_EXT:
        return False
    name = path.name.lower()
    if ".min." in name or name.endswith(".d.ts") or ".test." in name or ".spec." in name or ".stories." in name:
        return False
    return True


def collect(targets, root, changed=False):
    files = []
    if changed:
        files = [p for p in changed_files(root) if p.is_file()]
    else:
        for t in targets:
            t = Path(t)
            if t.is_file():
                files.append(t)
                continue
            listed = git_files(t)
            if listed is None:
                listed = []
                for d, dirs, names in os.walk(t):
                    dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
                    listed.extend(Path(d) / n for n in names)
            t_res = t.resolve()
            for p in listed:
                try:
                    parts = p.resolve().relative_to(t_res).parts
                except ValueError:
                    continue
                if not any(x in SKIP_DIRS for x in parts):
                    files.append(p)
    out = []
    for p in files:
        if not ui_file(p):
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.count("\n") + 1
        if len(text) / lines > 400:  # minified or generated
            continue
        if p.suffix.lower() in {".js", ".ts"} and "<" not in text and "className" not in text and "styled" not in text:
            continue
        out.append((p, text))
        if len(out) >= MAX_FILES:
            break
    return out


# ---------- color math ----------

def parse_color(value):
    v = value.strip().lower()
    if v in NAMED:
        v = NAMED[v]
    if v in ("transparent", "currentcolor", "inherit", "initial", "unset", "none"):
        return None
    m = re.fullmatch(HEX, v)
    if m:
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)
    m = re.fullmatch(r"(rgba?|hsla?)\(([^()]*)\)", v)
    if not m:
        return None
    parts = [p for p in re.split(r"[\s,/]+", m.group(2).strip()) if p]
    if len(parts) < 3:
        return None
    try:
        def num(p, scale):
            return float(p[:-1]) * scale / 100 if p.endswith("%") else float(p.replace("deg", ""))
        a = 1.0
        if len(parts) > 3:
            a = float(parts[3][:-1]) / 100 if parts[3].endswith("%") else float(parts[3])
        if m.group(1).startswith("rgb"):
            r, g, b = (max(0, min(255, round(num(p, 255)))) for p in parts[:3])
        else:
            h = num(parts[0], 360) % 360 / 360
            s = max(0.0, min(1.0, num(parts[1], 1) if parts[1].endswith("%") else float(parts[1]) / 100))
            light = max(0.0, min(1.0, num(parts[2], 1) if parts[2].endswith("%") else float(parts[2]) / 100))
            r, g, b = (round(c * 255) for c in colorsys.hls_to_rgb(h, light, s))
        return (r, g, b, max(0.0, min(1.0, a)))
    except ValueError:
        return None


def blend(fg, bg):
    a = fg[3]
    return tuple(round(fg[i] * a + bg[i] * (1 - a)) for i in range(3)) + (1.0,)


def luminance(c):
    def ch(x):
        x /= 255
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(fg, bg):
    bg = blend(bg, (255, 255, 255, 1.0)) if bg[3] < 1 else bg
    fg = blend(fg, bg) if fg[3] < 1 else fg
    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def hexof(c):
    return "#%02x%02x%02x" % tuple(int(x) for x in c[:3])


def suggest(fg, bg, target):
    """Nearest foreground (same hue and saturation) that meets the target ratio."""
    h, light, s = colorsys.rgb_to_hls(*(x / 255 for x in fg[:3]))
    best = None
    for direction in (-1, 1):
        x = light
        while 0 <= x <= 1:
            c = tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, x, s)) + (1.0,)
            if ratio(c, bg) >= target:
                if best is None or abs(x - light) < best[0]:
                    best = (abs(x - light), c)
                break
            x += direction * 0.002
    return hexof(best[1]) if best else None


def lab(c):
    def ch(x):
        x /= 255
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in c[:3])
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return (116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z)))


def delta_e(a, b):
    return math.dist(lab(a), lab(b))


def to_px(value):
    m = re.fullmatch(r"\s*(-?\d*\.?\d+)(px|rem|em)?\s*", value)
    if not m:
        return None
    n = float(m.group(1))
    return n * 16 if m.group(2) in ("rem", "em") else (n if m.group(2) == "px" or n == 0 else None)


# ---------- analysis ----------

class Report:
    def __init__(self):
        self.items = {}

    def add(self, sev, rule, where, msg):
        self.items.setdefault((SEVERITY[sev], rule), []).append((where, msg))

    def counts(self):
        e = sum(len(v) for (s, _), v in self.items.items() if s == 0)
        return e, sum(len(v) for (s, _), v in self.items.items() if s == 1)


def line_at(text, pos):
    return text.count("\n", 0, pos) + 1


def strip_comments(text):
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


DARK_SCOPE = re.compile(r"\.dark\b|\[data-(?:theme|mode|color-scheme)\s*=\s*[\"']?dark|prefers-color-scheme\s*:\s*dark", re.I)


DARK_PREFIX = re.compile(r"^(?:html|:root|body)?(?:\.dark\b|\[data-(?:theme|mode|color-scheme)\s*=\s*[\"']?dark[\"']?\])\s*", re.I)


def in_dark_scope(text, m):
    before = text[max(0, m.start() - 300):m.start()]
    return bool(DARK_SCOPE.search(before[before.rfind("}") + 1:] + m.group(1)))


def css_vars(files):
    """Custom properties for the light (default) and dark themes, plus dark-theme color overrides per selector."""
    light, dark, dark_rules = {}, {}, {}
    for _, text in files:
        text = strip_comments(text)
        for m in BLOCK_RX.finditer(text):
            is_dark = in_dark_scope(text, m)
            target = dark if is_dark else light
            for d in re.finditer(r"(--[\w-]+)\s*:\s*([^;{}]+)", m.group(2)):
                target.setdefault(d.group(1), d.group(2).strip())
            if is_dark:
                for sel in m.group(1).strip().split("\n")[-1].split(","):
                    base = DARK_PREFIX.sub("", sel.strip()).strip()
                    for d in DECL_RX.finditer(m.group(2)):
                        prop = d.group(1).lower()
                        if base and prop in ("color", "background", "background-color"):
                            dark_rules.setdefault(base, {})["color" if prop == "color" else "background"] = d.group(2).strip()
    return light, dark, dark_rules


def resolve(value, defs, depth=0):
    if depth > 6:
        return value
    def sub(m):
        if m.group(1) in defs:
            return resolve(defs[m.group(1)], defs, depth + 1)
        return m.group(2).strip() if m.group(2) else m.group(0)
    return VAR_RX.sub(sub, value)


def first_color(value, defs):
    value = resolve(value, defs)
    for m in COLOR_RX.finditer(value):
        c = parse_color(m.group(0))
        if c:
            return c, m.group(0)
    for word in re.findall(r"[a-z]+", value.lower()):
        if word in NAMED:
            return parse_color(word), word
    return None, None


def check_pair(rep, where, fg, bg, fg_s, bg_s, large=False, sev="error"):
    if not fg or not bg:
        return
    target = 3.0 if large else 4.5
    r = ratio(fg, bg)
    if r < target:
        fix = suggest(fg, bg, target)
        rep.add(sev, "contrast", where, f"{r:.2f}:1 < {target}:1 ({fg_s} on {bg_s})" + (f"; try {fix}" if fix else ""))


def audit_css(rep, path, text, defs, ctx):
    text = strip_comments(text)
    token_file = bool(TOKEN_FILE.search(path))
    if re.search(r"prefers-reduced-motion", text):
        ctx["reduced_motion"] = True
    if re.search(r"@keyframes|\banimation\s*:", text):
        ctx["animations"].append(path)
    if re.search(r"@media[^{]*\b(?:min|max)-width|@container", text):
        ctx["responsive"] = True
    if re.search(r":focus-visible|:focus\b", text):
        ctx["focus_styles"] = True
    for m in re.finditer(r"@media[^{]*?\((?:min|max)-width\s*:\s*(\d+(?:\.\d+)?)(px|em|rem)", text):
        ctx["breakpoints"].add(float(m.group(1)) * (16 if m.group(2) != "px" else 1))
    for m in BLOCK_RX.finditer(text):
        sel_full = m.group(1).strip().split("\n")[-1].strip()
        for part in sel_full.split(","):
            part = part.strip()
            base = re.sub(r":(?:hover|focus-visible|focus|active|focus-within)\b", "", part).strip()
            if ":hover" in part:
                ctx["hover"].setdefault(base, f"{path}:{line_at(text, m.start(2))}")
            if re.search(r":focus(?:-visible|-within)?\b", part):
                ctx["focus"].add(base)
        if sel_full.startswith("@font-face") and "font-display" not in m.group(2):
            rep.add("warn", "performance", f"{path}:{line_at(text, m.start(2))}",
                    "@font-face without font-display: text stays invisible while the font loads; add font-display: swap")
        selector, body = m.group(1).strip().split("\n")[-1].strip(), m.group(2)
        where = f"{path}:{line_at(text, m.start(2))}"
        decls = {}
        for d in DECL_RX.finditer(body):
            prop, val = d.group(1).lower(), d.group(2).strip()
            decls[prop] = val
            dl = f"{path}:{line_at(text, m.start(2) + d.start())}"
            if not prop.startswith("--") and not token_file:
                for c in COLOR_RX.finditer(val):
                    ctx["colors"].append((c.group(0).lower(), dl))
            if SPACING_PROPS.match(prop) and "var(" not in val:
                for part in val.split():
                    px = to_px(part)
                    if px is not None:
                        ctx["spacing"].append((px, dl))
            if prop == "font-size" and "var(" not in val and "clamp" not in val:
                px = to_px(val)
                if px is not None:
                    ctx["font_sizes"].append((px, dl))
            if prop == "font-family":
                ctx["families"].add(val.split(",")[0].strip().strip("'\"").lower())
            if prop == "z-index" and re.fullmatch(r"-?\d+", val):
                ctx["z"].append((int(val), dl))
            if "!important" in val:
                ctx["important"] += 1
            if prop in ("background", "background-image") and "gradient(" in val:
                hues = []
                for c in COLOR_RX.finditer(resolve(val, defs)):
                    pc = parse_color(c.group(0))
                    if pc:
                        h, light, s = colorsys.rgb_to_hls(*(x / 255 for x in pc[:3]))
                        hues.append((h * 360, s))
                if hues and sum(1 for h, s in hues if 245 <= h <= 300 and s > 0.35) >= 1 and len(hues) >= 2:
                    rep.add("warn", "ai-default", dl, "purple/indigo gradient: the most common generated look; use the brand palette")
            if prop == "border-radius" and "var(" not in val:
                for part in val.split():
                    px = to_px(part)
                    if px is not None and px < 999:
                        ctx["radii"].add(px)
            if prop in ("transition", "transition-property") and re.search(r"(?:^|[\s,])all\b", val):
                rep.add("warn", "motion", dl, "transition: all also animates layout; list properties (transform, opacity)")
            if prop in ("transition", "transition-timing-function", "animation", "animation-timing-function") and re.search(r"\bease-in\b(?!-)", val):
                rep.add("warn", "motion", dl, "ease-in feels sluggish on UI; use ease-out to enter and exit")
            if prop in ("transition", "transition-property") and re.search(
                    r"(?:^|[\s,])(?:width|height|top|left|right|bottom|margin(?:-\w+)?|padding(?:-\w+)?|max-height)\b", val):
                rep.add("warn", "performance", dl, "animating layout properties reflows every frame; animate transform or opacity")
            if re.search(r"(?<![\w-])100vh\b", val) and "dvh" not in body and "svh" not in body:
                rep.add("warn", "responsive", dl, "100vh is taller than the visible area on phones; use 100dvh (keep 100vh as a fallback)")
            if prop == "transform" and re.search(r"scale\(\s*0\s*\)", val):
                rep.add("warn", "motion", dl, "scale(0) entrance pops from nothing; start near scale(0.95) with opacity 0")
            if re.fullmatch(r"(?:-webkit-)?background-clip", prop) and val.startswith("text"):
                rep.add("warn", "ai-default", dl, "gradient text: a common generated look and hard to read; use a solid color")
        if decls.get("text-transform") == "uppercase" and "letter-spacing" in decls:
            size = to_px(resolve(decls.get("font-size", ""), defs) or "x")
            if size and size <= 14:
                ctx["eyebrows"].append(where)
        if re.search(r"\b(?:input|select|textarea)\b", selector) and not re.search(r"\[type=.?(?:checkbox|radio)", selector):
            size = to_px(resolve(decls.get("font-size", ""), defs) or "x")
            if size and size < 16:
                rep.add("warn", "responsive", where, f"{selector[:30]} font-size {size:g}px: iOS zooms into inputs under 16px")
        if decls.get("outline", "").strip() in ("none", "0", "0px") or decls.get("outline-width", "") in ("0", "0px"):
            if "focus-visible" not in selector and not any(k in decls for k in ("box-shadow", "border-color")):
                ctx["outline_removed"].append((where, selector[:40]))
        fg_v = decls.get("color")
        bg_v = decls.get("background-color") or decls.get("background")
        dark_rule = in_dark_scope(text, m)  # its colors are checked through the light rule it overrides
        if bg_v and re.fullmatch(r"(?:html|body|:root)(?:\s*,\s*(?:html|body|:root))*", selector) and "gradient(" not in bg_v:
            ctx["page_bg"] = bg_v
        elif fg_v and not bg_v and ":" not in selector and not selector.startswith("@") and not dark_rule:
            size = to_px(resolve(decls.get("font-size", ""), defs) or "x") or 0
            ctx["fg_only"].append((where, fg_v, size >= 24, selector))
        if fg_v and bg_v and "gradient(" not in bg_v and "url(" not in bg_v and not dark_rule:
            size = to_px(resolve(decls.get("font-size", ""), defs) or "x") or 0
            bold = decls.get("font-weight", "").strip() in ("bold", "600", "700", "800", "900")
            large = size >= 24 or (bold and size >= 18.66)
            fg, fs = first_color(fg_v, defs)
            bg, bs = first_color(bg_v, defs)
            check_pair(rep, where, fg, bg, fs, bs, large)
            override = ctx["dark_rules"].get(selector, {})
            if (ctx["dark"] and "var(" in fg_v + bg_v) or override:
                both = {**defs, **ctx["dark"]}
                dfg, dfs = first_color(override.get("color", fg_v), both)
                dbg, dbs = first_color(override.get("background", bg_v), both)
                if (dfg, dbg) != (fg, bg):
                    check_pair(rep, where, dfg, dbg, dfs, dbs + " in dark theme" if dbs else dbs, large)
        if re.search(r"\b(button|btn|\[role=.?button|icon-?button|\ba\b)", selector, re.I):
            for prop in ("height", "min-height"):
                px = to_px(decls.get(prop, "") or "x")
                if px and px < 24:
                    rep.add("error", "touch-target", where, f"{selector[:30]} {prop} {px:g}px < 24px (WCAG 2.5.8; aim for 44px)")
        w = to_px(decls.get("width", "") or "x")
        if w and w >= 500 and "max-width" not in decls:
            rep.add("warn", "responsive", where, f"fixed width {w:g}px without max-width overflows phones")


EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌]")
SLOP_WORDS = re.compile(r"\b(?:seamless(?:ly)?|unlock|elevate|revolutioni[sz]e|supercharge|game[- ]chang(?:er|ing)|cutting[- ]edge|"
                        r"next[- ]level|effortless(?:ly)?|empower|leverage|synerg\w*|world[- ]class|best[- ]in[- ]class|unleash)\b", re.I)


def audit_markup(rep, path, text, defs, ctx):
    ext = Path(path).suffix.lower()
    if re.search(r"\b(?:sm|md|lg|xl|2xl):[\w-]|@media|useMediaQuery|matchMedia", text):
        ctx["responsive"] = True
    if re.search(r"motion-reduce|motion-safe|prefers-reduced-motion|useReducedMotion", text):
        ctx["reduced_motion"] = True
    if re.search(r"\banimate-(?!none)[\w-]+|@keyframes|framer-motion|\bmotion\.\w+", text):
        ctx["animations"].append(path)
    if re.search(r"focus-visible:|focus:ring|focus:outline-(?!none)|:focus-visible", text):
        ctx["focus_styles"] = True
    if ext in (".html", ".htm"):
        if re.search(r"<html\b(?![^>]*\blang=)", text, re.I):
            rep.add("error", "lang", f"{path}:{line_at(text, re.search(r'<html', text, re.I).start())}", "<html> has no lang attribute")
        if re.search(r"<head\b", text, re.I) and not re.search(r"<meta[^>]+name=[\"']viewport", text, re.I):
            rep.add("error", "viewport", f"{path}:1", "no <meta name=\"viewport\">: phones render the desktop layout zoomed out")
    zoom = re.search(r"<meta[^>]+name=[\"']viewport[^>]*(?:user-scalable\s*=\s*(?:no|0)|maximum-scale\s*=\s*1(?:\.0)?\b)", text, re.I)
    if zoom:
        rep.add("error", "zoom", f"{path}:{line_at(text, zoom.start())}", "viewport blocks pinch zoom (user-scalable=no / maximum-scale=1)")
    for m in re.finditer(r"<(button|h[1-6]|a)\b[^>]*>([^<]{0,80})", text, re.I):
        if EMOJI.search(m.group(2)):
            rep.add("warn", "ai-default", f"{path}:{line_at(text, m.start())}", f"emoji used as an icon in <{m.group(1)}>; use an SVG icon")
    for m in re.finditer(r">([^<>{}]{3,300})<", text):
        words = SLOP_WORDS.findall(m.group(1))
        if words:
            rep.add("warn", "copy", f"{path}:{line_at(text, m.start())}", f"filler marketing words ({', '.join(dict.fromkeys(w.lower() for w in words))}): say what it does")
        if re.search(r"\bclick here\b", m.group(1), re.I):
            rep.add("warn", "copy", f"{path}:{line_at(text, m.start())}", "\"click here\": link text should name the destination")
    for m in re.finditer(r"<img\b([^>]*)>", text):
        attrs, where = m.group(1), f"{path}:{line_at(text, m.start())}"
        spread = "{..." in attrs
        if not re.search(r"\balt\s*=", attrs) and not spread:
            rep.add("error", "alt-text", where, "<img> without alt (use alt=\"\" if decorative)")
        if not spread and not (re.search(r"\bwidth\s*=", attrs) and re.search(r"\bheight\s*=", attrs)) \
                and not re.search(r"aspect-|\bfill\b|\b[wh]-(?:\d|full|\[)|size-", attrs):
            rep.add("warn", "performance", where, "<img> without width and height (or aspect-ratio) shifts the layout when it loads")
    for m in re.finditer(r"<a\b([^>]*?)\bon[Cc]lick\s*=", text):
        attrs = m.group(1) + text[m.end():m.end() + 200].split(">")[0]
        if not re.search(r"\bhref\s*=", attrs) and not re.search(r"\brole\s*=", attrs):
            rep.add("error", "semantics", f"{path}:{line_at(text, m.start())}", "<a> with onClick but no href is not focusable; use <button>")
    for m in re.finditer(r"<div\b[^>]*\brole\s*=\s*[\"'](?:alert)?dialog[\"'][^>]*>", text):
        if "aria-modal" not in m.group(0):
            rep.add("warn", "semantics", f"{path}:{line_at(text, m.start())}",
                    "custom dialog: prefer <dialog>, or add aria-modal, a focus trap, Esc to close, and focus return")
    for m in re.finditer(r"<input\b([^>]*)>", text):
        if re.search(r"type\s*=\s*[\"'](?:email|tel|password)[\"']", m.group(1)) and "autoComplete" not in m.group(1) \
                and "autocomplete" not in m.group(1) and "{..." not in m.group(1):
            rep.add("warn", "forms", f"{path}:{line_at(text, m.start())}", "email/tel/password input without autocomplete: browsers cannot fill it")
    for m in re.finditer(r"<(div|span|li|td|p)\b([^>]*?)\bon[Cc]lick\s*=", text):
        attrs = m.group(2) + text[m.end():m.end() + 200].split(">")[0]
        if not re.search(r"\brole\s*=", attrs):
            rep.add("error", "semantics", f"{path}:{line_at(text, m.start())}",
                    f"clickable <{m.group(1)}> is not keyboard-reachable; use <button> or <a href>")
    for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", text, re.S | re.I):
        attrs, inner = m.group(1), m.group(2)
        if re.search(r"aria-label|aria-labelledby|\btitle\s*=", attrs):
            continue
        visible = re.sub(r"<[^>]*>|\{[^{}]*\}", " ", inner)
        if not visible.strip() and re.search(r"<svg|<[A-Z]\w*(?:Icon)?\b|<i\b|<img", inner) and "{" not in inner.replace("{/*", ""):
            rep.add("error", "label", f"{path}:{line_at(text, m.start())}", "icon-only <button> needs aria-label")
    for m in re.finditer(r"<(input|select|textarea)\b([^>]*)>", text, re.I):
        attrs = m.group(2)
        if re.search(r"type\s*=\s*[\"'](?:hidden|submit|button|reset|image)[\"']", attrs, re.I):
            continue
        if re.search(r"aria-label|aria-labelledby|\{\.\.\.", attrs):
            continue
        ident = re.search(r"\bid\s*=\s*[\"']([^\"']+)[\"']", attrs)
        if ident and re.search(r"(?:for|htmlFor)\s*=\s*[\"']" + re.escape(ident.group(1)) + "[\"']", text):
            continue
        before = text[max(0, m.start() - 300):m.start()]
        if before.rfind("<label") > before.rfind("</label>"):
            continue
        hint = " (a placeholder is not a label)" if "placeholder" in attrs else ""
        rep.add("error", "label", f"{path}:{line_at(text, m.start())}", f"<{m.group(1)}> has no label{hint}")
    for m in re.finditer(r"tab[Ii]ndex\s*=\s*\{?\s*[\"']?([1-9]\d*)", text):
        rep.add("error", "focus-order", f"{path}:{line_at(text, m.start())}", "positive tabIndex breaks keyboard order")
    for m in CLASS_ATTR.finditer(text):
        classes, where = m.group(2), f"{path}:{line_at(text, m.start())}"
        if re.search(r"(?<![\w:-])(?:focus:)?outline-none\b", classes) and not re.search(r"focus(?:-visible)?:(?:ring|outline-|border|shadow)", classes):
            ctx["outline_removed"].append((where, "outline-none"))
        if TW_SLOP.search(classes):
            rep.add("warn", "ai-default", where, "purple/indigo gradient classes: the most common generated look; use the brand palette")
        if re.search(r"(?<![\w-])bg-clip-text\b", classes) and "gradient" in classes:
            rep.add("warn", "ai-default", where, "gradient text: a common generated look and hard to read; use a solid color")
        if re.search(r"(?<![\w:-])transition-all\b", classes):
            rep.add("warn", "motion", where, "transition-all also animates layout; use transition-colors / transition-transform")
        if re.search(r"(?<![\w:-])ease-in\b(?!-)", classes):
            rep.add("warn", "motion", where, "ease-in feels sluggish on UI; use ease-out to enter and exit")
        if re.search(r"(?<![\w:-])uppercase\b", classes) and re.search(r"(?<![\w:-])tracking-(?:wide|wider|widest|\[)", classes) \
                and re.search(r"(?<![\w:-])text-(?:xs|sm)\b", classes):
            ctx["eyebrows"].append(where)
        for s in TW_SPACE.finditer(classes):
            ctx["spacing"].append((float(s.group(1)) * (16 if s.group(2) == "rem" else 1), where))
        for s in TW_TEXT_SIZE.finditer(classes):
            ctx["font_sizes"].append((float(s.group(1)) * (16 if s.group(2) == "rem" else 1), where))
        pair = {}
        for c in TW_COLOR.finditer(classes):
            if c.start() > 0 and classes[c.start() - 1] == ":":
                continue  # hover:, dark:, md: variants describe another state
            raw = c.group(2).strip("[]")
            col = parse_color(raw)
            if col and c.group(3):
                col = col[:3] + (int(c.group(3)) / 100,)
            pair[c.group(1)] = (col, raw)
            if raw.startswith(("#", "rgb", "hsl")):
                ctx["colors"].append((raw.lower(), where))
        if "text" in pair and "bg" in pair:
            large = bool(re.search(r"(?<![\w:-])text-(?:2xl|[3-9]xl)\b", classes)) or (
                bool(re.search(r"(?<![\w:-])text-xl\b", classes)) and bool(re.search(r"(?<![\w:-])font-(?:semibold|bold|extrabold|black)\b", classes)))
            check_pair(rep, where, pair["text"][0], pair["bg"][0], pair["text"][1], pair["bg"][1], large)
    for m in list(STYLE_OBJ.finditer(text)) + list(STYLE_ATTR.finditer(text)):
        body, where = m.group(1), f"{path}:{line_at(text, m.start())}"
        fg = re.search(r"(?<![\w-])color\s*:\s*['\"]?([^'\",;}]+)", body)
        bg = re.search(r"background(?:Color|-color)?\s*:\s*['\"]?([^'\",;}]+)", body)
        for c in COLOR_RX.finditer(body):
            ctx["colors"].append((c.group(0).lower(), where))
        if fg and bg:
            f, fs = first_color(fg.group(1), defs)
            b, bs = first_color(bg.group(1), defs)
            check_pair(rep, where, f, b, fs, bs)


def audit_components(rep, path, text):
    """Is this the right component for the job? Flags common misfits; `design.py choose` explains the alternatives."""
    def at(pos):
        return f"{path}:{line_at(text, pos)}"
    for m in re.finditer(r"<select\b([^>]*)>(.*?)</select>", text, re.S | re.I):
        if re.search(r"\bmultiple\b", m.group(1)):
            rep.add("warn", "component", at(m.start()), "multi-select <select> is hard to use; use checkboxes or a multi-select combobox (choose \"pick several\")")
            continue
        opts = [o for o in re.findall(r"<option\b([^>]*)>(.*?)</option>", m.group(2), re.S | re.I)
                if not re.search(r"\bdisabled\b|value\s*=\s*[\"'][\"']", o[0]) and o[1].strip()]
        if "{" in m.group(2) and not opts:
            continue  # options rendered from data; count unknown
        if 0 < len(opts) <= 3:
            rep.add("warn", "component", at(m.start()), f"<select> with {len(opts)} options hides them behind a click; use radio buttons or a segmented control")
        elif len(opts) > 15:
            rep.add("warn", "component", at(m.start()), f"<select> with {len(opts)} options: use a combobox with type-to-search")
    radios = {}
    for m in re.finditer(r"<input\b[^>]*type\s*=\s*[\"']radio[\"'][^>]*>", text, re.I):
        name = re.search(r"\bname\s*=\s*[\"']([^\"']+)", m.group(0))
        if name:
            radios.setdefault(name.group(1), []).append(m.start())
    for name, spots in radios.items():
        if len(spots) > 7:
            rep.add("warn", "component", at(spots[0]), f"{len(spots)} radio buttons in '{name}': use a select (8-15) or a searchable combobox")
        elif len(spots) == 1 and not re.search(r"\.map\(|\$\{|forEach|v-for|\{#each|ngFor", text):  # rendered in a loop: count unknown
            rep.add("warn", "component", at(spots[0]), f"a single radio button '{name}' cannot be unselected; use a checkbox")
    for m in re.finditer(r"<dialog\b[^>]*>(.*?)</dialog>|<div\b[^>]*role\s*=\s*[\"']dialog[\"'][^>]*>(.*?)(?=<div\b[^>]*role\s*=\s*[\"']dialog|\Z)",
                         text, re.S | re.I):
        body = m.group(1) or m.group(2) or ""
        body = body[:20000]
        fields = len(re.findall(r"<(?:input|select|textarea)\b(?![^>]*type\s*=\s*[\"'](?:hidden|submit|button)[\"'])", body, re.I))
        if fields > 6:
            rep.add("warn", "component", at(m.start()), f"form with {fields} fields inside a modal: use its own page or a drawer")
        if m.group(1) and re.search(r"<dialog\b|role\s*=\s*[\"']dialog", body, re.I):
            rep.add("warn", "component", at(m.start()), "a dialog inside a dialog: flatten into steps or a page")
    tabs = re.findall(r"role\s*=\s*[\"']tab[\"']", text)
    if len(tabs) == 1:
        rep.add("warn", "component", f"{path}", "a tab list with one tab: show the content directly")
    elif len(tabs) > 7:
        rep.add("warn", "component", f"{path}", f"{len(tabs)} tabs: use side or top navigation (tabs over 5-7 wrap or hide)")
    if re.search(r"\b(?:carousel|swiper|slick-slider|splide|glide__|embla)\b", text, re.I):
        m = re.search(r"\b(?:carousel|swiper|slick-slider|splide|glide__|embla)\b", text, re.I)
        rep.add("warn", "component", at(m.start()), "carousel: rotating slides hide content; use a grid or a scrollable row (choose \"featured items\")")
    primaries = re.findall(r"\b(?:btn-primary|button--primary|button-primary|variant\s*=\s*[\"'{]?\s*[\"']?primary)\b", text)
    if len(primaries) > 2:
        rep.add("warn", "component", f"{path}", f"{len(primaries)} primary buttons in one file: keep one primary action per view")
    for m in re.finditer(r"<button\b[^>]*type\s*=\s*[\"']submit[\"'][^>]*\bdisabled\b(?![-\w])[^>]*>", text, re.I):
        near = text[max(0, m.start() - 800):m.end() + 200]
        typed_confirmation = re.search(r"confirm|danger|destructive|delete|remove|type\s+[\"'“]?[A-Z]{3,}", near, re.I)
        if "aria-describedby" not in m.group(0) and not typed_confirmation:  # disabled until "type DELETE" is the right pattern
            rep.add("warn", "component", at(m.start()), "disabled submit button with no reason: keep it enabled and show what is missing on submit")
    for m in re.finditer(r"<a\b[^>]*href\s*=\s*[\"']#[\"'][^>]*>", text, re.I):
        if re.search(r"on[Cc]lick", m.group(0)):
            rep.add("error", "semantics", at(m.start()), "<a href=\"#\"> used as a button: use <button type=\"button\">")
    for m in re.finditer(r"<a\b[^>]*target\s*=\s*[\"']_blank[\"'][^>]*>", text, re.I):
        if not re.search(r"rel\s*=\s*[\"'][^\"']*noopener|rel\s*=\s*[\"'][^\"']*noreferrer", m.group(0)):
            rep.add("warn", "component", at(m.start()), "target=_blank without rel=\"noopener\"; also say it opens a new tab")


def audit_component_css(rep, path, text):
    text = strip_comments(text)
    hover_menu = re.search(r":hover\s*>\s*(?:ul|ol|\.?[\w-]*(?:menu|dropdown|submenu)[\w-]*)\s*\{[^}]*(?:display|visibility|opacity)", text)
    if hover_menu and ":focus-within" not in text:
        rep.add("warn", "component", f"{path}:{line_at(text, hover_menu.start())}",
                "menu opens on hover only: open it on click and :focus-within, or keyboard and touch users cannot reach it")


def page_contrast(rep, ctx):
    """Text that sets a color but no background sits on the page background (body/html), in each theme."""
    if not ctx["page_bg"]:
        return
    themes = [("", ctx["light"])] + ([(" in dark theme", {**ctx["light"], **ctx["dark"]})] if ctx["dark"] else [])
    seen = set()
    for where, fg_v, large, selector in ctx["fg_only"]:
        for label, defs in themes:
            if label:
                fg_v = ctx["dark_rules"].get(selector, {}).get("color", fg_v)
            fg, fs = first_color(fg_v, defs)
            bg, bs = first_color(ctx["page_bg"], defs)
            if not fg or not bg or (fg_v, label) in seen:
                continue
            seen.add((fg_v, label))
            check_pair(rep, where, fg, bg, fs, f"page {bs}{label}", large, sev="warn")  # a guess: the element may sit on its own section


def scale_drift(rep, ctx):
    off = [(v, w) for v, w in ctx["spacing"] if abs(v) > 2 and abs(v) % 4]
    if off:
        sample = ", ".join(f"{v:g}px {w}" for v, w in off[:3])
        rep.add("warn", "spacing-scale", off[0][1], f"{len(off)} spacing values off the 4px grid: {sample}")
    distinct = sorted({abs(v) for v, _ in ctx["spacing"] if v})
    if len(distinct) > 12:
        rep.add("warn", "spacing-scale", ctx["spacing"][0][1], f"{len(distinct)} distinct spacing values; a scale needs about 8")
    sizes = sorted({round(v, 1) for v, _ in ctx["font_sizes"]})
    if len(sizes) > 8:
        rep.add("warn", "type-scale", ctx["font_sizes"][0][1], f"{len(sizes)} font sizes ({', '.join(f'{s:g}' for s in sizes[:10])}px); pick 5-7 from one scale")
    for v, w in ctx["font_sizes"]:
        if 0 < v < 12:
            rep.add("warn", "type-scale", w, f"font-size {v:g}px is too small to read; 12px minimum, 16px for body text")
    if len(ctx["families"] - {"inherit", "monospace", "sans-serif", "serif", "system-ui"}) > 3:
        rep.add("warn", "type-scale", "", f"{len(ctx['families'])} font families: {', '.join(sorted(ctx['families'])[:5])}; use 1-2")
    parsed = {}
    for raw, where in ctx["colors"]:
        c = parse_color(raw)
        if c and c[3] > 0:
            parsed.setdefault(hexof(c), []).append(where)
    if len(parsed) > 12:
        top = sorted(parsed.items(), key=lambda kv: -len(kv[1]))[:4]
        rep.add("warn", "tokens", top[0][1][0], f"{len(parsed)} hard-coded colors; most used: "
                + ", ".join(f"{h} x{len(w)}" for h, w in top) + " -> move them into tokens")
    keys = list(parsed)[:150]
    near = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if delta_e(parse_color(a), parse_color(b)) < 3:
                near.append((a, b))
    if near:
        rep.add("warn", "tokens", parsed[near[0][0]][0], f"{len(near)} near-duplicate colors (look the same): "
                + ", ".join(f"{a}~{b}" for a, b in near[:3]))
    big = [(v, w) for v, w in ctx["z"] if v >= 100]
    if len({v for v, _ in ctx["z"]}) > 6 or big:
        rep.add("warn", "z-index", (big or ctx["z"])[0][1], f"{len({v for v, _ in ctx['z']})} z-index values, max {max(v for v, _ in ctx['z'])}; use a named layer scale")
    interactive = re.compile(r"\b(?:button|btn|a|link|tab|menu-?item|nav-?item|chip|toggle|option|input|select|textarea)\b|\[role", re.I)
    global_focus = bool(ctx["focus"] & {"", "*", "html", "body", ":root"})  # a bare :focus-visible rule covers everything
    no_focus = [] if global_focus else [(b, w) for b, w in ctx["hover"].items() if interactive.search(b) and b not in ctx["focus"]]
    if no_focus:
        rep.add("warn", "states", no_focus[0][1], f"{len(no_focus)} interactive selectors style :hover but not :focus-visible: "
                + ", ".join(b[:25] for b, _ in no_focus[:3]))
    if len(ctx["breakpoints"]) > 5:
        rep.add("warn", "tokens", "", f"{len(ctx['breakpoints'])} different breakpoints ({', '.join(f'{b:g}' for b in sorted(ctx['breakpoints'])[:8])}px); use 3-5 named ones")
    if len(ctx["radii"]) > 4:
        rep.add("warn", "tokens", "", f"{len(ctx['radii'])} border radii ({', '.join(f'{r:g}' for r in sorted(ctx['radii'])[:8])}px); use 2-3 radius tokens")
    if len(ctx["eyebrows"]) >= 2:
        rep.add("warn", "ai-default", ctx["eyebrows"][0], f"{len(ctx['eyebrows'])} small tracked all-caps labels (eyebrows): a common generated look; keep only ones that carry information")
    named = ctx["families"] - {"inherit", "monospace", "sans-serif", "serif", "system-ui", "-apple-system", "ui-sans-serif", "ui-monospace"}
    if named and named <= {"inter", "roboto", "arial", "helvetica", "helvetica neue", "open sans"}:
        rep.add("warn", "ai-default", "", f"only default fonts ({', '.join(sorted(named))}): fine for app UI; a brand or marketing page needs a chosen typeface")
    light_colors = [n for n, v in ctx["light"].items() if first_color(resolve(v, ctx["light"]), {})[0]]
    if ctx["dark"] and light_colors:
        missing = [n for n in light_colors if n not in ctx["dark"]]
        if len(missing) > max(2, len(light_colors) // 3):
            rep.add("warn", "tokens", "", f"{len(missing)}/{len(light_colors)} color tokens have no dark-theme value: {', '.join(missing[:4])}")
    if ctx["important"] > 10:
        rep.add("warn", "specificity", "", f"{ctx['important']} !important declarations")
    if ctx["animations"] and not ctx["reduced_motion"]:
        rep.add("warn", "motion", ctx["animations"][0], "animations without a prefers-reduced-motion (motion-reduce:) fallback")
    if ctx["ui_files"] >= 3 and not ctx["responsive"]:
        rep.add("warn", "responsive", "", "no media queries or responsive classes found; check 375px, 768px, 1280px")
    if ctx["outline_removed"] and not ctx["focus_styles"]:
        for where, sel in ctx["outline_removed"][:5]:
            rep.add("error", "focus", where, f"{sel}: focus outline removed with no :focus-visible replacement")
    elif ctx["outline_removed"]:
        where, sel = ctx["outline_removed"][0]
        rep.add("warn", "focus", where, f"{len(ctx['outline_removed'])} elements remove the outline; confirm each has a visible focus style")


def run_audit(a):
    root = Path(a.dir).resolve()
    targets = [Path(t) if Path(t).is_absolute() else root / t for t in (a.paths or ["."])]
    files = collect(targets, root, a.changed)
    all_styles = files if not a.changed else collect([root], root)
    defs, dark, dark_rules = css_vars(all_styles)
    rep = Report()
    ctx = {"colors": [], "spacing": [], "font_sizes": [], "families": set(), "z": [], "important": 0, "animations": [],
           "reduced_motion": False, "responsive": False, "focus_styles": False, "outline_removed": [], "ui_files": len(files),
           "radii": set(), "eyebrows": [], "light": defs, "dark": dark, "hover": {}, "focus": set(), "breakpoints": set(),
           "page_bg": None, "fg_only": [], "dark_rules": dark_rules}
    for path, text in files:
        r = rel(path, root)
        if path.suffix.lower() in STYLE_EXT:
            audit_css(rep, r, text, defs, ctx)
            audit_component_css(rep, r, text)
        else:
            audit_markup(rep, r, text, defs, ctx)
            audit_components(rep, r, text)
            for block in re.finditer(r"<style[^>]*>(.*?)</style>|css`(.*?)`|styled\.\w+`(.*?)`", text, re.S):
                idx = next(i for i, g in enumerate(block.groups(), 1) if g is not None)
                inner = "\n" * (line_at(text, block.start(idx)) - 1) + block.group(idx)  # keep real line numbers
                audit_css(rep, r, inner, defs, ctx)
    page_contrast(rep, ctx)
    scale_drift(rep, ctx)
    errors, warns = rep.counts()
    out = [f"design audit: {len(files)} UI files; {errors} errors, {warns} warnings" + (" (changed files only)" if a.changed else "")]
    if not files:
        out[0] = "design audit: no UI files found (css, scss, html, jsx, tsx, vue, svelte, astro)"
    for (sev, rule), items in sorted(rep.items.items()):
        label = "ERROR" if sev == 0 else "warn"
        for where, msg in items[:a.per_rule]:
            out.append(f"{label} {rule}: {msg}" + (f"  {where}" if where else ""))
        if len(items) > a.per_rule:
            out.append(f"  (+{len(items) - a.per_rule} more {rule})")
    text = "\n".join(out)
    if len(text) > a.max_chars:
        text = text[:a.max_chars].rsplit("\n", 1)[0] + f"\n[truncated; narrow with a path, --changed, or --per-rule 1]"
    print(text)
    if not files:
        return 0
    return 1 if a.strict and errors else 0


def run_tokens(a):
    root = Path(a.dir).resolve()
    target = Path(a.path) if Path(a.path).is_absolute() else root / a.path
    files = collect([target], root)
    defs = {}
    where = {}
    for path, text in files:
        for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;{}]+)", strip_comments(text)):
            if m.group(1) not in defs:
                defs[m.group(1)] = m.group(2).strip()
                where[m.group(1)] = rel(path, root)
    groups = {"color": [], "space": [], "type": [], "radius": [], "shadow": [], "other": []}
    for name, val in defs.items():
        n = name.lower()
        res = resolve(val, defs)
        if "shadow" in n:
            g = "shadow"
        elif "radius" in n or "rounded" in n:
            g = "radius"
        elif re.search(r"font|text|leading|line-height|tracking|weight", n):
            g = "type"
        elif first_color(res, {})[0] and not re.search(r"\d(px|rem)", res):
            g = "color"
        elif re.search(r"space|gap|pad|margin|size|gutter", n) or to_px(res) is not None:
            g = "space"
        else:
            g = "other"
        groups[g].append(f"{name}: {val[:40]}")
    out = [f"tokens: {len(defs)} CSS variables in {len({*where.values()})} files"]
    for g, items in groups.items():
        if items:
            out.append(f"{g} ({len(items)}): " + "; ".join(items[:a.per_group]) + (f"; +{len(items) - a.per_group} more" if len(items) > a.per_group else ""))
    for cfg in sorted(root.glob("tailwind.config.*")) + sorted(root.glob("*/tailwind.config.*")):
        try:
            t = cfg.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        keys = re.findall(r"\b(colors|fontFamily|fontSize|spacing|borderRadius|boxShadow|screens)\s*:", t)
        out.append(f"tailwind: {rel(cfg, root)} theme keys: {', '.join(dict.fromkeys(keys)) or 'defaults only'}")
    if re.search(r"@theme\b", "".join(t for _, t in files)):
        out.append("tailwind v4: @theme block found (tokens are the --color-*, --spacing-*, --font-* variables above)")
    counts = {}
    for path, text in files:
        if TOKEN_FILE.search(path.name):
            continue
        for line in re.sub(r"--[\w-]+\s*:[^;{}]*", "", strip_comments(text)).splitlines():
            for c in COLOR_RX.finditer(line):
                pc = parse_color(c.group(0))
                if pc:
                    counts[hexof(pc)] = counts.get(hexof(pc), 0) + 1
    if counts:
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:8]
        out.append(f"hard-coded colors outside tokens ({len(counts)}): " + ", ".join(f"{h} x{n}" for h, n in top))
    if len(out) == 1 and not defs:
        out.append("no tokens found: generate a starter set with `design.py scale`, then define colors from the brand")
    text = "\n".join(out)
    print(text if len(text) <= a.max_chars else text[:a.max_chars].rsplit("\n", 1)[0] + "\n[truncated]")
    return 0


def run_contrast(a):
    fg, bg = parse_color(a.fg), parse_color(a.bg)
    if not fg or not bg:
        print("could not parse a color; use #hex, rgb(), hsl(), or a basic name")
        return 2
    r = ratio(fg, bg)
    rows = [("normal text AA", 4.5), ("large text AA", 3.0), ("UI / icons AA", 3.0), ("normal text AAA", 7.0)]
    print(f"{a.fg} on {a.bg}: {r:.2f}:1")
    for name, t in rows:
        print(f"  {'pass' if r >= t else 'FAIL'}  {name} ({t}:1)")
    target = 3.0 if a.large else 4.5
    if r < target:
        fix = suggest(fg, bg, target)
        if fix:
            print(f"  nearest passing foreground: {fix} ({ratio(parse_color(fix), bg):.2f}:1)")
    return 0 if r >= target else 1


def run_scale(a):
    names = ["xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl"]
    print(":root {")
    print(f"  /* type: base {a.base:g}px, ratio {a.ratio:g} */")
    for i, n in enumerate(names):
        px = a.base * a.ratio ** (i - 2)
        lh = 1.5 if i <= 3 else (1.3 if i <= 5 else 1.15)
        print(f"  --text-{n}: {px / 16:.3f}rem; --leading-{n}: {lh};")
    print("  /* space: 4px grid */")
    for i, px in enumerate([0, 4, 8, 12, 16, 24, 32, 48, 64, 96], 0):
        print(f"  --space-{i}: {px / 16:g}rem;")
    print("  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px; --radius-full: 9999px;")
    print("  --measure: 65ch; /* readable line length */")
    print("}")
    return 0


# ---------- project directions: a design generated for each project ----------

REF = Path(__file__).resolve().parent.parent / "references"
FONT_POOLS = {  # all free on Google Fonts
    "grotesk": ["Geist", "Hanken Grotesk", "Schibsted Grotesk", "Space Grotesk", "Familjen Grotesk", "Inter Tight", "Onest",
                "Instrument Sans", "Archivo", "Bricolage Grotesque"],
    "grotesk-expressive": ["Bricolage Grotesque", "Syne", "Unbounded", "Space Grotesk", "Familjen Grotesk"],
    "humanist": ["Source Sans 3", "Public Sans", "Atkinson Hyperlegible", "Figtree", "Albert Sans", "Libre Franklin", "Work Sans",
                 "Red Hat Text", "Mulish"],
    "geometric": ["Plus Jakarta Sans", "Manrope", "Outfit", "DM Sans", "Lexend", "Sora", "Urbanist", "Jost"],
    "rounded": ["Nunito", "Baloo 2", "Quicksand", "Fredoka", "Rubik", "Varela Round"],
    "serif-text": ["Source Serif 4", "Literata", "Lora", "Newsreader", "Spectral", "Crimson Pro", "EB Garamond", "Petrona"],
    "serif-display": ["Fraunces", "DM Serif Display", "Playfair Display", "Instrument Serif", "Young Serif", "Cormorant Garamond",
                      "Bodoni Moda", "Gloock", "Libre Caslon Display"],
    "condensed": ["Big Shoulders Display", "Archivo Black", "Anton", "Oswald", "Bebas Neue", "Unbounded"],
    "mono": ["JetBrains Mono", "IBM Plex Mono", "Space Mono", "DM Mono", "Geist Mono", "Source Code Pro", "Fira Code"],
}
SERIF_VOICES = {"serif-text", "serif-display"}
LAYOUTS = {
    "Operate": ["sidebar navigation + content, page title with primary action top right",
                "top bar + full-width content with a summary strip above the main table or list",
                "list on the left, detail on the right (stacks to one column on phones)",
                "command-first: search or command bar on top, content below, minimal chrome",
                "tabs across the top of a single focused workspace"],
    "Read": ["centered reading column (60-75ch) with a sticky table of contents on wide screens",
             "magazine front page: one lead story large, the rest in a typographic list",
             "left navigation tree, article in the middle, on-page outline on the right"],
    "Persuade": ["split hero: words on one side, real product or photo on the other, then proof, then one CTA",
                 "editorial long scroll: big statement, story sections that alternate image and text",
                 "product-first: the product or photo is the hero, details and price beside it",
                 "chaptered page: numbered chapters only if the content is a real sequence",
                 "one full-bleed image or video with a short line and a single action"],
    "Experience": ["full-bleed immersive sections with one authored transition",
                   "asymmetric grid where the work sets the rhythm",
                   "horizontal gallery for the main items, vertical for the details",
                   "a playful single-screen hub that opens into each section"],
}
SUBJECT_HUES = [  # (hue degrees, saturation, words): a subject's natural color when there is no brand color
    (205, 0.65, "ocean sea water marine boat sail sailing surf beach cloud sky air flight airline swim pool ice"),
    (175, 0.55, "health clinic care medical dental pharmacy fresh clean hygiene spa therapy"),
    (140, 0.45, "nature plant plants garden green eco forest farm farming agriculture tree climate sustainability hiking camping"),
    (100, 0.45, "salad vegan organic tea matcha herb"),
    (34, 0.85, "sun solar energy honey bee summer lemon gold"),  # yellow cannot carry 3:1 on light backgrounds, so amber
    (28, 0.55, "coffee cafe bakery bread chocolate leather wood craft whisky barbecue"),
    (15, 0.75, "food restaurant pizza spice chili tomato cooking recipe kitchen"),
    (355, 0.7, "news sport sports fitness fire passion wine cinema film"),
    (335, 0.6, "beauty cosmetics fashion love dating flower wedding"),
    (228, 0.5, "night nightlife astronomy space galaxy dream sleep shift"),  # night is deep blue, not the generic purple
    (215, 0.55, "bank banking finance fintech insurance law legal government security trust payment payroll accounting invoice invoicing bookkeeping"),
]
STOPWORDS = set("a an and the for of to in on with app apps application website site web platform tool tools page our my your "
                "that this is are be by from it its as at or build make new project small simple modern best good home landing our "
                "we us page first time young people user users".split())


AUDIENCE = {"kid", "child", "children", "parent", "baby", "student", "teacher", "patient", "doctor", "nurse", "senior", "elderly",
            "developer", "engineer", "gamer", "traveller", "tourist", "freelancer", "lawyer", "investor", "trader", "volunteer"}  # who uses it


def stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"  # bakeries -> bakery
    return w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w


def word_list(text):
    return [stem(w) for w in re.findall(r"[a-z][a-z0-9]+", text.lower()) if w not in STOPWORDS]


def load_directions():
    try:
        return json.loads((REF / "directions.json").read_text(encoding="utf-8"))["directions"]
    except (OSError, ValueError, KeyError) as e:
        raise SystemExit(f"cannot read references/directions.json: {e}")


def project_signals(a):
    """Words that describe the project, and a stable identity for its seed."""
    parts, identity, sources = [" ".join(a.describe)], [" ".join(a.describe).strip().lower()], []
    if a.dir:
        root = Path(a.dir).resolve()
        identity.append(root.name.lower())
        try:
            remote = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=5)
            if remote.returncode == 0:
                identity.append(remote.stdout.strip().lower())
        except (OSError, subprocess.SubprocessError):
            pass
        for name in ("README.md", "README", "readme.md", "README.rst", "package.json", "pyproject.toml", "index.html", "app.json"):
            f = root / name
            if not f.is_file():
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                continue
            if name == "package.json":
                try:
                    pkg = json.loads(text if len(text) < 4000 else f.read_text(encoding="utf-8", errors="replace"))
                    text = " ".join(str(pkg.get(k, "")) for k in ("name", "description", "keywords"))
                except ValueError:
                    pass
            elif name == "index.html":
                found = re.findall(r"<title>(.*?)</title>", text, re.S | re.I)
                found += re.findall(r"<meta[^>]+name=[\"'](?:description|keywords)[\"'][^>]+content=[\"']([^\"']*)", text, re.I)
                text = " ".join(found)
            parts.append(re.sub(r"```.*?```|<[^>]+>|https?://\S+", " ", text, flags=re.S))
            sources.append(name)
    return " ".join(parts), "|".join(i for i in identity if i), sources


def score_directions(dirs, words):
    wanted = set(words)
    sets = [(set(word_list(d["fits"])), set(word_list(d["feel"]))) for d in dirs]
    df = {}  # in how many directions a word appears: rare words ("surf") say more than shared ones ("school")
    for fits, feel in sets:
        for w in fits | feel:
            df[w] = df.get(w, 0) + 1
    ranked = []
    for d, (fits, feel) in zip(dirs, sets):
        hit_fit, hit_feel = sorted(wanted & fits), sorted(wanted & feel)
        score = sum((3 if w in AUDIENCE else 2) / df[w] ** 0.5 for w in hit_fit) + sum(1 / df[w] ** 0.5 for w in hit_feel)
        ranked.append((round(score, 3), hit_fit + hit_feel, d))
    ranked.sort(key=lambda r: -r[0])
    return ranked


def hls_hex(h, light, s):
    return hexof(tuple(round(v * 255) for v in colorsys.hls_to_rgb((h / 360) % 1, max(0, min(1, light)), max(0, min(1, s)))))


def hls_of(hx):
    c = parse_color(hx)
    h, light, s = colorsys.rgb_to_hls(*(v / 255 for v in c[:3]))
    return h * 360, light, s


def chroma(hx):
    c = parse_color(hx)
    return (max(c[:3]) - min(c[:3])) / 255


def meets(fg, bgs, target):
    return all(ratio(parse_color(fg), parse_color(b)) >= target for b in bgs)


def tune(h, s, light, bgs, target, step):
    """Move lightness in `step` direction until the color reaches `target` against every background."""
    for _ in range(120):
        hx = hls_hex(h, light, s)
        if meets(hx, bgs, target):
            return hx
        light += step
        if not 0 <= light <= 1:
            break
    return hls_hex(h, 0.0 if step < 0 else 1.0, s)


def theme_palette(base, hue, tint, accent_sat, brand, dark, rng):
    pal = {}
    lean = rng.random() < 0.5  # one choice per theme, so bg, surface, and border stay one family
    roles = ("bg", "surface", "border")
    # one decision for the family: deliberately colored neutrals (or tinted ones, half the time) keep their character
    keep = any(chroma(base[r]) >= 0.12 for r in roles) or (chroma(base["bg"]) >= 0.02 and not lean)
    for role in roles:
        h0, l0, s0 = hls_of(base[role])
        c = chroma(base[role])  # HLS saturation overstates near-white colors; chroma is how colored it looks
        if keep:
            pal[role] = hls_hex(h0, l0, s0)
        else:  # lean toward this project's hue at the same lightness and about the same visible tint
            target = max(c, tint * 0.25)
            s = min(1.0, target / max(1e-6, 1 - abs(2 * l0 - 1)))
            pal[role] = hls_hex(hue, l0, s)
    bgs = [pal["bg"], pal["surface"]]
    for role, target in (("text", 7.0), ("muted", 4.6)):
        h0, l0, s0 = hls_of(base[role])
        pal[role] = tune(hue if s0 < 0.03 else h0, s0 if s0 >= 0.03 else min(tint * 1.5, 0.12), l0, bgs, target, 0.01 if dark else -0.01)
    h0, l0, s0 = hls_of(base["accent"])
    neutral_accent = s0 < 0.08 and not brand
    a_h, a_s = (h0, s0) if neutral_accent else (hue, accent_sat)
    a_l = l0 if not brand or dark else hls_of(brand)[1]
    best, best_move = None, 2.0
    for txt in ("#ffffff", pal["bg"] if dark else pal["text"]):  # light or dark text on the accent: whichever changes the hue least
        for step in range(201):
            light = step / 200
            acc = hls_hex(a_h, light, a_s)
            if abs(light - a_l) < best_move and meets(acc, [pal["bg"]], 3.0) and meets(txt, [acc], 4.5):
                best, best_move = (acc, txt), abs(light - a_l)
    if brand and not dark and meets(brand, [pal["bg"]], 3.0):
        for txt in ("#ffffff", pal["text"]):
            if meets(txt, [brand], 4.5):
                best = (brand, txt)
                break
    pal["accent"], pal["accent_text"] = best or (pal["text"], pal["bg"])
    dh, dl, ds = hls_of(base["danger"])
    pal["danger"] = tune(dh, ds, dl, bgs, 4.5, 0.01 if dark else -0.01)
    return pal


def generate(d, seed, words, brand, hue_sat=None):
    rng = random.Random(seed)
    j1, j2 = rng.uniform(-1, 1), rng.uniform(0, 1)  # always drawn, so a design code replays the same sequence
    if hue_sat:
        hue, accent_sat = hue_sat
        hue_source = "the design code"
    elif brand:
        hue, accent_sat = hls_of(brand)[0], max(0.35, hls_of(brand)[2])
        hue_source = f"brand color {brand}"
    else:
        found = [(sum(w in set(word_list(ws)) for w in words), h, s, ws) for h, s, ws in SUBJECT_HUES]
        found.sort(key=lambda f: -f[0])
        if found[0][0]:
            hue, accent_sat = found[0][1] + 14 * j1, found[0][2] * (0.85 + 0.25 * j2)
            hue_source = "the subject (" + ", ".join(w for w in words if w in set(word_list(found[0][3])))[:40] + ")"
        else:
            h0, _, s0 = hls_of(d["light"]["accent"])
            hue, accent_sat = h0 + 30 * j1, max(0.4, s0) * (0.85 + 0.2 * j2)
            hue_source = "the direction, shifted for this project"
        if 250 <= hue % 360 <= 290 and not any(w in words for w in ("purple", "violet", "lavender", "lilac")):
            hue = 232 if hue % 360 < 270 else 322  # step out of the generic purple to the nearest blue or rose
        if 45 <= hue % 360 <= 80:  # muddy olive when darkened for contrast: use amber instead
            hue = 34
    hue, accent_sat = round(hue) % 360, round(min(accent_sat, 0.99), 2)
    tint = rng.choice([0.0, 0.02, 0.04, 0.06])
    light = theme_palette(d["light"], hue, tint, min(accent_sat, 0.95), brand, False, rng)
    dark = theme_palette(d["dark"], hue, tint, min(accent_sat * 0.9, 0.9), brand, True, rng)
    voices = d.get("voices", {"display": "grotesk", "body": "humanist"})
    display = rng.choice(FONT_POOLS[voices["display"]] + [d["fonts"]["display"]])
    body = display if voices["display"] == voices["body"] and rng.random() < 0.5 else rng.choice(
        [f for f in FONT_POOLS[voices["body"]] + [d["fonts"]["body"]] if f != display] or [display])
    mono = rng.choice(FONT_POOLS["mono"])
    ratios = [1.125, 1.2, 1.25, 1.333, 1.414, 1.5, 1.618]
    i = min(range(len(ratios)), key=lambda k: abs(ratios[k] - d["type_ratio"]))
    ratio_ = ratios[max(0, min(len(ratios) - 1, i + rng.choice([-1, 0, 0, 1])))]
    if d["mode"] == "Operate":
        ratio_ = min(ratio_, 1.25)
    r = int(re.sub(r"\D", "", d["radius"]) or 0)
    radius = rng.choice([0, 0, 2]) if r == 0 else rng.choice([max(2, round(r * 0.75 / 2) * 2), r, round(r * 1.25 / 2) * 2])
    return {"light": light, "dark": dark, "display": display, "body": body, "mono": mono, "ratio": ratio_, "radius": radius,
            "layout": rng.choice(LAYOUTS[d["mode"]]), "hue_source": hue_source, "hue": hue, "sat": accent_sat}


def font_stack(name, voice):
    fallback = "Georgia, serif" if voice in SERIF_VOICES else ("ui-monospace, monospace" if voice == "mono" else "system-ui, sans-serif")
    return f"\"{name}\", {fallback}"


def design_css(d, g, code):
    space = {"dense": [0, 2, 4, 8, 12, 16, 20, 24, 32, 48], "standard": [0, 4, 8, 12, 16, 24, 32, 48, 64, 96],
             "spacious": [0, 4, 8, 16, 24, 32, 48, 64, 96, 128]}[d["density"]]
    dur = {"Operate": (120, 180, 240), "Read": (120, 200, 300), "Persuade": (150, 250, 400), "Experience": (200, 350, 600)}[d["mode"]]
    v = d.get("voices", {})
    fonts = sorted({g["display"], g["body"], g["mono"]})
    out = [f"/* {d['name']} direction, design code {code}. Generated by design.py direction; every color pair passes WCAG AA. */",
           f"/* Fonts (Google Fonts): {', '.join(fonts)}. Load only the weights you use, with font-display: swap. */",
           ":root {",
           f"  --font-display: {font_stack(g['display'], v.get('display'))};",
           f"  --font-body: {font_stack(g['body'], v.get('body'))};",
           f"  --font-mono: {font_stack(g['mono'], 'mono')};"]
    out += [f"  --color-{k.replace('_', '-')}: {val};" for k, val in g["light"].items()]
    for i, n in enumerate(["xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl"]):
        out.append(f"  --text-{n}: {16 * g['ratio'] ** (i - 2) / 16:.3f}rem;")
    out += [f"  --space-{i}: {px / 16:g}rem;" for i, px in enumerate(space)]
    rr = g["radius"]
    out += [f"  --radius-sm: {max(0, rr // 2)}px; --radius-md: {rr}px; --radius-lg: {rr * 2 if rr else 0}px; --radius-full: 9999px;",
            f"  --duration-fast: {dur[0]}ms; --duration-base: {dur[1]}ms; --duration-slow: {dur[2]}ms;",
            "  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);", "  --measure: 65ch;", "  color-scheme: light;", "}"]
    dark = [f"  --color-{k.replace('_', '-')}: {val};" for k, val in g["dark"].items()] + ["  color-scheme: dark;"]
    out += ["@media (prefers-color-scheme: dark) {", "  :root:not([data-theme=\"light\"]) {"] + ["  " + x for x in dark] + ["  }", "}"]
    out += ["[data-theme=\"dark\"] {"] + dark + ["}"]
    out += ["@media (prefers-reduced-motion: reduce) {", "  :root { --duration-fast: 0ms; --duration-base: 0ms; --duration-slow: 0ms; }", "}"]
    return "\n".join(out)


def run_direction(a):
    dirs = load_directions()
    if a.list:
        for d in dirs:
            print(f"{d['id']:22} {d['mode']:10} {d['feel']}")
        return 0
    brand = None
    if a.brand:
        c = parse_color(a.brand)
        if not c:
            print("could not parse --brand; use #hex, rgb(), or hsl()")
            return 2
        brand = hexof(c)
    text, identity, sources = project_signals(a)
    words = word_list(text)
    by_id = {d["id"]: d for d in dirs}
    if a.pick and a.pick not in by_id:
        print(f"unknown direction '{a.pick}'; run design.py direction --list")
        return 2
    ranked = score_directions(dirs, words)
    if not a.pick and not a.seed and ranked[0][0] == 0:
        print("Not enough to go on. Describe the product, its audience, and the feeling, for example:\n"
              "  design.py direction \"invoicing app for freelancers, calm and trustworthy\"\n"
              "or run it with --dir . in a project that has a README or package.json description.")
        return 2
    chosen = by_id[a.pick] if a.pick else ranked[0][2]
    hue_sat = None
    if a.seed:
        m = re.fullmatch(r"(?:([a-z-]+):)?([0-9a-f]{8})(?:h(\d{1,3})s(\d{1,2}))?", a.seed.strip().lower())
        if not m or (m.group(1) and m.group(1) not in by_id):
            print("--seed takes a design code such as travel-stay:a2d32562h205s55 (or its part after the colon)")
            return 2
        if m.group(1):
            chosen = by_id[m.group(1)]
        seed = int(m.group(2), 16)
        if m.group(3):
            hue_sat = (int(m.group(3)) % 360, int(m.group(4)) / 100)
    else:
        seed = int(hashlib.sha256((identity or " ".join(sorted(set(words)))).encode("utf-8")).hexdigest()[:8], 16)
    g = generate(chosen, seed, words, brand, hue_sat)
    code = f"{chosen['id']}:{seed:08x}h{g['hue']:03d}s{round(g['sat'] * 100):02d}"
    if a.css:
        print(design_css(chosen, g, code))
        return 0
    out = []
    if a.dir:
        light_vars, _, _ = css_vars(collect([Path(a.dir).resolve()], Path(a.dir).resolve()))
        colors = [n for n, v in light_vars.items() if first_color(resolve(v, light_vars), {})[0]]
        if len(colors) >= 6:
            out.append(f"NOTE: this project already has {len(colors)} color tokens. Extend that system; use this only for gaps "
                       "(run design.py tokens).")
    if sources:
        out.append(f"read: {', '.join(sources)}")
    top = [r for r in ranked if r[0] > 0][:3]
    if top:
        out.append("fit: " + "; ".join(f"{r[2]['id']} ({', '.join(r[1][:4])})" for r in top))
    L, D = g["light"], g["dark"]
    out += [f"design for this project: {chosen['name']}  [code {code}]",
            f"  mode {chosen['mode']}, {chosen['density']} spacing, radius {g['radius']}px, type ratio {g['ratio']}",
            f"  layout: {g['layout']}",
            f"  fonts: {g['display']} (display), {g['body']} (body), {g['mono']} (mono)",
            f"  accent hue from {g['hue_source']}",
            f"  light: bg {L['bg']} surface {L['surface']} text {L['text']} muted {L['muted']} accent {L['accent']} on {L['accent_text']}",
            f"  dark:  bg {D['bg']} surface {D['surface']} text {D['text']} muted {D['muted']} accent {D['accent']} on {D['accent_text']}",
            f"  imagery: {chosen['imagery']}; motion: {chosen['motion']}",
            f"  signature: {chosen['signature']}. Make it this project's own: use one detail from its subject.",
            f"  avoid: {chosen['avoid']}",
            f"  study: {chosen['study']}",
            f"next: design.py direction ... --css > tokens file; save it: memory.py add decision \"Design: {code}, {g['display']}/{g['body']}\""]
    text_out = "\n".join(out)
    print(text_out if len(text_out) <= a.max_chars else text_out[:a.max_chars].rsplit("\n", 1)[0] + "\n[truncated]")
    return 0


NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "fifty": 50, "dozens": 30,
                "hundred": 100, "hundreds": 300, "thousand": 1000, "thousands": 3000}


def run_choose(a):
    """Recommend the component for a need: which one, why, when the alternative wins, what to avoid."""
    try:
        rules = json.loads((REF / "components.json").read_text(encoding="utf-8"))["rules"]
    except (OSError, ValueError, KeyError) as e:
        raise SystemExit(f"cannot read references/components.json: {e}")
    text = " ".join(a.need)
    if not text.strip():
        print("Describe what the user must do, for example:\n  design.py choose \"pick one of 4 shipping speeds\"\n"
              "  design.py choose \"confirm deleting a project\"\nneeds: " + "; ".join(r["need"] for r in rules))
        return 2
    words = set(word_list(text))
    sets = [set(word_list(r["words"] + " " + r["need"])) for r in rules]
    df = {}
    for s in sets:
        for w in s:
            df[w] = df.get(w, 0) + 1
    scored = sorted(((sum(1 / df[w] ** 0.5 for w in words & s), r) for r, s in zip(rules, sets)), key=lambda x: -x[0])
    if scored[0][0] == 0:
        print("no matching decision; needs covered: " + "; ".join(r["need"] for r in rules))
        return 2
    nums = [int(n) for n in re.findall(r"\b(\d{1,6})\b", text)]
    nums += [v for k, v in NUMBER_WORDS.items() if re.search(rf"\b{k}\b", text.lower())]
    n = a.n if a.n is not None else (max(nums) if nums else None)
    out = []
    for score, r in scored[:2]:
        if out and score < scored[0][0] * 0.75:
            break  # show a second decision only when it is nearly as relevant
        out.append(f"{r['need']} [{r['id']}]")
        if "bands" in r and n is not None:
            band = next(b for b in r["bands"] if n <= b["max"])
            out.append(f"  use: {band['use']}  (n={n})\n  why: {band['why']}")
        elif "bands" in r:
            lo = 1
            for b in r["bands"]:
                rng_txt = f"{lo}+" if b["max"] >= 100000 else (f"{lo}-{b['max']}" if lo < b["max"] else f"{b['max']}")
                out.append(f"  {rng_txt}: {b['use']}")
                lo = b["max"] + 1
            out.append("  (add the count, e.g. --n 12, for one answer)")
        else:
            out.append(f"  use: {r['use']}\n  why: {r['why']}")
        out.append(f"  instead: {r['instead']}\n  avoid: {r['avoid']}")
    text_out = "\n".join(out)
    print(text_out if len(text_out) <= a.max_chars else text_out[:a.max_chars].rsplit("\n", 1)[0] + "\n[truncated]")
    return 0


def run_pattern(a):
    try:
        text = (REF / "patterns.md").read_text(encoding="utf-8")
    except OSError:
        print("references/patterns.md is missing")
        return 2
    sections = re.split(r"(?m)^## ", text)[1:]
    index = []
    for s in sections:
        title = s.split("\n", 1)[0].strip()
        also = re.search(r"(?m)^Also:\s*(.+)$", s)
        index.append((title, set(word_list(title + " " + (also.group(1) if also else ""))), s))
    if not a.feature:
        print("patterns: " + ", ".join(t for t, _, _ in index))
        return 0
    want = set(word_list(" ".join(a.feature)))
    best = max(index, key=lambda x: len(want & x[1]))
    if not want & best[1]:
        print("no pattern for that; available: " + ", ".join(t for t, _, _ in index))
        return 2
    body = "## " + best[2].strip()
    print(body if len(body) <= a.max_chars else body[:a.max_chars].rsplit("\n", 1)[0] + "\n[truncated]")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    au = sub.add_parser("audit", help="check UI code for accessibility and consistency problems")
    au.add_argument("paths", nargs="*")
    au.add_argument("--dir", default=".")
    au.add_argument("--changed", action="store_true", help="only files changed since HEAD (plus untracked)")
    au.add_argument("--strict", action="store_true", help="exit 1 if any error")
    au.add_argument("--per-rule", type=int, default=3)
    au.add_argument("--max-chars", type=int, default=1600)
    tk = sub.add_parser("tokens", help="list the design tokens the project already has")
    tk.add_argument("path", nargs="?", default=".")
    tk.add_argument("--dir", default=".")
    tk.add_argument("--per-group", type=int, default=8)
    tk.add_argument("--max-chars", type=int, default=1600)
    ct = sub.add_parser("contrast", help="WCAG contrast of two colors")
    ct.add_argument("fg")
    ct.add_argument("bg")
    ct.add_argument("--large", action="store_true", help="large text (24px, or 18.66px bold): 3:1 target")
    sc = sub.add_parser("scale", help="print starter type/spacing/radius tokens")
    sc.add_argument("--base", type=float, default=16)
    sc.add_argument("--ratio", type=float, default=1.25)
    dr = sub.add_parser("direction", help="design direction generated for this project (fit + unique per project)")
    dr.add_argument("describe", nargs="*", help="what the product is, who uses it, the feeling")
    dr.add_argument("--dir", help="also read this project's README, package.json, index.html, and git remote")
    dr.add_argument("--brand", help="brand color to build around (#hex)")
    dr.add_argument("--pick", help="use this direction id instead of the best fit")
    dr.add_argument("--seed", help="hex part of a design code, to reproduce a design exactly")
    dr.add_argument("--css", action="store_true", help="print the design as CSS variables (light, dark, type, space, motion)")
    dr.add_argument("--list", action="store_true", help="list the directions")
    dr.add_argument("--max-chars", type=int, default=1800)
    ch = sub.add_parser("choose", help="which component fits a need (radio or select, modal or page, table or cards, ...)")
    ch.add_argument("need", nargs="*", help="what the user must do, e.g. 'pick one of 4 shipping speeds'")
    ch.add_argument("--n", type=int, help="number of options or items, if not in the text")
    ch.add_argument("--max-chars", type=int, default=1800)
    pt = sub.add_parser("pattern", help="checklist for a feature (table, checkout, search, ...)")
    pt.add_argument("feature", nargs="*")
    pt.add_argument("--max-chars", type=int, default=2200)
    a = p.parse_args()
    if getattr(a, "max_chars", 1) < 200:
        a.max_chars = 200
    if getattr(a, "per_rule", 1) < 1:
        a.per_rule = 1
    if getattr(a, "per_group", 1) < 1:
        a.per_group = 1
    if a.cmd == "scale" and not (8 <= a.base <= 32 and 1.0 < a.ratio <= 2.0):
        p.error("--base must be 8-32 and --ratio between 1 and 2")
    return {"audit": run_audit, "tokens": run_tokens, "contrast": run_contrast, "scale": run_scale,
            "direction": run_direction, "pattern": run_pattern, "choose": run_choose}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
