#!/usr/bin/env python3
"""Fuzz every kit script with random and malformed input. Stdlib only, deterministic per --seed.

Usage: python tools/fuzz.py [--rounds 40] [--seed 1]

Rules checked for every case: no Python traceback, an allowed exit code, output within budget, and for the hook:
exit 0 with either no output or a valid hook JSON object. In-process parser fuzzing runs 25x more cases than CLI
fuzzing because it is cheap. Exit code 1 on any failure; failing inputs are printed (truncated) for reproduction.
"""
import argparse
import importlib.util
import json
import os
import random
import shutil
import string
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = ROOT / "skills" / "lean-navigation" / "scripts"
LED = ROOT / "skills" / "task-ledger" / "scripts"
ENV = {**os.environ, "LEAN_MEMORY_FILE": "", "PYTHONUTF8": "1"}
ALPHABET = string.printable + "éñ中文✓🐛\u200b\ufeff\x00\x1b[31m"
failures = []


def rand_text(rng, n=200):
    parts = []
    for _ in range(rng.randint(1, 12)):
        pick = rng.random()
        if pick < 0.25:
            parts.append(f"  at {rng.choice(['Cart', 'x', ''])} ({rng.choice(['http://localhost:5173/', 'webpack:///', '/app/', '', 'C:\\\\src\\\\'])}"
                         f"{rng.choice(['src/a', 'lib/b', '../c', 'node_modules/x/y', 'd e/f'])}.{rng.choice(['js', 'tsx', 'py', 'go', 'rs', 'map'])}"
                         f"{rng.choice(['', '?t=1'])}:{rng.randint(0, 99999)}:{rng.randint(0, 99)})")
        elif pick < 0.4:
            parts.append(f'File "{rng.choice(["/a/b.py", "x.py", "", "C:/w/y.py"])}", line {rng.randint(-5, 10**9)}')
        elif pick < 0.55:
            parts.append(f"{rng.choice(['GET', 'POST', ''])} {rng.choice(['http://h', ''])}/api/{rng.choice(['users', '', '%%', 'a' * 300])}/"
                         f"{rng.randint(0, 10**12)} {rng.choice([500, 404, ''])}")
        elif pick < 0.7:
            parts.append(rng.choice(["TypeError: Cannot read properties of undefined (reading 'items')", "x is not a function",
                                     "NameError: name 'y' is not defined", "Can't resolve './z'", "Uncaught (in promise) Error:"]))
        else:
            parts.append("".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, n))))
    return "\n".join(parts)


