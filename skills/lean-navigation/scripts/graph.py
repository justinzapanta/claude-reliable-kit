#!/usr/bin/env python3
"""Lightweight code graph: folders, files, symbols, imports, calls, routes, tests. Stdlib only, bounded output.

Commands (all take --dir PROJECT, default "."):
  tree [SUBDIR] [--depth 2]   folder nodes: files, languages, key symbols, folder-to-folder imports
  node TARGET                 a file (path) or symbol (name): definitions, imports, importers, callers, tests, routes
  brief TARGET                node + project memory + the last commits that touched it: one call before editing
  impact [FILES...] [--base REF]
                              what a change can break: changed symbols, callers, importers (2 levels), tests, routes
  routes [PATTERN]            HTTP route table (Express/Koa/Flask/FastAPI-style and file-based pages/app routes)
  build                       (re)build the cache; other commands update it incrementally on their own

The graph is cached in .git/lean-graph.json inside a Git work tree (never committed), else .lean-graph.json.
"""
import argparse
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True  # never leave __pycache__ inside the skill folder
_spec = importlib.util.spec_from_file_location("lean_find", Path(__file__).with_name("find.py"))
_find = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_find)

VERSION = 4  # bump whenever parsing rules change so old caches are rebuilt
CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".cs"}
JS_EXT = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"]
JS_DEF = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\*?\s+([A-Za-z_$][\w$]*)|class\s+([A-Za-z_$][\w$]*)"
                    r"|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>))")
JS_METHOD = re.compile(r"^\s{2,}(?:async\s+|static\s+|public\s+|private\s+|protected\s+)*([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*[:{]")
OTHER_DEF = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:public\s+|private\s+|protected\s+|static\s+|abstract\s+)*"
                       r"(?:func(?:\s*\([^)]*\))?|fn|def|class|struct|interface|enum|trait)\s+([A-Za-z_]\w*)")
