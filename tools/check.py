#!/usr/bin/env python3
"""One command for the whole quality process. Stdlib only.

  python tools/check.py            # fast: unit + lint tests, package check, fuzz (quick)        ~1-2 min
  python tools/check.py --full     # + deeper fuzz and the large-repo stress test                 ~5-15 min
  python tools/check.py --repos D  # + the real-repository workbench on Git checkouts in D

Every step must pass; the summary lists each step with its time. Exit code 1 on any failure.
Run the fast check before every commit and the full check before a release (CI runs both).
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def step(name, cmd, results, timeout=3600):
    print(f"\n=== {name}: {' '.join(str(c) for c in cmd)}", flush=True)
    start = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=ROOT, timeout=timeout, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        ok = r.returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    results.append((name, ok, time.perf_counter() - start))
    return ok


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--full", action="store_true", help="deeper fuzzing and the large-repo stress test")
    p.add_argument("--repos", help="folder of real Git checkouts for tools/workbench.py")
    a = p.parse_args()
    py = sys.executable
    results = []
    step("rebuild release ZIPs", [py, "-I", "tools/package_skills.py"], results)  # first: tests compare ZIPs to sources
    step("release ZIPs match sources", [py, "-I", "tools/package_skills.py", "--check"], results)
    step("unit and lint tests", [py, "-m", "unittest", "discover", "-s", "tests"], results)
    step("fuzz (seed 1)", [py, "-I", "tools/fuzz.py", "--rounds", "40" if a.full else "12", "--seed", "1"], results)
    if a.full:
        step("fuzz (seed 2)", [py, "-I", "tools/fuzz.py", "--rounds", "40", "--seed", "2"], results)
        step("stress: large messy repo", [py, "-I", "tools/stress.py", "--files", "6000"], results)
    if a.repos:
        step("workbench: real repositories", [py, "-I", "tools/workbench.py", a.repos], results)
    print("\n=== Summary")
    for name, ok, secs in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:32} {secs:7.1f}s")
    failed = [n for n, ok, _ in results if not ok]
    print("All checks passed." if not failed else f"{len(failed)} step(s) failed: {', '.join(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