def run(label, script, args, stdin=None, codes=(0,), budget=2600, cwd=None, check_json=False):
    args = [str(x).replace("\x00", "") for x in args]  # the OS cannot pass NUL in arguments to any program
    try:
        r = subprocess.run([sys.executable, "-I", str(script), *args], input=stdin, capture_output=True, cwd=cwd, env=ENV,
                           timeout=120)
    except subprocess.TimeoutExpired:
        failures.append((label, "timeout", args, stdin))
        return
    out, err = r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    problem = None
    if "Traceback" in err:
        problem = "traceback: " + err.strip().splitlines()[-1][:160]
    elif r.returncode not in codes:
        problem = f"exit {r.returncode}: {err.strip()[-160:]}"
    elif len(out.rstrip()) > budget:
        problem = f"output {len(out.rstrip())} > {budget}"
    elif check_json and out.strip():
        try:
            d = json.loads(out)
            assert d["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        except Exception as exc:  # noqa: BLE001 - any shape problem is a finding
            problem = f"bad hook JSON ({exc.__class__.__name__}): {out[:120]}"
    if problem:
        failures.append((label, problem, args, stdin))


def load(name, path):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rounds", type=int, default=40)
    p.add_argument("--seed", type=int, default=1)
    a = p.parse_args()
    rng = random.Random(a.seed)
    work = Path(tempfile.mkdtemp(prefix="kit-fuzz-"))
    repo = work / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text("def items():\n    return []\n", encoding="utf-8")
    (repo / "src" / "b.js").write_text('import { items } from "./a"\nexport const y = () => items()\n', encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, capture_output=True)
    cases = 0

    # 1. In-process parsers: graph's Python/regex parsers and route mapping, trace's clue extraction, squeeze's filters.
    graph = load("lean_graph_fuzz", NAV / "graph.py")
    trace = load("lean_trace_fuzz", NAV / "trace.py")
    squeeze = load("lean_squeeze_fuzz", NAV / "squeeze.py")
    for _ in range(a.rounds * 25):
        text = rand_text(rng, 400)
        for label, fn in [("graph.parse_regex js", lambda: graph.parse_regex(text, "js")),
                          ("graph.parse_regex go", lambda: graph.parse_regex(text, "go")),
                          ("graph.file_routes", lambda: graph.file_routes(text.replace("\n", "/")[:300])),
                          ("trace.extract", lambda: trace.extract(text)),
                          ("squeeze.select", lambda: squeeze.select(squeeze.clean(text * rng.randint(1, 30)), 400)),
                          ("squeeze.git_status", lambda: squeeze.squeeze_git_status(text.splitlines()))]:
            cases += 1
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                failures.append((label, f"{exc.__class__.__name__}: {exc}"[:160], [], text[:300]))
        cases += 1
        try:
            graph.parse_python(text)
        except (SyntaxError, ValueError, RecursionError):
            pass  # build() falls back to the regex parser on these
        except Exception as exc:  # noqa: BLE001
            failures.append(("graph.parse_python", f"{exc.__class__.__name__}: {exc}"[:160], [], text[:300]))

    # 2. CLI: trace, find, graph with random arguments.
    for i in range(a.rounds):
        cases += 4
        run("trace stdin", NAV / "trace.py", ["--dir", str(repo)], stdin=rand_text(rng).encode("utf-8", "surrogatepass"))
        pattern = "".join(rng.choice(ALPHABET.replace("\x00", "")) for _ in range(rng.randint(1, 12)))
        run("find pattern", NAV / "find.py", [pattern, str(repo)] + rng.sample(["--symbol", "-i", "--map", "--changed"], rng.randint(0, 2)),
            codes=(0, 2))
        run("graph node", NAV / "graph.py", ["node", pattern, "--dir", str(repo)], codes=(0, 2))
        run("graph impact", NAV / "graph.py", ["impact", pattern, "--dir", str(repo)], codes=(0, 1, 2))

    # 3. squeeze: random bytes on stdout/stderr and random exit codes must come back intact.
    for i in range(a.rounds):
        cases += 1
        code = rng.choice([0, 1, 2, 3, 77, 255])
        n = rng.randint(0, 200000)
        child = f"import sys,random;r=random.Random({i});sys.stdout.buffer.write(bytes(r.randrange(256) for _ in range({n})));" \
                f"sys.stderr.write('E'*{rng.randint(0, 5000)});sys.exit({code})"
        run("squeeze random bytes", NAV / "squeeze.py", ["--max-chars", str(rng.randint(300, 3000)), "--", sys.executable, "-c", child],
            codes=(code,), budget=3200, cwd=repo)

    # 4. Hook: malformed events must never fail or print anything but valid hook JSON.
    memory_cli = LED / "memory.py"
    subprocess.run([sys.executable, "-I", str(memory_cli), "add", "decision", "Keep items() pure", "--files", "src/a.py",
                    "--dir", str(repo)], capture_output=True, env=ENV)
    for i in range(a.rounds * 2):
        cases += 1
        shape = rng.random()
        if shape < 0.2:
            payload = bytes(rng.randrange(256) for _ in range(rng.randint(0, 300)))
        else:
            fp = rng.choice([str(repo / "src" / "a.py"), "src/a.py", "", None, 5, ["x"], "C:\\nope\\x.py", "/" * 300,
                             str(repo / "src" / "missing.py"), rand_text(rng, 40)])
            event = rng.choice([{"session_id": rng.choice(["s", None, 3]), "cwd": rng.choice([str(repo), "", None, 7]),
                                 "tool_name": "Edit", "tool_input": {"file_path": fp}},
                                {"tool_input": fp}, [], None, {"tool_input": None}, "string"])
            payload = json.dumps(event).encode("utf-8")
        run("hook event", LED / "memory_hook.py", [], stdin=payload, codes=(0,), check_json=True)

    # 5. memory CLI: random sequences of commands and texts.
    for i in range(a.rounds):
        cases += 1
        cmd = rng.choice([["add", rng.choice(["bug", "decision", "gotcha", "concept", "pref", "todo"]), rand_text(rng, 80),
                           "--files", rng.choice(["src/a.py", ".x", "../out.py", "", "a,b,,c"])],
                          ["recall", *rand_text(rng, 20).split()[:3]], ["recall", "--file", rng.choice(["src/a.py", "", "zz"])],
                          ["link", str(rng.randint(-1, 5)), str(rng.randint(0, 5))], ["forget", str(rng.randint(0, 9))],
                          ["done", str(rng.randint(0, 9))], ["show", str(rng.randint(0, 9))], ["stale"], ["list"], ["seed", "--dry-run"]])
        run("memory " + cmd[0], memory_cli, [*cmd, "--dir", str(repo)], codes=(0, 1, 2))

    # 6. installer: random settings.json and CLAUDE.md shapes, always with --dry-run into a scratch home.
    for i in range(a.rounds // 2):
        cases += 1
        home, proj = work / f"home{i}", work / f"proj{i}"
        (home / ".claude").mkdir(parents=True)
        proj.mkdir()
        settings = rng.choice(['{}', '{"hooks": null}', '{"hooks": []}', '{"hooks": {"PreToolUse": {}}}', '[]', 'null', '{bad',
                               '{"hooks": {"PreToolUse": [{"hooks": [{"command": 5}]}]}}', '// c\n{}', '{"permissions": {"allow": []}}'])
        (home / ".claude" / "settings.json").write_text(settings, encoding="utf-8")
        md = rng.choice(["", "# x\n", "<!-- claude-reliable-kit:begin -->\n", "<!-- claude-reliable-kit:end -->\n<!-- claude-reliable-kit:begin -->\n",
                         "<!-- claude-reliable-kit:begin -->\nold\n<!-- claude-reliable-kit:end -->\n"])
        (proj / "CLAUDE.md").write_text(md, encoding="utf-8")
        run("install dry-run", ROOT / "install.py", ["--all", "--dry-run", "--home", str(home)], codes=(0, 1), cwd=proj, budget=10000)
        run("uninstall dry-run", ROOT / "install.py", ["--uninstall", "--dry-run", "--home", str(home)], codes=(0, 1), cwd=proj, budget=10000)
        before = (home / ".claude" / "settings.json").read_text(encoding="utf-8")
        if before != settings:
            failures.append(("install dry-run", "dry run changed settings.json", [], settings))

    shutil.rmtree(work, ignore_errors=True)
    seen = set()
    for label, problem, args, stdin in failures:
        key = (label, problem.split(":")[0])
        if key in seen:
            continue
        seen.add(key)
        print(f"FAIL {label}: {problem}")
        print(f"     args={str(args)[:160]} input={repr(stdin)[:200]}")
    print(f"{cases} fuzz cases, {len(failures)} failures ({len(seen)} distinct)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
