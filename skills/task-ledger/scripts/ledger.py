#!/usr/bin/env python3
"""Task ledger with an evidence graph: what the task needs, what was tried, and what proves it. Stdlib only.

  goal TEXT                                  the task's goal
  add req|decision|loc|open|pref TEXT [TEXT ...] [--files a,b] [--src user|inferred] [--replace ID]
  hypo TEXT [--files a,b]                    a guess to confirm or rule out
  fact TEXT --run "COMMAND" [--expect-exit N] [--proves ID,..|all] [--kills ID,..] [--files a,b]
                                             run COMMAND now; store exit code and decisive output lines as evidence
  fact TEXT --seen "OBSERVATION" [...]       evidence observed without a command (weaker; prove says so)
  link A proves|kills|derived_from B         connect two entries
  prove                                      unproven requirements, open hypotheses, failing or stale evidence (exit 1 if any)
  tree                                       the exploration graph: goal, requirements and hypotheses, the evidence on each
  coverage [--base REF]                      what the change affects (code graph impact) vs what the evidence checked
  close                                      promote proven bugs and decisions to project memory
  verify ID HOW | done ID | rm ID | show [--open] | summary | get ID | export | trim | init

Stored in .git/task-ledger.json inside a Git work tree (never committed), else ledger.json in the current directory.
Override with LEDGER_FILE. Output is bounded; evidence keeps at most 3 decisive output lines per command.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import locale
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True


def default_file():
    try:
        r = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return os.path.join(r.stdout.strip(), "task-ledger.json")
    except (OSError, subprocess.SubprocessError):
        pass
    return "ledger.json"


FILE = os.environ.get("LEDGER_FILE") or default_file()
KINDS = ["req", "decision", "loc", "verified", "open", "pref"]
CAP = 60
DROP_ORDER = ["verified", "loc", "decision"]  # never drops goal, req, hypo, fact, open, pref
RELATIONS = ["proves", "kills", "derived_from"]
CONTROL = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|[\x00-\x08\x0b-\x1f\x7f]")
DECISIVE = re.compile(r"error|fail|exception|traceback|assert|panic|fatal|passed|failed|\bok\b|ran \d+|tests?:|"
                      r"\d+ (passed|failed|errors?)|warning|expected|received|status|exit", re.I)
FULL_SUITE = re.compile(r"unittest discover|\bpytest\b(?!\s+\S*test_\w+)|npm (run )?test|yarn test|pnpm test|go test \./\.\.\.|"
                        r"cargo test|mvn test|gradle test|rspec\s*$|dotnet test|make test|tox\b", re.I)


def clean(text, limit=300):
    text = " ".join(CONTROL.sub(" ", str(text)).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def load():
    if not os.path.exists(FILE):
        return {"next": 1, "items": []}
    with open(FILE, "rb") as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except UnicodeDecodeError:
        return json.loads(raw.decode(locale.getpreferredencoding(False)))


def save(d):
    with tempfile.NamedTemporaryFile(dir=os.path.dirname(os.path.abspath(FILE)), delete=False) as f:
        temporary = f.name
    try:
        with open(temporary, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
        os.replace(temporary, FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def find(d, i):
    for it in d["items"]:
        if it["id"] == i:
            return it
    sys.exit(f"no entry {i}")


def ids(text):
    return [int(v) for v in str(text or "").replace(" ", "").split(",") if v.strip().lstrip("-").isdigit()]


def files_arg(values):
    """Accept --files a.py,b.py, --files a.py b.py, or repeated --files flags."""
    parts = values if isinstance(values, list) else [values or ""]
    return [f.strip().replace("\\", "/").lstrip("/") for part in parts for f in str(part).split(",") if f.strip()]


def fingerprint(rel):
    try:
        return hashlib.sha1(Path(rel).read_bytes()).hexdigest()[:12]
    except OSError:
        return None


def trim(d):
    removed = 0
    for kind in DROP_ORDER:
        while len(d["items"]) > CAP:
            cand = [it for it in d["items"] if it["kind"] == kind]
            if not cand:
                break
            d["items"].remove(cand[0])
            removed += 1
    return removed


def add_item(d, kind, text, **extra):
    it = {"id": d["next"], "kind": kind, "text": clean(text, 500), "date": datetime.date.today().isoformat(), **extra}
    d["items"].append(it)
    d["next"] += 1
    n = trim(d)
    if len(d["items"]) > CAP or it not in d["items"]:
        sys.exit("ledger full; merge or remove an entry first")
    return it, n


def link(d, src, rel, dst):
    a, b = find(d, src), find(d, dst)
    a.setdefault("links", [])
    if [rel, b["id"]] not in a["links"]:
        a["links"].append([rel, b["id"]])


def incoming(d, target_id, rel):
    return [it for it in d["items"] if [rel, target_id] in it.get("links", [])]


def passing(fact):
    ev = fact.get("evidence", {})
    return "exit" in ev and ev["exit"] == ev.get("expect", 0)


def stale_files(fact):
    return [f for f, fp in fact.get("evidence", {}).get("fp", {}).items() if fp and fingerprint(f) != fp]


def status(d, it):
    """Proof status of a requirement or hypothesis from the evidence graph."""
    proofs = incoming(d, it["id"], "proves")
    kills = incoming(d, it["id"], "kills")
    if it["kind"] == "hypo" and any(passing(f) or "seen" in f.get("evidence", {}) for f in kills):
        return "killed"
    # A hypothesis is proven by evidence from before the fix, so later edits do not make that evidence stale.
    # A requirement must hold now, so its evidence must be newer than the last change to the files it covers.
    good = [f for f in proofs if passing(f) and (it["kind"] == "hypo" or not stale_files(f))]
    if good:
        return "proven"
    if any("seen" in f.get("evidence", {}) for f in proofs):
        return "observed"
    return "open"


def line(it, d=None):
    kind = it["kind"]
    if kind == "goal":
        return f"{it['id']:>2} [G]  goal     {it['text']}"
    if kind == "fact":
        ev = it.get("evidence", {})
        mark = "[ok]" if passing(it) else ("[~]" if "seen" in ev else "[!!]")
        rels = " ".join(f"{r} #{t}" for r, t in it.get("links", []))
        how = f"exit {ev['exit']}" if "exit" in ev else "observed"
        return f"{it['id']:>2} {mark} fact     {it['text']} ({how}{'; ' + rels if rels else ''})"
    if kind == "hypo":
        st = status(d, it) if d else "open"
        mark = {"proven": "[x]", "killed": "[-]"}.get(st, "[?]")
        return f"{it['id']:>2} {mark}  hypo     {it['text']} ({st})"
    mark = {"req": "[ ]", "open": "[?]"}.get(kind, "   ")
    if kind == "req" and d and status(d, it) == "proven":
        mark = "[x]"
    if it.get("done"):
        mark = "[x]"
    src = f" ({it['src']})" if it.get("src") else ""
    chk = f" -> {it['how']}" if it.get("how") else ""
    return f"{it['id']:>2} {mark} {kind:<8} {it['text']}{src}{chk}"


def summary(d):
    items = d["items"]
    pending = [it for it in items if (it["kind"] in ("open", "req") and not it.get("done")
                                      and not (it["kind"] == "req" and status(d, it) == "proven"))
               or (it["kind"] == "hypo" and status(d, it) == "open")]
    header = f"{len(items)} entries, {len(pending)} pending. Expand with get ID; check with prove."
    print(header)
    if not items:
        return
    width = max(40, min(200, (1600 - len(header) - 1) // len(items) - 1))
    pending_ids = {it["id"] for it in pending}
    shown = 0
    for it in sorted(items, key=lambda it: (it["kind"] != "goal", it["id"] not in pending_ids)):
        row = " ".join(line(it, d).split())
        if shown + len(row) > 1500:
            print(f"... {len(items) - items.index(it)} more; use show")
            break
        print(row if len(row) <= width else row[:width - 3] + "...")
        shown += min(len(row), width) + 1


def run_evidence(command, expect, timeout=600):
    start = time.time()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"}
    try:
        r = subprocess.run(command, shell=True, capture_output=True, timeout=timeout, env=env)
        out = (r.stdout + b"\n" + r.stderr).decode("utf-8", "replace")
        code = r.returncode
    except subprocess.TimeoutExpired:
        out, code = f"timed out after {timeout}s", 124
    lines = [clean(l, 200) for l in out.splitlines() if l.strip()]
    decisive = [l for l in lines if DECISIVE.search(l)][-3:] or lines[-2:]
    return {"cmd": clean(command, 300), "exit": code, "expect": expect, "lines": decisive,
            "secs": round(time.time() - start, 1), "at": datetime.datetime.now().isoformat(timespec="seconds")}


def load_sibling(name, rel):
    path = Path(__file__).resolve().parents[2] / rel
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_prove(d):
    reqs = [it for it in d["items"] if it["kind"] == "req"]
    hypos = [it for it in d["items"] if it["kind"] == "hypo"]
    facts = [it for it in d["items"] if it["kind"] == "fact"]
    out, problems = [], 0
    proven = [r for r in reqs if status(d, r) == "proven"]
    out.append(f"{len(proven)}/{len(reqs)} requirements proven by passing, current evidence.")
    for r in reqs:
        st = status(d, r)
        if st == "proven":
            continue
        problems += 1
        if st == "observed":
            out.append(f"  WEAK     #{r['id']} {r['text'][:90]}: only observed evidence; run a command that shows it")
        elif r.get("done"):
            out.append(f"  NO PROOF #{r['id']} {r['text'][:90]}: marked done without evidence"
                       + (f" ({r['how'][:60]})" if r.get("how") else "") + "; add a fact --run ... --proves " + str(r["id"]))
        else:
            out.append(f"  UNPROVEN #{r['id']} {r['text'][:90]}")
    for h in hypos:
        if status(d, h) == "open":
            out.append(f"  OPEN     hypothesis #{h['id']} {h['text'][:90]}: neither confirmed nor ruled out")
    by_id = {it["id"]: it for it in d["items"]}
    for f in facts:
        # Old failing or stale evidence only matters while nothing current proves the same entry (red -> green is normal).
        targets = [t for rel, t in f.get("links", []) if rel == "proves" and t in by_id and status(d, by_id[t]) != "proven"]
        if targets and "exit" in f.get("evidence", {}) and not passing(f):
            problems += 1
            ev = f["evidence"]
            out.append(f"  FAILING  fact #{f['id']} (exit {ev['exit']}, expected {ev.get('expect', 0)}) is linked as proof of "
                       + ", ".join(f"#{t}" for t in targets))
        stale = stale_files(f)
        req_targets = [t for t in targets if by_id[t]["kind"] == "req"]
        if req_targets and stale:
            problems += 1
            out.append(f"  STALE    fact #{f['id']}: {', '.join(stale[:3])} changed after this evidence; rerun it")
    if not reqs:
        out.append("  no requirements recorded: add req entries for what the task must achieve")
    print("\n".join(out)[:1600])
    return 1 if problems else 0


def cmd_coverage(d, ref):
    graph = load_sibling("lean_graph_ledger", "lean-navigation/scripts/graph.py")
    if graph is None:
        print("coverage needs lean-navigation's graph.py next to task-ledger; skipped.")
        return 0
    base = Path(graph.subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                                     encoding="utf-8").stdout.strip() or ".").resolve()
    g = graph.build(base)
    files = g["files"]
    changed, ranges = graph.git_changes(base, ref)
    code = [c for c in changed if c in files]
    if not code:
        print("No changed code files" + (f" vs {ref}" if ref else "") + "; nothing to cover.")
        return 0
    symbols = [(rel, name, s, e) for rel in code for name, s, e, kind in files[rel]["defs"]
               if any(a <= e and b >= s for a, b in ranges.get(rel, []))]
    callers = sorted({crel for rel, name, s, e in symbols for crel, line in graph.callers_of(files, name.split(".")[-1])
                      if not files[crel]["test"] and not (crel == rel and s <= line <= e)} - set(code))
    rev = graph.importers_map(files)
    affected = set(code) | {i for c in code for i in rev.get(c, [])}
    stems = {Path(c).stem.lower() for c in code if not files[c]["test"]}
    tests = sorted({r for r in affected if files[r]["test"]} |
                   {r for r, i in files.items() if i["test"] and any(s in Path(r).stem.lower() for s in stems)})
    routes = sorted({f"{m} {p}" for r in affected if not files[r]["test"] for m, p, _ in files[r]["routes"]})
    facts = [it for it in d["items"] if it["kind"] == "fact"]
    corpus = " ".join((f.get("evidence", {}).get("cmd", "") + " " + f["text"] + " " + " ".join(f.get("files", []))).lower()
                      for f in facts)
    anchored = {f for it in d["items"] for f in it.get("files", [])}
    full_suite = any(FULL_SUITE.search(f.get("evidence", {}).get("cmd", "")) and passing(f) for f in facts)
    out = [f"Coverage of {len(code)} changed code files" + (f" vs {ref}" if ref else "") + f": {len(symbols)} changed symbols."]
    unrun = [t for t in tests if not full_suite and t.lower() not in corpus and Path(t).stem.lower() not in corpus]
    out.append(f"tests: {len(tests) - len(unrun)}/{len(tests)} run" + (" (full suite ran)" if full_suite else "")
               + (": not run: " + ", ".join(unrun[:6]) if unrun else ""))
    unchecked = [c for c in callers if c not in anchored and c.lower() not in corpus]
    out.append(f"callers: {len(callers) - len(unchecked)}/{len(callers)} checked"
               + (": not looked at: " + ", ".join(unchecked[:6]) if unchecked else ""))
    untried = [r for r in routes if r.split(" ", 1)[1].lower() not in corpus]
    out.append(f"routes: {len(routes) - len(untried)}/{len(routes)} exercised" + (": not exercised: " + ", ".join(untried[:5]) if untried else ""))
    if unrun or unchecked or untried:
        out.append("Record checks with: fact \"...\" --run \"<command>\" --files <paths>  (or explain why a gap is safe).")
    print("\n".join(out)[:1600])
    return 1 if (unrun or unchecked) else 0


def cmd_tree(d):
    """The exploration graph: goal, then each requirement and hypothesis with the evidence linked to it."""
    by_id = {it["id"]: it for it in d["items"]}
    out = []
    goals = [it for it in d["items"] if it["kind"] == "goal"]
    out.append(f"goal #{goals[0]['id']}: {goals[0]['text'][:120]}" if goals else "goal: (none set; use goal TEXT)")
    nodes = [it for it in d["items"] if it["kind"] in ("req", "hypo")]
    for n, node in enumerate(nodes):
        last = n == len(nodes) - 1
        out.append(f"{'`-' if last else '|-'} {node['kind']} #{node['id']} [{status(d, node)}] {node['text'][:100]}")
        evidence = [(rel, f) for rel in ("proves", "kills") for f in incoming(d, node["id"], rel)]
        for k, (rel, f) in enumerate(evidence):
            ev = f.get("evidence", {})
            how = f"`{ev['cmd'][:60]}` exit {ev['exit']}" if "cmd" in ev else "observed"
            flag = "" if passing(f) or "seen" in ev else " FAILING"
            flag += " STALE" if node["kind"] == "req" and stale_files(f) else ""
            out.append(f"{'   ' if last else '|  '}{'`-' if k == len(evidence) - 1 else '|-'} {rel} by fact #{f['id']}{flag}: "
                       f"{f['text'][:60]} ({how})")
    loose = [it for it in d["items"] if it["kind"] == "fact" and not it.get("links")]
    if loose:
        out.append("unlinked facts: " + ", ".join(f"#{f['id']} {f['text'][:40]}" for f in loose[:6]))
    decisions = [it for it in d["items"] if it["kind"] == "decision"]
    if decisions:
        out.append("decisions: " + "; ".join(f"#{x['id']} {x['text'][:60]}" for x in decisions[:6]))
    text = "\n".join(out)
    print(text if len(text) <= 1600 else text[:1580] + "\n[truncated]")


def cmd_close(d):
    mem = load_sibling("lean_memory_ledger", "task-ledger/scripts/memory.py")
    if mem is None:
        print("memory.py not found; nothing promoted.")
        return
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, encoding="utf-8")
    base = Path(top.stdout.strip() or ".").resolve()
    picks = []
    for it in d["items"]:
        if it.get("promoted"):
            continue
        if it["kind"] == "hypo" and status(d, it) == "proven":
            proof = next(f for f in incoming(d, it["id"], "proves") if passing(f))
            picks.append((it, "bug", f"{it['text']} (proven: {proof['text']})"))
        elif it["kind"] == "decision":
            picks.append((it, "decision", it["text"]))
    if not picks:
        print("Nothing new to promote: no proven hypotheses or unpromoted decisions.")
        return
    path = mem.store_path(base)
    with mem.locked(path):
        data = mem.load(path)
        for it, kind, text in picks:
            files = it.get("files", []) or [f for p in incoming(d, it["id"], "proves") for f in p.get("files", [])]
            data["items"].append({"id": data["next"], "kind": kind, "text": mem.clean_text(text),
                                  "date": datetime.date.today().isoformat(), "files": files,
                                  "fp": {f: mem.fingerprint(base, f) for f in files}, "tags": ["ledger"], "links": []})
            data["next"] += 1
            it["promoted"] = True
        mem.save(path, data)
    save(d)
    print(f"Promoted {len(picks)} to project memory: " + "; ".join(f"{k}: {t[:60]}" for _, k, t in picks)[:1400])


for _stream in (sys.stdout, sys.stderr):  # never crash on non-ASCII output (Windows consoles default to cp1252)
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("goal").add_argument("text")
    a = sub.add_parser("add")
    a.add_argument("kind", choices=KINDS)
    a.add_argument("text", nargs="+")
    a.add_argument("--src", choices=["user", "inferred"])
    a.add_argument("--replace", type=int)
    a.add_argument("--files", nargs="*", action="extend", default=[])
    h = sub.add_parser("hypo")
    h.add_argument("text")
    h.add_argument("--files", nargs="*", action="extend", default=[])
    f = sub.add_parser("fact")
    f.add_argument("text")
    src = f.add_mutually_exclusive_group(required=True)
    src.add_argument("--run", help="command to run now; its exit code and decisive lines become the evidence")
    src.add_argument("--seen", help="evidence observed without a command (weaker)")
    f.add_argument("--expect-exit", type=int, default=0)
    f.add_argument("--proves", default="")
    f.add_argument("--kills", default="")
    f.add_argument("--files", nargs="*", action="extend", default=[])
    f.add_argument("--timeout", type=int, default=600)
    lk = sub.add_parser("link")
    lk.add_argument("a", type=int)
    lk.add_argument("rel", choices=RELATIONS)
    lk.add_argument("b", type=int)
    sub.add_parser("prove")
    sub.add_parser("tree")
    cv = sub.add_parser("coverage")
    cv.add_argument("--base")
    sub.add_parser("close")
    v = sub.add_parser("verify")
    v.add_argument("id", type=int)
    v.add_argument("how")
    sub.add_parser("done").add_argument("id", type=int)
    sub.add_parser("rm").add_argument("id", type=int)
    s = sub.add_parser("show")
    s.add_argument("--open", action="store_true")
    sub.add_parser("summary")
    sub.add_parser("get").add_argument("id", type=int)
    sub.add_parser("export")
    sub.add_parser("trim")
    x = p.parse_args()
    d = load()

    if x.cmd == "init":
        if not os.path.exists(FILE):
            save(d)
        print(f"ledger ready: {os.path.abspath(FILE)}")
    elif x.cmd == "goal":
        old = [it for it in d["items"] if it["kind"] == "goal"]
        for it in old:
            d["items"].remove(it)
        it, _ = add_item(d, "goal", x.text)
        save(d)
        print(f"goal #{it['id']} set" + (" (replaced the previous goal)" if old else ""))
    elif x.cmd == "add":
        if x.replace:
            d["items"].remove(find(d, x.replace))
        extra = {"src": x.src} if x.src else {}
        if x.files:
            extra["files"] = files_arg(x.files)
        added, n = [], 0
        for text in x.text:  # several requirements in one call: add req "a" "b" "c"
            it, k = add_item(d, x.kind, text, **extra)
            added.append(it["id"])
            n += k
        save(d)
        print(("added " + ", ".join(f"#{i}" for i in added) if len(added) > 1 else f"added {added[0]}")
              + (f" (trimmed {n})" if n else ""))
    elif x.cmd == "hypo":
        it, _ = add_item(d, "hypo", x.text, files=files_arg(x.files))
        save(d)
        print(f"hypothesis #{it['id']}: confirm with fact ... --proves {it['id']} or rule out with --kills {it['id']}")
    elif x.cmd == "fact":
        proves = ([it["id"] for it in d["items"] if it["kind"] == "req"] if x.proves.strip().lower() == "all"
                  else ids(x.proves))  # --proves all: one full-suite run proves every requirement
        targets = [(rel, t) for rel, lst in (("proves", proves), ("kills", ids(x.kills))) for t in lst]
        for _, t in targets:
            find(d, t)
        files = files_arg(x.files)
        if x.run:
            ev = run_evidence(x.run, x.expect_exit, x.timeout)
        else:
            ev = {"seen": clean(x.seen, 300), "at": datetime.datetime.now().isoformat(timespec="seconds")}
        ev["fp"] = {f: fingerprint(f) for f in files}
        it, _ = add_item(d, "fact", x.text, evidence=ev, files=files)
        for rel, t in targets:
            link(d, it["id"], rel, t)
        save(d)
        if x.run:
            verdict = "PASS" if passing(it) else "FAIL"
            print(f"fact #{it['id']} {verdict}: `{ev['cmd'][:80]}` exit {ev['exit']} (expected {ev['expect']}) in {ev['secs']}s")
            for l in ev["lines"]:
                print("  " + l)
            if targets and not passing(it):
                print("  note: this failing evidence does not prove " + ", ".join(f"#{t}" for _, t in targets))
        else:
            print(f"fact #{it['id']} recorded as observed (weaker than a command)")
    elif x.cmd == "link":
        link(d, x.a, x.rel, x.b)
        save(d)
        print(f"#{x.a} {x.rel} #{x.b}")
    elif x.cmd == "prove":
        sys.exit(cmd_prove(d))
    elif x.cmd == "tree":
        cmd_tree(d)
    elif x.cmd == "coverage":
        sys.exit(cmd_coverage(d, x.base))
    elif x.cmd == "close":
        cmd_close(d)
    elif x.cmd == "verify":
        it = find(d, x.id)
        it["how"] = x.how
        it["done"] = True
        if it["kind"] == "open":
            it["kind"] = "verified"
        save(d)
        print(f"verified {x.id}")
    elif x.cmd == "done":
        find(d, x.id)["done"] = True
        save(d)
        print(f"done {x.id}")
    elif x.cmd == "rm":
        target = find(d, x.id)
        d["items"].remove(target)
        for it in d["items"]:
            it["links"] = [l for l in it.get("links", []) if l[1] != x.id]
        save(d)
        print(f"removed {x.id}")
    elif x.cmd == "summary":
        summary(d)
    elif x.cmd == "get":
        it = find(d, x.id)
        print(line(it, d))
        ev = it.get("evidence")
        if ev:
            print("  evidence: " + (f"`{ev.get('cmd', '')}` exit {ev.get('exit')} at {ev.get('at')}" if "cmd" in ev
                                    else f"observed: {ev.get('seen')}"))
            for l in ev.get("lines", []):
                print("    " + l)
    elif x.cmd == "show":
        items = d["items"]
        if x.open:
            items = [i for i in items if (i["kind"] in ("open", "req") and not i.get("done")) or
                     (i["kind"] == "hypo" and status(d, i) == "open")]
        print(f"{len(d['items'])}/{CAP} entries")
        for it in items:
            print(line(it, d))
        pending = [i for i in d["items"] if i["kind"] in ("req", "open") and not i.get("done")]
        if pending:
            print(f"\nPENDING: {len(pending)} (req/open not done)")
    elif x.cmd == "export":
        out = os.path.join(os.path.dirname(os.path.abspath(FILE)), "ledger-export.md")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(f"# Ledger export {datetime.date.today()}\n\n")
            for it in d["items"]:
                fh.write("- " + line(it, d).strip() + "\n")
                for l in it.get("evidence", {}).get("lines", []):
                    fh.write(f"  - `{l}`\n")
        print(f"wrote {out}; save it and upload next time")
    elif x.cmd == "trim":
        n = trim(d)
        save(d)
        print(f"trimmed {n}; {len(d['items'])} left")


if __name__ == "__main__":
    main()
