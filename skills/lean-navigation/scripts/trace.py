#!/usr/bin/env python3
"""Trace a pasted browser or server error to source. Usage: trace.py [TEXT] [--dir PROJECT] [--max-chars 1600]

Reads TEXT (or stdin): a console error, stack trace, failed request line, or URL. Extracts stack
frames, route paths, identifiers, and the fixed part of the message, then searches the project
once and prints ranked path:line hits per clue within a character budget."""
import argparse
import importlib.util
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.dont_write_bytecode = True  # never leave __pycache__ inside the skill folder
_spec = importlib.util.spec_from_file_location("lean_find", Path(__file__).with_name("find.py"))
_find = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_find)

SRC_EXT = r"(?:jsx?|tsx?|mjs|cjs|vue|svelte|py|rb|go|php|java|kt|cs|rs|swift)"
# Bounded repeats keep matching linear on long pasted lines (unbounded versions were quadratic).
FRAME = re.compile(r"((?:[A-Za-z][\w+.-]{0,20}://[^\s()'\"]{0,300}?/)?[\w@~.\-/\\]{1,300}\." + SRC_EXT
                   + r")(?:\?[^\s:()'\"]{0,200})?:(\d+)(?::\d+)?")
MAX_LINE, MAX_LINES = 2000, 400  # pasted errors beyond this are noise
PY_FRAME = re.compile(r'File "([^"]+)", line (\d+)')
URL = re.compile(r"(?:https?://[^\s'\"()<>]+|(?<![\w.])/(?:api|v\d+|graphql|rest|auth)[^\s'\"()<>]*)")
IDENT_PATTERNS = [
    r"reading '([A-Za-z_$][\w$]*)'", r"properties of \w+ \(reading '([A-Za-z_$][\w$]*)'\)",
    r"([A-Za-z_$][\w$.]*) is not a function", r"([A-Za-z_$][\w$]*) is not defined",
    r"Cannot find module '([^']+)'", r"has no attribute '(\w+)'", r"name ['\"](\w+)['\"] is not defined",
    r"undefined method [`'](\w+)'", r"Unknown (?:column|field) '(\w+)'", r"Can't resolve '([^']+)'",
]
VENDOR = ("node_modules", "/.vite/", "chunk-", "vendor", "webpack/runtime", "<anonymous>", "site-packages", "dist-packages")
VARIABLE_SEG = re.compile(r"^(?:\d+|[0-9a-fA-F-]{16,}|[0-9a-fA-F]{8}-[0-9a-fA-F-]+|[A-Za-z0-9_-]{20,})$")
ROUTE_PARAM = r"(?::\w+|\[[^\]/]+\]|\{[^}/]+\}|<[^>/]+>|\$\{[^}]+\}|[^/'\"`\s]+)"


def clean_path(raw):
    raw = raw.replace("\\", "/")
    if "://" in raw:
        raw = raw.split("://", 1)[1]
        raw = raw.split("/", 1)[1] if "/" in raw else raw
    return raw.lstrip("./~")


def extract(text):
    text = "\n".join(line[:MAX_LINE] for line in text.splitlines()[:MAX_LINES])
    clues, seen = [], set()

    def add(kind, value, pattern, line=None):
        key = (kind, value)
        if value and key not in seen:
            seen.add(key)
            clues.append({"kind": kind, "value": value, "rx": pattern, "line": line, "hits": []})

    for rx in (PY_FRAME, FRAME):
        for m in rx.finditer(text):
            path = clean_path(m.group(1))
            if any(v in "/" + path for v in VENDOR):
                continue
            add("frame", f"{path}:{m.group(2)}", None, int(m.group(2)))
    for m in URL.finditer(text):
        path = urlsplit(m.group(0)).path if "://" in m.group(0) else m.group(0).split("?")[0]
        path = re.sub(r"(?::\d+){1,2}$", "", path)
        if any(v in path for v in VENDOR):
            continue
        segs = [s for s in path.strip("/").split("/") if s]
        if not segs or re.search(r"\." + SRC_EXT + r"$", segs[-1]) or segs[-1].endswith((".map", ".css", ".png", ".svg", ".ico")):
            continue
        parts = [ROUTE_PARAM if VARIABLE_SEG.match(s) else re.escape(s) for s in segs]
        literal = [s for s in segs if not VARIABLE_SEG.match(s)]
        if literal:
            add("route", "/" + "/".join(segs), re.compile(r"/" + r"/".join(parts) + r"(?![\w-])"))
    for pat in IDENT_PATTERNS:
        for m in re.finditer(pat, text):
            name = m.group(1).split(".")[-1]
            if len(name) > 1:
                add("identifier", name, re.compile(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])"))
    messages = 0
    for line in text.splitlines():
        if messages >= 2 or any(re.search(pat, line) for pat in IDENT_PATTERNS):
            continue
        msg = re.sub(r"^\s*(?:Uncaught\s+)?(?:\(in promise\)\s+)?(?:\w*(?:Error|Exception)\b:?\s*)", "", line).strip()
        if not msg or FRAME.search(line) or PY_FRAME.search(line) or line.lstrip().startswith("at "):
            continue
        chunks = re.split(r"'[^']*'|\"[^\"]*\"|`[^`]*`|\b\d[\w.:-]*|https?://\S+|\([^)]*\)", msg)
        best = max((c.strip(" .:,;-") for c in chunks), key=len, default="")
        if len(best) >= 12:
            add("message", best, re.compile(re.escape(best), re.I))
            messages += 1
    return clues


