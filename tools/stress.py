#!/usr/bin/env python3
"""Stress test: generate a large, messy repository and time every kit command against budgets. Stdlib only.

Usage: python tools/stress.py [--files 6000] [--keep DIR]

The repo mixes Python, JS/TS, Go and Rust; deep folders; long files; very long lines; non-UTF-8 and binary files;
non-ASCII and dotted file names; a 3 MB log; 300 commits of history with fix commits. Each command must exit
cleanly, stay within its output budget, and finish within its time budget (generous, to survive slow CI disks).
Exit code 1 if anything fails.
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = ROOT / "skills" / "lean-navigation" / "scripts"
LED = ROOT / "skills" / "task-ledger" / "scripts"
ENV = {**os.environ, "LEAN_MEMORY_FILE": "", "PYTHONUTF8": "1", "GIT_AUTHOR_NAME": "s", "GIT_AUTHOR_EMAIL": "s@example.invalid",
       "GIT_COMMITTER_NAME": "s", "GIT_COMMITTER_EMAIL": "s@example.invalid"}


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=ENV)


def generate(repo, n_files, rng):
    repo.mkdir(parents=True)
    langs = [("py", "def {f}(x):\n    return helper_{g}(x)\n\n"), ("ts", "export function {f}(x: number) {{ return helper_{g}(x) }}\n"),
             ("js", "const {f} = (x) => helper_{g}(x)\nmodule.exports = {{ {f} }}\n"),
             ("go", "func {f}(x int) int {{ return helper_{g}(x) }}\n"), ("rs", "pub fn {f}(x: u32) -> u32 {{ helper_{g}(x) }}\n")]
    paths = []
    for i in range(n_files):
        ext, tmpl = langs[i % len(langs)]
        depth = rng.randint(1, 9)
        folder = "/".join(f"d{rng.randint(0, 40)}" for _ in range(depth))
        rel = f"{folder}/m{i}.{ext}"
        body = "".join(tmpl.format(f=f"fn_{i}_{k}", g=rng.randint(0, n_files)) for k in range(rng.randint(1, 30)))
        if ext == "py" and i % 7 == 0:
            body = f"from d{rng.randint(0, 40)} import m{rng.randint(0, n_files)}\n" + body
        if ext == "ts" and i % 7 == 0:
            body = f'import {{ fn_{i}_0 }} from "../d{rng.randint(0, 40)}/m{rng.randint(0, n_files)}"\n' + body
        if i % 50 == 0:
            body += "# NOTE: generated module; do not hand-edit\n" if ext == "py" else "// WARNING: keep in sync with schema\n"
        if i % 97 == 0:
            body += "x = '" + "a." * 4000 + "'\n"  # very long line
        paths.append(rel)
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes((body).encode("utf-8"))
    (repo / "api").mkdir()
    (repo / "api" / "routes.py").write_text("".join(f'@app.get("/api/items/{{item_id}}/r{k}")\ndef r{k}(item_id):\n    return {k}\n'
                                                    for k in range(200)), encoding="utf-8")
    (repo / "big").mkdir()
    (repo / "big" / "huge.py").write_text("".join(f"def big_{k}():\n    return {k}\n" for k in range(40000)), encoding="utf-8")
    (repo / "weird").mkdir()
    (repo / "weird" / "café ñ 中文.py").write_text("def unicode_name():\n    return 'ok'\n", encoding="utf-8")
    (repo / "weird" / ".hidden.js").write_text("export const hidden = 1\n", encoding="utf-8")
    (repo / "weird" / "latin1.py").write_bytes("s = 'caf\xe9'\n".encode("latin-1"))
    (repo / "weird" / "bom.py").write_bytes("﻿def bom():\n    return 1\n".encode("utf-8"))
    (repo / "weird" / "crlf.js").write_bytes(b"export function crlf() {\r\n  return 1\r\n}\r\n")
    (repo / "weird" / "blob.bin").write_bytes(bytes(range(256)) * 400)
    (repo / "logs").mkdir()
    (repo / "logs" / "app.log").write_text("".join(f"[INFO] request {k} ok\n" for k in range(150000)), encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "Initial import")
    for c in range(300):
        rel = rng.choice(paths)
        with open(repo / rel, "a", encoding="utf-8") as fh:
            fh.write(f"# change {c}\n" if rel.endswith(".py") else f"// change {c}\n")
        msg = rng.choice(["Fix crash in {r}", "Refactor {r}", "Revert change to {r}", "Update docs", "fix: handle null in {r}"])
        git(repo, "commit", "-qam", msg.format(r=rel))
    return paths


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--files", type=int, default=6000)
    p.add_argument("--keep", help="generate into this folder and keep it")
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()
    rng = random.Random(a.seed)
    base = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="kit-stress-"))
    repo = base / "repo"
    if repo.exists():
        shutil.rmtree(repo)
    t0 = time.perf_counter()
    paths = generate(repo, a.files, rng)
    print(f"generated {a.files} files + edge cases in {time.perf_counter() - t0:.1f}s at {repo}")
    t0 = time.perf_counter()
    for f in repo.rglob("*"):  # read once so timings measure the kit, not an antivirus scanning brand-new files
        if f.is_file() and ".git" not in f.parts:
            f.read_bytes()
    print(f"pre-read all files in {time.perf_counter() - t0:.1f}s (first-touch scanning excluded from timings)")
    for f in (repo / ".git").glob("lean-*"):
        f.unlink()
    some = next(x for x in paths if x.endswith(".py"))
    sym = "fn_5_0"
    # (label, script, args, stdin, time budget s, output budget chars, allowed exit codes)
    checks = [
        ("graph build (cold)", NAV / "graph.py", ["build", "--dir", "."], None, 120, 1600, (0,)),
        ("graph tree (warm)", NAV / "graph.py", ["tree", "--dir", "."], None, 20, 1600, (0,)),
        ("graph node", NAV / "graph.py", ["node", sym, "--dir", "."], None, 20, 1600, (0,)),
        ("graph routes", NAV / "graph.py", ["routes", "/api", "--dir", "."], None, 20, 1600, (0,)),
        ("graph impact HEAD~50", NAV / "graph.py", ["impact", "--base", "HEAD~50", "--dir", "."], None, 60, 1600, (0,)),
        ("graph node unicode file", NAV / "graph.py", ["node", "weird/café ñ 中文.py", "--dir", "."], None, 20, 1600, (0,)),
        ("find --symbol", NAV / "find.py", [sym, ".", "--symbol"], None, 30, 1600, (0,)),
        ("find no match", NAV / "find.py", ["fn_zzz_nothing", ".", "--symbol"], None, 30, 1600, (0,)),
        ("outline huge file", NAV / "outline.py", ["big/huge.py"], None, 20, 1600, (0,)),
        ("map", NAV / "map.py", ["."], None, 30, 1600, (0,)),
        ("trace long paste", NAV / "trace.py", ["--dir", "."], "TypeError: " + "a." * 50000 + f"\n  at x ({some}:2:1)", 30, 1600, (0,)),
        ("squeeze 3 MB log", NAV / "squeeze.py", ["--", sys.executable, "-c", "print(open('logs/app.log').read()); raise SystemExit(2)"],
         None, 30, 2000, (2,)),
        ("memory seed", LED / "memory.py", ["seed", "--dir", "."], None, 60, 1600, (0,)),
        ("memory recall --changed", LED / "memory.py", ["recall", "--changed", "--dir", "."], None, 20, 1600, (0,)),
        ("memory stale", LED / "memory.py", ["stale", "--dir", "."], None, 30, 1600, (0,)),
        ("hook on edit", LED / "memory_hook.py", [], json.dumps({"session_id": "s", "cwd": str(repo), "tool_name": "Edit",
                                                                  "tool_input": {"file_path": str(repo / some)}}), 10, 2500, (0,)),
    ]
    failures = 0
    for label, script, args, stdin, tbudget, obudget, codes in checks:
        t = time.perf_counter()
        r = subprocess.run([sys.executable, "-I", str(script), *args], cwd=repo, input=stdin, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=ENV, timeout=600)
        dt = time.perf_counter() - t
        out = r.stdout.rstrip("\n")
        bad = []
        if r.returncode not in codes:
            bad.append(f"exit {r.returncode}")
        if "Traceback" in r.stderr:
            bad.append("traceback: " + r.stderr.strip().splitlines()[-1][:120])
        if len(out) > obudget:
            bad.append(f"output {len(out)} > {obudget}")
        if dt > tbudget:
            bad.append(f"time {dt:.1f}s > {tbudget}s")
        failures += bool(bad)
        print(f"{'FAIL' if bad else 'ok  '} {label:28} {dt:6.2f}s {len(out):5} chars  {'; '.join(bad)}")
    if not a.keep:
        shutil.rmtree(base, ignore_errors=True)
    print(f"{len(checks) - failures}/{len(checks)} stress checks passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
