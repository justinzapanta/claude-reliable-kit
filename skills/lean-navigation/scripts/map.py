#!/usr/bin/env python3
"""Print a compact, body-free repository map. Usage: map.py [DIR] [--max-chars 5000]."""
import argparse
import os
import subprocess
from collections import Counter
from pathlib import Path

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "dist", "build", "coverage", "__pycache__", ".venv", "venv", ".next", ".nuxt", "target", ".idea", ".turbo", "vendor", "Pods", "DerivedData"}
SOURCE_EXTS = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".cs": "C#", ".cpp": "C++", ".c": "C", ".h": "C/C++", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".vue": "Vue", ".svelte": "Svelte"}
MANIFESTS = {"pyproject.toml", "requirements.txt", "package.json", "pnpm-workspace.yaml", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts", "Gemfile", "composer.json", "Makefile", "justfile", "Dockerfile", "AGENTS.md", "CLAUDE.md", "README.md"}
ENTRY_STEMS = {"main", "app", "server", "index", "cli", "__main__", "manage"}


def repo_files(base):
    try:
        top = subprocess.run(["git", "-C", str(base), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=3)
        if top.returncode == 0:
            git_root = Path(top.stdout.strip()).resolve()
            proc = subprocess.run(["git", "-C", str(git_root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], capture_output=True, timeout=10)
            if proc.returncode == 0:
                for raw in proc.stdout.decode("utf-8", "replace").split("\0"):
                    if raw:
                        path = git_root / raw
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dir", nargs="?", default=".")
    p.add_argument("--max-chars", type=int, default=5000)
    p.add_argument("--max-files", type=int, default=10000)
    a = p.parse_args()
    if a.max_chars < 200 or a.max_files < 1:
        p.error("--max-chars must be at least 200 and --max-files at least 1")
    base = Path(a.dir).resolve()
    paths = []
    source_counts, areas = Counter(), Counter()
    manifests, entries = [], []
    for path in repo_files(base):
        if len(paths) >= a.max_files:
            break
        try:
            rel = path.relative_to(base).as_posix()
        except ValueError:
            continue
        paths.append(rel)
        source = SOURCE_EXTS.get(path.suffix.lower())
        if source:
            source_counts[source] += 1
            parts = Path(rel).parts
            area = "/".join(parts[:-1][:2]) if len(parts) > 1 else "."
            areas[area] += 1
        if path.name in MANIFESTS:
            manifests.append(rel)
        if path.stem.lower() in ENTRY_STEMS and source:
            entries.append(rel)
    lines = [f"Repository map for {base}", f"Files indexed: {len(paths)}" + (" (file cap reached)" if len(paths) >= a.max_files else ""), "Source counts: " + (", ".join(f"{k} {v}" for k, v in source_counts.most_common(8)) or "none recognized"), "", "Key manifests and instructions:"]
    lines.extend(f"- {x}" for x in sorted(manifests)[:40] or ["(none found)"])
    lines.extend(["", "Likely entry points:"])
    lines.extend(f"- {x}" for x in sorted(entries)[:40] or ["(none recognized)"])
    lines.extend(["", "Largest source areas:"])
    lines.extend(f"- {name}: {count} files" for name, count in areas.most_common(16))
    lines.extend(["", "This map has paths and counts only, no source bodies. Use targeted search/open next; treat paths as leads, not proof."])
    text = "\n".join(lines)
    if len(text) > a.max_chars:
        text = text[:a.max_chars - 20].rstrip() + "\n[map truncated]"
    print(text)


if __name__ == "__main__":
    main()
