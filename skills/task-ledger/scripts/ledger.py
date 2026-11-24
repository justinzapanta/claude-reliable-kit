#!/usr/bin/env python3
"""Tiny task ledger. Commands: init | add KIND TEXT [--src user|inferred] [--replace ID] | verify ID HOW | done ID | rm ID | show [--open] | export | trim
Stores ledger.json in the current directory (override with LEDGER_FILE)."""
import argparse, datetime, json, locale, os, sys, tempfile
FILE = os.environ.get("LEDGER_FILE", "ledger.json")
KINDS = ["req", "decision", "loc", "verified", "open", "pref"]
CAP = 30
DROP_ORDER = ["verified", "loc", "decision"]  # never drops open, pref, req

def load():
    if not os.path.exists(FILE): return {"next": 1, "items": []}
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
        if it["id"] == i: return it
    sys.exit(f"no entry {i}")

def trim(d):
    removed = 0
    for kind in DROP_ORDER:
        while len(d["items"]) > CAP:
            cand = [it for it in d["items"] if it["kind"] == kind]
            if not cand: break
            d["items"].remove(cand[0]); removed += 1
    return removed

def line(it):
    mark = {"req": "[ ]", "open": "[?]"}.get(it["kind"], "   ")
    if it.get("done"): mark = "[x]"
    src = f" ({it['src']})" if it.get("src") else ""
    chk = f" -> {it['how']}" if it.get("how") else ""
    return f"{it['id']:>2} {mark} {it['kind']:<8} {it['text']}{src}{chk}"

def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    a = sub.add_parser("add"); a.add_argument("kind", choices=KINDS); a.add_argument("text")
    a.add_argument("--src", choices=["user", "inferred"]); a.add_argument("--replace", type=int)
    v = sub.add_parser("verify"); v.add_argument("id", type=int); v.add_argument("how")
    dn = sub.add_parser("done"); dn.add_argument("id", type=int)
    r = sub.add_parser("rm"); r.add_argument("id", type=int)
    s = sub.add_parser("show"); s.add_argument("--open", action="store_true")
    sub.add_parser("export"); sub.add_parser("trim")
    x = p.parse_args(); d = load()

    if x.cmd == "init":
        if not os.path.exists(FILE): save(d)
        print("ledger ready")
    elif x.cmd == "add":
        if x.replace: d["items"].remove(find(d, x.replace))
        it = {"id": d["next"], "kind": x.kind, "text": x.text, "date": datetime.date.today().isoformat()}
        if x.src: it["src"] = x.src
        d["items"].append(it); d["next"] += 1
        n = trim(d)
        if len(d["items"]) > CAP or it not in d["items"]:
            sys.exit("ledger full; merge or remove an entry first")
        save(d)
        print(f"added {it['id']}" + (f" (trimmed {n})" if n else ""))
    elif x.cmd == "verify":
        it = find(d, x.id); it["how"] = x.how; it["done"] = True
        if it["kind"] == "open": it["kind"] = "verified"
        save(d); print(f"verified {x.id}")
    elif x.cmd == "done":
        find(d, x.id)["done"] = True; save(d); print(f"done {x.id}")
    elif x.cmd == "rm":
        d["items"].remove(find(d, x.id)); save(d); print(f"removed {x.id}")
    elif x.cmd == "show":
        items = d["items"]
        if x.open: items = [i for i in items if i["kind"] in ("open", "req") and not i.get("done")]
        print(f"{len(d['items'])}/{CAP} entries")
        for it in items: print(line(it))
        pending = [i for i in d["items"] if i["kind"] in ("req", "open") and not i.get("done")]
        if pending: print(f"\nPENDING: {len(pending)} (req/open not done)")
    elif x.cmd == "export":
        out = "ledger-export.md"
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"# Ledger export {datetime.date.today()}\n\n")
            for it in d["items"]: f.write("- " + line(it).strip() + "\n")
        print(f"wrote {out}; save it and upload next time")
    elif x.cmd == "trim":
        n = trim(d); save(d); print(f"trimmed {n}; {len(d['items'])} left")

if __name__ == "__main__":
    main()
