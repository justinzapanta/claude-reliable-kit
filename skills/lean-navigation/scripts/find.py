#!/usr/bin/env python3
"""Bounded regex search. Usage: find.py REGEX [DIR] [--ext py,js] [--max-hits 6] [--max-chars 1600]"""
import argparse
import ast
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "dist", "build", "coverage", "__pycache__", ".venv", "venv", ".next", ".nuxt", "target", ".idea", ".turbo", "vendor", "Pods", "DerivedData"}
SKIP_EXT = (".lock", ".min.js", ".map", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".woff", ".woff2", ".ico", ".svg", ".pyc")
LANGS = {".py": "py", ".js": "js", ".jsx": "js", ".ts": "ts", ".tsx": "ts", ".go": "go", ".rs": "rs", ".java": "java", ".kt": "kt", ".cs": "cs", ".rb": "rb", ".php": "php", ".swift": "swift", ".vue": "vue", ".svelte": "svelte"}
MANIFESTS = {"pyproject.toml", "requirements.txt", "package.json", "pnpm-workspace.yaml", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts", "Gemfile", "composer.json", "Makefile", "Dockerfile", "AGENTS.md", "CLAUDE.md", "README.md"}
ENTRY_STEMS = {"main", "app", "server", "index", "cli", "__main__", "manage"}


def files_under(base):
    """Yield ordinary files, preferring git's ignore-aware file list."""
    try:
        top = subprocess.run(["git", "-C", str(base), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=3)
        if top.returncode == 0:
            git_root = Path(top.stdout.strip()).resolve()
            proc = subprocess.run(["git", "-C", str(git_root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], capture_output=True, timeout=10)
            if proc.returncode == 0:
                for name in proc.stdout.decode("utf-8", "replace").split("\0"):
                    if name:
                        path = git_root / name
                        try:
                            rel = path.relative_to(base)
                            if any(part in SKIP_DIRS for part in rel.parts):
                                continue
                            yield path
                        except ValueError:
                            continue
                return
    except (OSError, TimeoutError, subprocess.TimeoutExpired):
        pass
    for root, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            yield Path(root) / name


def changed_files(base):
    """Enumerate current files with local changes, relative to the requested directory."""
    diff = ["diff", "--relative", "--no-renames", "--name-only", "-z"]
    commands = [diff + ["--", "."], diff + ["--cached", "--", "."],
                ["ls-files", "--others", "--exclude-standard", "-z", "--", "."]]
    names = set()
    for args in commands:
        result = subprocess.run(["git", "-C", str(base), *args], capture_output=True,
                                timeout=15, check=True)
        names.update(os.fsdecode(raw) for raw in result.stdout.split(b"\0") if raw)
    return [base / name for name in sorted(names)
            if not SKIP_DIRS.intersection(Path(name).parts)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pattern")
    p.add_argument("dir", nargs="?", default=".")
    p.add_argument("--ext", default="", help="comma-separated extensions, e.g. py,ts")
    p.add_argument("--max-hits", type=int, default=6)
    p.add_argument("--max-chars", type=int, default=1600)
    p.add_argument("--max-files", type=int, default=2000)
    p.add_argument("--max-bytes", type=int, default=20_000_000, help="maximum total file bytes read")
    p.add_argument("--ctx", type=int, default=0, help="context lines around each match")
    p.add_argument("--map", action="store_true", help="include a compact path/count overview in this same invocation")
    p.add_argument("-i", action="store_true")
    p.add_argument("--symbol", action="store_true", help="find a literal identifier, prioritizing Python definitions")
    p.add_argument("--changed", action="store_true", help="search current files with uncommitted Git changes")
    a = p.parse_args()
    if min(a.max_hits, a.max_chars, a.max_files, a.max_bytes) < 1 or a.ctx < 0:
        p.error("limits must be positive and --ctx cannot be negative")
    try:
        rx = re.compile(r"(?<!\w)" + re.escape(a.pattern) + r"(?!\w)" if a.symbol else a.pattern, re.I if a.i else 0)
    except re.error as exc:
        p.error(f"invalid regex: {exc}")

    base = Path(a.dir).resolve()
    exts = {"." + e.strip(".").lower() for e in a.ext.split(",") if e.strip(".")}
    results, scanned, bytes_read = [], 0, 0
    languages, areas, manifests, entries = Counter(), Counter(), [], []
    limited = False
    try:
        candidates = changed_files(base) if a.changed else files_under(base)
    except (OSError, subprocess.SubprocessError) as exc:
        p.error(f"cannot list local Git changes in {base}: {type(exc).__name__}")
    for path in candidates:
        try:
            if path.is_symlink() or not path.is_file():
                continue
            if exts and path.suffix.lower() not in exts:
                continue
            if str(path).lower().endswith(SKIP_EXT):
                continue
            if a.map:
                try:
                    rel = path.relative_to(base)
                except ValueError:
                    rel = Path(path.name)
                parts = rel.parts
                area = "/".join(parts[:-1][:2]) if len(parts) > 1 else "."
                areas[area] += 1
                languages[LANGS.get(path.suffix.lower(), "other")] += 1
                if path.name in MANIFESTS:
                    manifests.append(rel.as_posix())
                if path.stem.lower() in ENTRY_STEMS:
                    entries.append(rel.as_posix())
            size = path.stat().st_size
            if size > 1_000_000 or bytes_read + size > a.max_bytes:
                limited = True
                continue
            if scanned >= a.max_files:
                limited = True
                break
            content = path.read_bytes()
            bytes_read += len(content)
            scanned += 1
            text = content.decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lines = text.splitlines()
        hits = [i for i, line in enumerate(lines) if rx.search(line)]
        if hits:
            definitions = set()
            if a.symbol and path.suffix.lower() == ".py":
                try:
                    tree = ast.parse(text)
                except (SyntaxError, ValueError, RecursionError):
                    tree = None
                if tree:
                    definitions = {node.lineno - 1 for node in ast.walk(tree)
                                   if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                                   and rx.fullmatch(node.name)}
            hits.sort(key=lambda i: (i not in definitions, i))
            results.append((path.relative_to(base), lines, hits, definitions))
    results.sort(key=lambda row: (not bool(row[3]), -len(row[2]), str(row[0]).casefold()))
    total = sum(len(row[2]) for row in results)
    out = [f"{total} matches in {len(results)} files; scanned {scanned} files / {bytes_read} bytes."]
    if a.changed:
        out[0] = "Local changes only: " + out[0]
    shown = 0
    for path, lines, hits, definitions in results:
        if shown >= a.max_hits:
            break
        out.append(f"\n{path} ({len(hits)} hits)")
        emitted_here = False
        for i in hits:
            if shown >= a.max_hits:
                break
            lo, hi = max(0, i - a.ctx), min(len(lines), i + a.ctx + 1)
            snippet = []
            for j in range(lo, hi):
                line = lines[j]
                match = rx.search(line) if j == i else None
                start = max(0, match.start() - 60) if match else 0
                excerpt = ("..." if start else "") + line[start:start + 200]
                label = " [definition]" if j in definitions else ""
                snippet.append(f"{'>' if j == i else ' '}{j + 1}{label}: {excerpt}")
            candidate = out + snippet
            if sum(map(len, candidate)) + len(candidate) - 1 > a.max_chars:
                break
            out.extend(snippet)
            shown += 1
            emitted_here = True
        if not emitted_here:
            out.pop()
            break
    if total > shown or limited:
        out.append(f"\nTruncated: {total - shown} matches not shown" + ("; scan limit reached" if limited else ". Narrow with --ext, a subdirectory, or a more specific pattern."))
    if a.map:
        out.extend(["", "Repo overview (paths/counts only; based on scanned scope):", "Languages: " + (", ".join(f"{k} {v}" for k, v in languages.most_common(6)) or "none recognized"), "Areas: " + (", ".join(f"{k} {v}" for k, v in areas.most_common(8)) or "none"), "Key files: " + (", ".join(sorted(set(manifests + entries))[:20]) or "none recognized")])
    rendered = "\n".join(out)
    if len(rendered) > a.max_chars:
        marker = "[truncated]"
        rendered = rendered[: max(0, a.max_chars - len(marker))] + marker[:a.max_chars]
    print(rendered)


if __name__ == "__main__":
    main()
