"""Workbench: run every kit command on real repositories; check exit codes, tracebacks, and output budgets.

Usage: python tools/workbench.py DIR
DIR holds one or more Git checkouts (for example clones of flask, express, and fastapi). The kit's caches inside
each checkout's .git folder are deleted first. Any row not marked "ok" is a bug.
"""
import json, os, subprocess, sys, time
from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "skills"
NAV, LED = KIT / "lean-navigation" / "scripts", KIT / "task-ledger" / "scripts"
REAL = Path(sys.argv[1])
rows = []


def run(label, repo, script, *args, budget=1600, stdin=None, expect_codes=(0,)):
    t = time.perf_counter()
    p = subprocess.run([sys.executable, "-I", str(script), *map(str, args)], cwd=repo, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", input=stdin, timeout=600,
                       env={**os.environ, "LEAN_MEMORY_FILE": "", "LEAN_HOOK_DEBUG": "1"})
    dt = time.perf_counter() - t
    out = p.stdout.rstrip("\n")
    problems = []
    if p.returncode not in expect_codes:
        problems.append(f"exit {p.returncode}")
    if budget and len(out) > budget:
        problems.append(f"output {len(out)} > {budget}")
    if p.stderr.strip() and "Traceback" in p.stderr:
        problems.append("TRACEBACK: " + p.stderr.strip().splitlines()[-1][:160])
    rows.append((repo.name, label, f"{dt:6.2f}s", len(out), "; ".join(problems) or "ok"))
    return out


for repo in sorted(p for p in REAL.iterdir() if (p / ".git").exists()):
    for f in (".git/lean-graph.json", ".git/lean-memory.json", ".git/lean-hook-seen.json"):
        (repo / f).unlink(missing_ok=True)
    run("graph build (cold)", repo, NAV / "graph.py", "build", "--dir", ".")
    run("graph build (warm)", repo, NAV / "graph.py", "tree", "--dir", ".")
    run("graph tree", repo, NAV / "graph.py", "tree", "--dir", ".")
    run("graph routes", repo, NAV / "graph.py", "routes", "--dir", ".")
    sym = {"flask": "url_for", "express": "createApplication", "fastapi": "get_openapi"}.get(repo.name, "main")
    run(f"graph node {sym}", repo, NAV / "graph.py", "node", sym, "--dir", ".")
    run("graph impact HEAD~5", repo, NAV / "graph.py", "impact", "--dir", ".", "--base", "HEAD~5")
    run(f"find --symbol {sym}", repo, NAV / "find.py", sym, ".", "--symbol")
    run("find regex", repo, NAV / "find.py", r"raise \w+Error\(", ".")
    run("find --map", repo, NAV / "find.py", "TODO", ".", "--map")
    run("outline .", repo, NAV / "outline.py", ".")
    run("map", repo, NAV / "map.py", ".", budget=5000)
    run("trace python tb", repo, NAV / "trace.py", "--dir", ".",
        f'Traceback (most recent call last):\n  File "/site/{repo.name}/app.py", line 10, in x\nAttributeError: \'NoneType\' object has no attribute \'{sym}\'')
    run("trace js error", repo, NAV / "trace.py", "--dir", ".",
        "TypeError: Cannot read properties of undefined (reading 'handle')\n    at Layer.handle (/app/lib/router/layer.js:95:5)\nGET /users/42/posts 500")
    out = run("memory seed", repo, LED / "memory.py", "seed", "--dir", ".")
    run("memory recall --changed", repo, LED / "memory.py", "recall", "--changed", "--dir", ".")
    run("memory stale", repo, LED / "memory.py", "stale", "--dir", ".")
    first_code = next(f for f in subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True).stdout.split()
                      if f.endswith((".py", ".js")))
    ev = json.dumps({"session_id": "wb", "cwd": str(repo), "tool_name": "Edit",
                     "tool_input": {"file_path": str(repo / first_code)}})
    run("hook on edit", repo, LED / "memory_hook.py", stdin=ev, budget=2500)
    run("squeeze git log", repo, NAV / "squeeze.py", "--", "git", "log", "-n", "200", "--stat", budget=2400)

w = [max(len(str(r[i])) for r in rows) for i in range(5)]
for r in rows:
    print("  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))

bad_rows = [r for r in rows if r[4] != "ok"]
print(f"{len(rows) - len(bad_rows)}/{len(rows)} workbench checks passed")
sys.exit(1 if bad_rows else 0)
