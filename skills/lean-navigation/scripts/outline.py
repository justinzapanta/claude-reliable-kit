#!/usr/bin/env python3
"""Show bounded symbol/heading outlines. Usage: outline.py FILE_OR_DIR [--max 60]."""
import argparse
import ast
import os
import re
import subprocess
from pathlib import Path

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "dist", "build", "coverage", "__pycache__", ".venv", "venv", ".next", ".nuxt", "target", ".idea", ".turbo", "vendor", "Pods", "DerivedData"}
EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".php", ".c", ".cpp", ".cs", ".md"}
GENERIC = re.compile(r"^\s*(export\s+)?(default\s+)?(async\s+)?(function\*?|class|interface|type|enum|struct|trait|impl|fn|func|def)\s+\w+|^\s*(export\s+)?const\s+\w+\s*=\s*(async\s*)?\(?[^=]*=>")
HEADING = re.compile(r"^#{1,4}\s+\S")


def candidates(target, max_files):
    target = Path(target).resolve()
    if target.is_file():
        yield target
        return
    try:
        top = subprocess.run(["git", "-C", str(target), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=3)
        if top.returncode == 0:
            root = Path(top.stdout.strip()).resolve()
            listing = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], capture_output=True, timeout=10)
            if listing.returncode == 0:
                count = 0
                for name in listing.stdout.decode("utf-8", "replace").split("\0"):
                    if not name:
                        continue
                    path = root / name
                    try:
                        rel = path.relative_to(target)
                    except ValueError:
                        continue
                    if any(part in SKIP_DIRS for part in rel.parts) or path.suffix.lower() not in EXTS:
                        continue
                    yield path
                    count += 1
                    if count >= max_files:
                        return
                return
    except (OSError, TimeoutError, subprocess.TimeoutExpired):
        pass
    count = 0
    for root, dirs, names in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            path = Path(root) / name
            if path.suffix.lower() in EXTS:
                yield path
                count += 1
                if count >= max_files:
                    return


def symbols(path, src):
    lines = src.splitlines()
    if path.suffix.lower() == ".py":
        try:
            tree = ast.parse(src)
        except SyntaxError:
            tree = None
        if tree is not None:
            out = []
            def visit(node, depth=0):
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        kind = "class" if isinstance(item, ast.ClassDef) else "def"
                        out.append(f"{item.lineno}: {'  ' * depth}{kind} {item.name}")
                        if isinstance(item, ast.ClassDef):
                            visit(item, depth + 1)
            visit(tree)
            return len(lines), out
    out = []
    for i, line in enumerate(lines, 1):
        if (path.suffix.lower() == ".md" and HEADING.match(line)) or (path.suffix.lower() != ".md" and GENERIC.match(line)):
            out.append(f"{i}: {line.strip()[:100]}")
    return len(lines), out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("target")
    p.add_argument("--max", type=int, default=60, help="maximum symbols/headings")
    p.add_argument("--max-files", type=int, default=200)
    p.add_argument("--max-bytes", type=int, default=10_000_000)
    p.add_argument("--max-chars", type=int, default=5000)
    a = p.parse_args()
    if min(a.max, a.max_files, a.max_bytes) < 1 or a.max_chars < 200:
        p.error("--max, --max-files, and --max-bytes must be positive; --max-chars must be at least 200")
    out, shown, files, bytes_read, truncated = [], 0, 0, 0, False
    for path in candidates(a.target, a.max_files + 1):
        if files >= a.max_files:
            truncated = True
            break
        try:
            size = path.stat().st_size
            if size > 1_000_000 or bytes_read + size > a.max_bytes:
                continue
            src = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        files += 1
        bytes_read += size
        line_count, items = symbols(path, src)
        if not items:
            continue
        header = f"\n{path} ({line_count} lines, {len(items)} symbols/headings)"
        if sum(map(len, out)) + len(out) + len(header) > a.max_chars:
            truncated = True
            break
        out.append(header)
        for item in items:
            if shown >= a.max:
                truncated = True
                break
            row = "  " + item
            if sum(map(len, out)) + len(out) + len(row) > a.max_chars:
                truncated = True
                break
            out.append(row)
            shown += 1
        if truncated:
            break
    out.insert(0, f"Outlined {files} files / {bytes_read} bytes; {shown} symbols/headings shown.")
    if truncated:
        out.append("\nTruncated by a configured limit; narrow the directory or raise one limit only if needed.")
    rendered = "\n".join(out)
    if len(rendered) > a.max_chars:
        marker = "[truncated]"
        rendered = rendered[: max(0, a.max_chars - len(marker))] + marker
    print(rendered)


if __name__ == "__main__":
    main()