def is_test(rel):
    s = rel.as_posix().lower()
    return "/test" in "/" + s or ".test." in s or ".spec." in s or "__tests__" in s


for _stream in (sys.stdout, sys.stderr):  # never crash on non-ASCII output (Windows consoles default to cp1252)
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("text", nargs="?", help="error text; reads stdin when omitted")
    p.add_argument("--dir", default=".", help="project directory to search")
    p.add_argument("--max-chars", type=int, default=1600)
    p.add_argument("--per-clue", type=int, default=3)
    p.add_argument("--max-files", type=int, default=4000)
    p.add_argument("--changed", action="store_true", help="search only files with uncommitted Git changes")
    a = p.parse_args()
    text = a.text if a.text is not None else sys.stdin.read()
    base = Path(a.dir).resolve()
    if not base.is_dir():
        p.error(f"expected an existing directory: {base}")
    clues = extract(text)
    if not clues:
        print("No usable clues (stack frame, route, identifier, or message of 12+ characters). Paste the exact first error line.")
        return
    files = []
    try:
        source = list(_find.changed_files(base)) if a.changed else _find.files_under(base)
    except (OSError, _find.subprocess.SubprocessError) as exc:
        p.error(f"--changed needs a Git work tree ({type(exc).__name__}); run without --changed")
    for path in source:
        if len(files) >= a.max_files:
            break
        if path.is_file() and not path.is_symlink() and not str(path).lower().endswith(_find.SKIP_EXT):
            files.append(path)
    rels = {f: f.relative_to(base) for f in files}
    for c in clues:
        if c["kind"] == "frame":
            want = c["value"].rsplit(":", 1)[0].lower()
            best = None
            for f, rel in rels.items():
                r = rel.as_posix().lower()
                if r == want or r.endswith("/" + want) or want.endswith("/" + r):
                    if best is None or len(r) > len(best[1].as_posix()):
                        best = (f, rel)
            if best:
                try:
                    lines = best[0].read_text(encoding="utf-8").splitlines()
                    excerpt = lines[c["line"] - 1].strip()[:160] if 0 < c["line"] <= len(lines) else "(line beyond file end: build output may differ from source)"
                except (OSError, UnicodeDecodeError):
                    excerpt = "(unreadable)"
                c["hits"].append((False, best[1], c["line"], excerpt))
    searchable = [c for c in clues if c["rx"] is not None]
    scanned = unreadable = 0
    if searchable:
        for f, rel in rels.items():
            try:
                if f.stat().st_size > 1_000_000:
                    continue
                lines = f.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                unreadable += 1
                continue
            scanned += 1
            for i, line in enumerate(lines):
                for c in searchable:
                    if c["rx"].search(line):
                        c["hits"].append((is_test(rel), rel, i + 1, line.strip()[:160]))
    out = [f"{len(clues)} clues; {len(files)} files listed, {scanned} scanned" + (f", {unreadable} unreadable" if unreadable else "") + ("; local changes only" if a.changed else "") + "."]
    misses = []
    for c in clues:
        hits = sorted(c["hits"], key=lambda h: (h[0], str(h[1]).casefold(), h[2]))
        if not hits:
            misses.append(f"{c['kind']} {c['value']}")
            continue
        block = [f"\n{c['kind']}: {c['value']}" + (f" ({len(hits)} hits)" if len(hits) > a.per_clue else "")]
        block += [f"  {rel.as_posix()}:{ln}: {ex}" for _, rel, ln, ex in hits[: a.per_clue]]
        if sum(map(len, out + block)) + len(out) + len(block) > a.max_chars:
            out.append("\n[truncated: raise --max-chars or paste fewer lines]")
            break
        out.extend(block)
    if misses:
        out.append("\nNo match: " + "; ".join(misses) + ". Absence is not proof; check build aliases or generated code.")
    hit_files = {h[1].as_posix() for c in clues for h in c["hits"][: a.per_clue] if not h[0]}
    near = set()
    if hit_files and _find.memory_store(base):
        try:  # one import hop via the code graph, only when there are memories to look up
            gspec = importlib.util.spec_from_file_location("lean_graph", Path(__file__).with_name("graph.py"))
            gmod = importlib.util.module_from_spec(gspec)
            gspec.loader.exec_module(gmod)
            gfiles = gmod.build(base)["files"]
            for rel, info in gfiles.items():
                if rel in hit_files:
                    near |= set(info.get("imports", []))
                elif hit_files & set(info.get("imports", [])):
                    near.add(rel)
        except Exception:  # memory is a bonus; never fail the trace over it
            near = set()
    notes = _find.memory_notes(base, hit_files, near=near)
    if notes:
        out.append("\n" + _find.MEMORY_HEADER[0].upper() + _find.MEMORY_HEADER[1:])
        out.extend(notes)
    rendered = "\n".join(out)
    print(rendered if len(rendered) <= a.max_chars else rendered[: a.max_chars - 11] + "[truncated]")


if __name__ == "__main__":
    main()