JS_IMPORT = re.compile(r"""(?:import\s[^'"`;]*?from\s*|import\s*\(\s*|require\s*\(\s*|export\s[^'"`;]*?from\s*|import\s+)['"`]([^'"`]+)['"`]""")
CALL = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(|\.([A-Za-z_$][\w$]*)\s*\(")
ROUTE = re.compile(r"""\.(get|post|put|patch|delete|options|head|all|route|use)\s*\(\s*['"`](/[^'"`]*)['"`]""", re.I)
PY_ROUTE = re.compile(r"""@\w+(?:\.\w+)*\.(get|post|put|patch|delete|route|api_route|websocket)\s*\(\s*['"](/[^'"]*)['"]""", re.I)
KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "function", "typeof", "new", "await", "super", "import",
            "require", "print", "len", "str", "int", "dict", "list", "set", "isinstance", "range", "elif", "and", "or",
            "not", "with", "assert", "sizeof", "func", "fn", "def", "class", "defer", "go", "match", "when", "else"}
MAX_CALL_LINES = 4
COMMON_NAMES = {"update", "get", "set", "add", "remove", "delete", "run", "call", "main", "handle", "handler", "close", "open",
                "read", "write", "save", "load", "start", "stop", "send", "create", "init", "setup", "process", "execute",
                "render", "apply", "build", "parse", "format", "validate", "next", "copy", "clear", "reset", "test", "wrapper",
                "wrapped", "decorator", "inner", "callback", "fn", "func", "default", "index", "app", "view"}


def cache_path(base):
    try:
        r = subprocess.run(["git", "-C", str(base), "rev-parse", "--absolute-git-dir"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip()) / "lean-graph.json"
    except (OSError, subprocess.SubprocessError):
        pass
    return base / ".lean-graph.json"


def lang_of(path):
    ext = path.suffix.lower()
    return "py" if ext == ".py" else "js" if ext in JS_EXT else ext.lstrip(".")


def add_call(calls, name, line):
    if name in KEYWORDS or len(name) < 2:
        return
    lines = calls.setdefault(name, [])
    if len(lines) < MAX_CALL_LINES and line not in lines:
        lines.append(line)


def parse_python(text):
    defs, imports, calls, routes = [], [], {}, []
    tree = ast.parse(text)

    def visit(node, prefix=""):
        for item in ast.iter_child_nodes(node):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(item, ast.ClassDef) else "def"
                defs.append([prefix + item.name, item.lineno, getattr(item, "end_lineno", item.lineno), kind])
                for dec in getattr(item, "decorator_list", []):
                    seg = ast.get_source_segment(text, dec) or ""
                    m = PY_ROUTE.search("@" + seg)
                    if m:
                        routes.append([m.group(1).upper(), m.group(2), dec.lineno])
                visit(item, prefix + item.name + "." if kind == "class" else prefix)
    visit(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports += [("abs", a.name, 0) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            kind = "rel" if node.level else "abs"
            if mod:
                imports.append((kind, mod, node.level))
            # "from pkg import name" may import a submodule; keep it only if such a file exists
            imports += [(kind + "?", (mod + "." if mod else "") + a.name, node.level) for a in node.names if a.name != "*"]
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if name:
                add_call(calls, name, node.lineno)
    return defs, imports, calls, routes


def parse_regex(text, lang):
    defs, imports, calls, routes = [], [], {}, []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith(("//", "#", "*", "/*")):
            continue
        m = JS_DEF.match(line) if lang == "js" else OTHER_DEF.match(line)
        if m:
            defs.append([next(g for g in m.groups() if g), i, i, "def"])
        elif lang == "js":
            mm = JS_METHOD.match(line)
            if mm and mm.group(1) not in KEYWORDS:
                defs.append([mm.group(1), i, i, "method"])
        for r in ROUTE.finditer(line):
            routes.append([r.group(1).upper(), r.group(2), i])
        for c in CALL.finditer(line):
            name = c.group(1) or c.group(2)
            if not (m and i == (defs[-1][1] if defs else 0) and name == defs[-1][0]):
                add_call(calls, name, i)
    if lang == "js":  # scan the whole text so import statements spread over several lines are found
        imports = [("js", im.group(1), 0) for im in JS_IMPORT.finditer(text)]
    for idx in range(len(defs)):
        nxt = next((d[1] for d in defs[idx + 1:] if d[3] != "method" or defs[idx][3] == "method"), len(lines) + 1)
        defs[idx][2] = max(defs[idx][1], nxt - 1)
    return defs, imports, calls, routes


def file_routes(rel):
    """File-based routing only where the framework convention is unambiguous:
    Next.js pages/ (any file) and app/ (page.* or route.*), SvelteKit src/routes/+page|+server, Remix app/routes/x.$id.tsx."""
    parts = list(PurePosixPath(rel).parts)
    stem = PurePosixPath(rel).stem
    ext = PurePosixPath(rel).suffix.lower()

    def build_path(segs, dots=False):
        if dots:
            segs = [s for seg in segs for s in seg.split(".")]
        segs = [s for s in segs if s and s not in ("index", "_index") and not (s.startswith("(") and s.endswith(")"))]
        return "/" + "/".join(segs)

    if "routes" in parts[:-1]:
        i = parts.index("routes")
        if stem.startswith("+") and i > 0 and parts[i - 1] == "src":              # SvelteKit
            return build_path(parts[i + 1:-1])
        if i > 0 and parts[i - 1] == "app" and ext in (".tsx", ".jsx", ".ts", ".js"):  # Remix
            return build_path(parts[i + 1:-1] + [stem], dots=True)
        return None
    if "pages" in parts[:-1] and ext in JS_EXT and not stem.startswith("_"):      # Next.js pages router
        i = parts.index("pages")
        return build_path(parts[i + 1:-1] + [stem])
    if "app" in parts[:-1] and stem in ("page", "route") and ext in JS_EXT:       # Next.js app router
        i = parts.index("app")
        return build_path(parts[i + 1:-1])
    return None


def resolve_imports(graph):
    files = graph["files"]
    by_noext = defaultdict(list)
    for rel in files:
        noext = str(PurePosixPath(rel).with_suffix(""))
        by_noext[noext].append(rel)
        if noext.endswith("/index") or noext.endswith("/__init__"):
            by_noext[noext.rsplit("/", 1)[0]].append(rel)

    dirs = {part for rel in files for part in PurePosixPath(rel).parts[:-1]}
    by_last = defaultdict(list)  # last path segment -> extensionless keys, so suffix lookups avoid a full scan
    for key in by_noext:
        by_last[key.rsplit("/", 1)[-1]].append(key)

    def lookup(candidate):
        candidate = str(PurePosixPath(candidate))
        if candidate in files:  # import written with its extension: "./d.js", "./View.vue"
            return [candidate]
        return by_noext.get(candidate, [])

    unresolved = Counter()
    for rel, info in files.items():
        out = set()
        here = PurePosixPath(rel).parent
        for kind, spec, level in info.pop("raw_imports", []):
            optional = kind.endswith("?")
            kind = kind.rstrip("?")
            hits = []
            if kind == "js":
                if spec.startswith("."):
                    hits = lookup(os.path.normpath(str(here / spec)).replace("\\", "/"))
                elif spec.startswith(("@/", "~/")):
                    hits = lookup("src/" + spec[2:]) or lookup(spec[2:])
                else:
                    continue  # package import
            elif kind == "rel":
                pkg = here
                for _ in range(level - 1):
                    pkg = pkg.parent
                hits = lookup(str(pkg / spec.replace(".", "/"))) if spec else []
            else:
                path = spec.replace(".", "/")
                hits = lookup(path)
                if not hits and spec.split(".")[0] in dirs:  # src-layout packages; never stdlib names like json
                    suffix = "/" + path
                    hits = [f for k in by_last.get(path.rsplit("/", 1)[-1], []) if k.endswith(suffix) for f in by_noext[k]][:1]
                if not hits and not optional and spec.split(".")[0] in {n.split("/")[0] for n in by_noext}:
                    unresolved[spec] += 1
            out.update(h for h in hits if h != rel)
        info["imports"] = sorted(out)
    graph["unresolved"] = dict(unresolved.most_common(20))


def build(base, refresh=False, changed_only=None):
    cpath = cache_path(base)
    old = {}
    if cpath.exists() and not refresh:
        try:
            data = json.loads(cpath.read_text(encoding="utf-8"))
            if data.get("version") == VERSION and data.get("root") == str(base):
                old = data.get("files", {})
        except (OSError, ValueError):
            old = {}
    files, reparsed, errors = {}, 0, 0
    for path in _find.files_under(base):
        if path.suffix.lower() not in CODE_EXT or path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        st = path.stat()
        if st.st_size > 1_000_000:
            continue
        sig = [st.st_mtime_ns, st.st_size]
        prev = old.get(rel)
        if prev and prev.get("sig") == sig:
            info = dict(prev)
            info["raw_imports"] = [tuple(x) for x in prev.get("raw", [])]
            files[rel] = info
            continue
        try:
            text = path.read_text(encoding="utf-8").lstrip("\ufeff")
        except (OSError, UnicodeDecodeError):
            errors += 1
            continue
        lang = lang_of(path)
        try:
            parsed = parse_python(text) if lang == "py" else parse_regex(text, lang)
        except (SyntaxError, ValueError, RecursionError):
            parsed = parse_regex(text, lang)
        defs, raw, calls, routes = parsed
        fr = file_routes(rel)
        if fr and lang in ("js", "py", "rb", "php"):
            routes = routes + [["FILE", fr, 1]]
        files[rel] = {"sig": sig, "lang": lang, "lines": text.count("\n") + 1, "defs": defs, "raw": [list(x) for x in raw],
                      "raw_imports": raw, "calls": calls, "routes": routes, "test": _find.is_test(PurePosixPath(rel))}
        reparsed += 1
    graph = {"version": VERSION, "root": str(base), "files": files}
    resolve_imports(graph)
    try:
        cpath.write_text(json.dumps(graph, separators=(",", ":")), encoding="utf-8")
    except OSError:
        pass
    graph["stats"] = {"files": len(files), "reparsed": reparsed, "errors": errors, "cache": str(cpath)}
    return graph


def importers_map(files):
    rev = defaultdict(set)
    for rel, info in files.items():
        for dep in info.get("imports", []):
            rev[dep].add(rel)
    return rev


def callers_of(files, name, exclude=None):
    out = []
    for rel, info in files.items():
        for line in info.get("calls", {}).get(name, []):
            if (rel, line) != exclude:
                out.append((rel, line))
    return out


def enclosing(info, line):
    best = None
    for name, start, end, _ in info.get("defs", []):
        if start <= line <= end and (best is None or start >= best[1]):
            best = (name, start)
    return best[0] if best else None


class Out:
    def __init__(self, limit):
        self.limit, self.lines, self.cut = limit, [], False

    def add(self, text):
        if self.cut:
            return False
        if sum(map(len, self.lines)) + len(self.lines) + len(text) + 1 > self.limit - 50:
            self.cut = True
            self.lines.append("[truncated: narrow it or raise --max-chars]")
            return False
        self.lines.append(text)
        return True

    def render(self):
        return "\n".join(self.lines)


def fmt_list(items, n):
    items = list(items)
    more = len(items) - n
    return ", ".join(items[:n]) + (f" (+{more} more)" if more > 0 else "")


def cmd_tree(graph, out, sub, depth):
    files = graph["files"]
    sub = sub.strip("/").replace("\\", "/") if sub else ""
    folders = defaultdict(lambda: {"files": 0, "lines": 0, "langs": Counter(), "defs": [], "tests": 0, "routes": 0})
    edges = Counter()

    def folder_of(rel):
        parts = PurePosixPath(rel).parts[:-1]
        if sub:
            sp = PurePosixPath(sub).parts
            if tuple(parts[:len(sp)]) != sp:
                return None
            parts = parts[len(sp):]
            prefix = sub + "/"
        else:
            prefix = ""
        return prefix + "/".join(parts[:depth]) if parts[:depth] else (sub or ".")

    for rel, info in files.items():
        f = folder_of(rel)
        if f is None:
            continue
        node = folders[f]
        node["files"] += 1
        node["lines"] += info["lines"]
        node["langs"][info["lang"]] += 1
        node["tests"] += info["test"]
        node["routes"] += len(info["routes"])
        if not info["test"]:
            node["defs"] += [d[0] for d in info["defs"] if d[3] != "method" and "." not in d[0]]
        for dep in info.get("imports", []):
            g = folder_of(dep)
            if g and g != f:
                edges[(f, g)] += 1
    out.add(f"{len(folders)} folders under {sub or 'project root'} ({sum(n['files'] for n in folders.values())} code files).")
    for name, n in sorted(folders.items(), key=lambda kv: (-kv[1]["files"], kv[0])):
        langs = "/".join(k for k, _ in n["langs"].most_common(3))
        extra = (f", {n['tests']} tests" if n["tests"] else "") + (f", {n['routes']} routes" if n["routes"] else "")
        deps = [g for (f, g), _ in edges.most_common() if f == name]
        line = f"\n{name}/  {n['files']} files, {n['lines']} lines, {langs}{extra}"
        if n["defs"]:
            line += f"\n  symbols: {fmt_list(n['defs'], 6)}"
        if deps:
            line += f"\n  imports from: {fmt_list(deps, 4)}"
        if not out.add(line):
            break


def find_symbol(files, name):
    hits = []
    for rel, info in files.items():
        for dname, start, end, kind in info["defs"]:
            if dname == name or dname.endswith("." + name):
                hits.append((info["test"], rel, start, end, dname, kind))
    return sorted(hits)


def add_memory(out, root, files, graph=None):
    near = set()
    if graph is not None:
        for rel, info in graph["files"].items():
            if rel in files:
                near |= set(info.get("imports", []))
            elif files & set(info.get("imports", [])):
                near.add(rel)
    notes = _find.memory_notes(root, files, near=near)
    if notes:
        out.add(_find.MEMORY_HEADER)
        for n in notes:
            if not out.add(n):
                break


def indirect_callers(files, direct, limit=8):
    """Second hop: who calls the functions that contain the direct call sites. Returns formatted rows."""
    rows, seen = [], set()
    for rel, line in direct:
        if files[rel]["test"]:
            continue
        via = enclosing(files[rel], line)
        if not via:
            continue
        short = via.split(".")[-1]
        if short in COMMON_NAMES or short.startswith("__"):
            continue  # name-based matching of update()/get()/run() would list unrelated callers
        for rel2, line2 in callers_of(files, short):
            key = (rel2, line2)
            if key in seen or key == (rel, line):
                continue
            seen.add(key)
            ctx = enclosing(files[rel2], line2)
            if ctx == via:
                continue
            rows.append((files[rel2]["test"], rel2, line2, ctx, short))
    rows.sort()
    return [f"{r}:{l}" + (f" in {c}" if c else "") + f" (via {v})" for _, r, l, c, v in rows[:limit]], len(rows)


def cmd_node(graph, out, target):
    files = graph["files"]
    rev = importers_map(files)
    key = rel_path(graph["root"], target)
    if key in files or [f for f in files if f.endswith("/" + key)]:
        rel = key if key in files else sorted(f for f in files if f.endswith("/" + key))[0]
        info = files[rel]
        out.add(f"file {rel}: {info['lines']} lines, {info['lang']}" + (", test" if info["test"] else ""))
        if info["defs"]:
            out.add("defines: " + fmt_list([f"{d[0]}:{d[1]}" for d in info["defs"]], 12))
        if info["routes"]:
            out.add("routes: " + fmt_list([f"{m} {p} (:{ln})" for m, p, ln in info["routes"]], 8))
        out.add("imports: " + (fmt_list(info["imports"], 10) or "none in project"))
        importers = sorted(rev.get(rel, []))
        out.add("imported by: " + (fmt_list(importers, 10) or "none found"))
        tests = sorted(r for r in importers if files[r]["test"])
        stem = PurePosixPath(rel).stem.lower()
        tests += sorted(r for r, i in files.items() if i["test"] and stem in PurePosixPath(r).stem.lower() and r not in tests)
        out.add("tests: " + (fmt_list(tests, 6) or "none found"))
        add_memory(out, graph["root"], {rel}, graph)
        return
    hits = find_symbol(files, target)
    if not hits:
        names = {d[0].split(".")[-1] for i in files.values() for d in i["defs"]}
        import difflib
        close = difflib.get_close_matches(target, list(names), n=6, cutoff=0.7)
        out.add(f"No file or symbol named {target}." + (f" Similar symbols: {', '.join(close)}" if close else ""))
        return
    for is_test, rel, start, end, dname, kind in hits[:4]:
        out.add(f"{kind} {dname}  {rel}:{start}-{end}" + ("  [test]" if is_test else ""))
    add_memory(out, graph["root"], {h[1] for h in hits[:4]}, graph)  # short and high-value: before long caller lists
    name = target.split(".")[-1]
    calls = callers_of(files, name)
    def_lines = {(h[1], h[2]) for h in hits}
    calls = [c for c in calls if c not in def_lines]
    calls.sort(key=lambda c: (files[c[0]]["test"], c))
    if calls:
        out.add(f"callers ({len(calls)}):")
        for rel, line in calls[:8]:
            ctx = enclosing(files[rel], line)
            if not out.add(f"  {rel}:{line}" + (f" in {ctx}" if ctx else "")):
                break
    else:
        out.add("callers: none found by name (dynamic calls are not tracked)")
    second, total2 = indirect_callers(files, calls, limit=4)
    if second:
        out.add(f"indirect callers ({total2}): " + ", ".join(second) + (" ..." if total2 > len(second) else ""))
    imp = sorted({r for h in hits for r in importers_map(files).get(h[1], [])})
    if imp:
        out.add("files importing its module: " + fmt_list(imp, 6))


def rel_path(base, given):
    """Project-relative POSIX path for user input: keeps leading dots (.eslintrc.js), accepts absolute paths."""
    p = str(given).replace("\\", "/")
    try:
        q = Path(given)
        if q.is_absolute():
            return q.resolve().relative_to(Path(base).resolve()).as_posix()
    except ValueError:
        return p
    while p.startswith("./"):
        p = p[2:]
    return p


def git_changes(base, ref):
    def run(*args):
        return subprocess.run(["git", "-C", str(base), "-c", "core.quotePath=false", *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=20)
    names = set()
    diff_args = ["diff", "--relative", "--name-only", ref] if ref else ["diff", "--relative", "--name-only", "HEAD"]
    r = run(*diff_args)
    if r.returncode != 0 and not ref:
        r = run("diff", "--relative", "--name-only")
    if r.returncode != 0:
        raise SystemExit(f"git diff failed: {r.stderr.strip()[:200]}")
    names.update(n for n in r.stdout.splitlines() if n)
    u = run("ls-files", "--others", "--exclude-standard")
    untracked = {n for n in u.stdout.splitlines() if n}
    names |= untracked
    ranges = defaultdict(list)
    for name in names:
        if name in untracked:
            ranges[name].append((1, 10**9))
            continue
        d = run("diff", "--relative", "-U0", ref or "HEAD", "--", name)
        for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", d.stdout, re.M):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            ranges[name].append((start, start + max(count, 1) - 1))
    return sorted(names), ranges


def cmd_impact(graph, out, base, paths, ref):
    files = graph["files"]
    if paths:
        changed = [rel_path(base, p) for p in paths]
        ranges = {p: [(1, 10**9)] for p in changed}
    else:
        changed, ranges = git_changes(base, ref)
    code = [c for c in changed if c in files]
    other = [c for c in changed if c not in files]
    if not changed:
        out.add("No changes found" + (f" against {ref}" if ref else " (staged, unstaged, or untracked)") + ".")
        return
    out.add(f"Impact of {len(changed)} changed files" + (f" vs {ref}" if ref else "") + f" ({len(code)} code, {len(other)} other).")
    rev = importers_map(files)
    symbols = []
    for rel in code:
        for name, start, end, kind in files[rel]["defs"]:
            if any(a <= end and b >= start for a, b in ranges.get(rel, [])) and kind != "method" or (
                    kind == "method" and any(a <= end and b >= start for a, b in ranges.get(rel, []))):
                symbols.append((rel, name, start, end))
    if symbols:
        out.add("changed symbols: " + fmt_list([f"{n} ({r}:{s})" for r, n, s, _ in symbols], 10))
    caller_rows = []
    for rel, name, start, end in symbols:
        short = name.split(".")[-1]
        for crel, line in callers_of(files, short):
            if crel == rel and start <= line <= end:
                continue
            caller_rows.append((files[crel]["test"], crel, line, short))
    caller_rows = sorted(set(caller_rows))
    non_test = [c for c in caller_rows if not c[0]]
    if non_test:
        out.add(f"callers ({len(non_test)}): " + fmt_list([f"{r}:{l} -> {n}" for _, r, l, n in non_test], 10))
        second, total2 = indirect_callers(files, [(r, l) for _, r, l, _ in non_test])
        if second:
            out.add(f"indirect callers ({total2}): " + ", ".join(second) + (" ..." if total2 > len(second) else ""))
    lvl1 = sorted({i for c in code for i in rev.get(c, [])} - set(code))
    lvl2 = sorted({i for c in lvl1 for i in rev.get(c, [])} - set(code) - set(lvl1))
    if lvl1:
        out.add("importers: " + fmt_list(lvl1, 10))
    if lvl2:
        out.add("importers of importers: " + fmt_list(lvl2, 8))
    affected = set(code) | set(lvl1) | set(lvl2)
    tests = {r for r in affected if files[r]["test"]} | {c[1] for c in caller_rows if c[0]}
    stems = {PurePosixPath(c).stem.lower() for c in code if not files[c]["test"]}
    tests |= {r for r, i in files.items() if i["test"] and any(s in PurePosixPath(r).stem.lower() for s in stems)}
    out.add("tests to run: " + (fmt_list(sorted(tests), 8) or "none found; consider adding one"))
    routes = [f"{m} {p} ({r}:{ln})" for r in sorted(affected) if not files[r]["test"] for m, p, ln in files[r]["routes"]]
    if routes:
        out.add("routes affected: " + fmt_list(routes, 8))
    add_memory(out, base, set(changed), graph)
    risk = len(non_test) + len(lvl1) + 2 * len(routes)
    out.add(f"blast radius: {'high' if risk >= 10 else 'medium' if risk >= 3 else 'low'} "
            f"({len(non_test)} callers, {len(lvl1) + len(lvl2)} importers, {len(routes)} routes). Name-based; dynamic dispatch is not tracked.")
    if other:
        out.add("not analyzed (non-code or not indexed): " + fmt_list(other, 6))


def add_history(out, graph, target):
    """brief = node + the last commits that touched the file(s), so one call answers 'what is this and what changed'."""
    files = graph["files"]
    key = rel_path(graph["root"], target)
    paths = [key] if key in files else sorted({h[1] for h in find_symbol(files, target)})[:2]
    for rel in paths:
        try:
            r = subprocess.run(["git", "-C", graph["root"], "-c", "core.quotePath=false", "log", "-n", "3", "--date=short",
                                "--format=%h %ad %s", "--", rel], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            return
        commits = [_find.safe_repo_text(c) for c in r.stdout.splitlines() if c.strip()] if r.returncode == 0 else []
        if commits and not out.add(f"recent commits on {rel}: " + " | ".join(commits)):
            return


def cmd_routes(graph, out, pattern):
    rows = []
    for rel, info in sorted(graph["files"].items()):
        if info["test"]:
            continue
        for method, path, line in info["routes"]:
            if pattern and pattern.lower() not in path.lower():
                continue
            rows.append(f"{method:6} {path}  {rel}:{line}")
    out.add(f"{len(rows)} routes" + (f" matching {pattern}" if pattern else "") + ".")
    for r in rows:
        if not out.add(r):
            break


for _stream in (sys.stdout, sys.stderr):  # never crash on non-ASCII output (Windows consoles default to cp1252)
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["build", "tree", "node", "brief", "impact", "routes"])
    p.add_argument("args", nargs="*")
    p.add_argument("--dir", default=".")
    p.add_argument("--depth", type=int, default=2)
    p.add_argument("--base", help="git ref to compare against for impact (default: working tree vs HEAD)")
    p.add_argument("--max-chars", type=int, default=1600)
    p.add_argument("--refresh", action="store_true", help="ignore the cache and parse every file")
    a = p.parse_args()
    base = Path(a.dir).resolve()
    if not base.is_dir():
        p.error(f"expected an existing directory: {base}")
    if a.max_chars < 200 or a.depth < 1:
        p.error("--max-chars must be at least 200 and --depth at least 1")
    graph = build(base, refresh=a.refresh or a.command == "build")
    out = Out(a.max_chars)
    s = graph["stats"]
    if a.command == "build":
        out.add(f"Graph built: {s['files']} code files ({s['reparsed']} parsed, {s['errors']} unreadable). Cache: {s['cache']}")
        if graph.get("unresolved"):
            out.add("Unresolved project imports: " + fmt_list(graph["unresolved"], 6))
    elif a.command == "tree":
        cmd_tree(graph, out, a.args[0] if a.args else "", a.depth)
    elif a.command in ("node", "brief"):
        if not a.args:
            p.error(f"{a.command} needs a file path or symbol name")
        cmd_node(graph, out, a.args[0])
        if a.command == "brief":
            add_history(out, graph, a.args[0])
    elif a.command == "impact":
        cmd_impact(graph, out, base, a.args, a.base)
    elif a.command == "routes":
        cmd_routes(graph, out, a.args[0] if a.args else "")
    print(out.render())


if __name__ == "__main__":
    main()
