#!/usr/bin/env python3
"""Project memory graph: decisions, bugs, gotchas, and concepts linked to files and to each other. Stdlib only.

Commands (all take --dir PROJECT, default "."):
  add KIND "TEXT" [--files a.py,src/b.ts] [--tags t1,t2] [--link ID,ID] [--src user|inferred]
        KIND: decision | bug | gotcha | concept | pref | todo
  recall [QUERY] [--file PATH] [--changed]
        Ranked memories for words, a file, or every file in your uncommitted Git changes. Also shows
        memories on neighbouring files (imports and importers) when lean-navigation's code graph exists.
  show ID          one memory with its links
  link A B         connect two memories
  done ID          mark a todo or bug resolved (kept, ranked lower)
  forget ID        delete a memory
  list [--kind K]  compact listing
  stale            memories whose linked files changed or vanished since they were recorded

Stored in .git/lean-memory.json inside a Git work tree (private, never committed), else .lean-memory.json.
Set LEAN_MEMORY_FILE to choose another path, for example a committed file to share memories with a team.
"""
import argparse
import atexit
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

KINDS = ["decision", "bug", "gotcha", "concept", "pref", "todo"]
WEIGHT = {"gotcha": 3, "bug": 3, "decision": 2, "pref": 2, "concept": 1, "todo": 1}
CAP = 300
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
STOP = {"the", "and", "for", "with", "that", "this", "from", "not", "are", "was", "but", "use", "when", "into", "have", "has"}


def git(base, *args):
    try:
        r = subprocess.run(["git", "-C", str(base), "-c", "core.quotePath=false", *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def store_path(base):
    if os.environ.get("LEAN_MEMORY_FILE"):
        return Path(os.environ["LEAN_MEMORY_FILE"])
    gd = git(base, "rev-parse", "--absolute-git-dir")
    return Path(gd.strip()) / "lean-memory.json" if gd and gd.strip() else base / ".lean-memory.json"


class MemoryError_(Exception):
    """The memory file cannot be used; the message says what to do."""


def load(path):
    if not path.exists():
        return {"next": 1, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("unexpected structure")
        data.setdefault("next", max([i.get("id", 0) for i in data["items"]] + [0]) + 1)
        return data
    except (ValueError, OSError) as exc:
        raise MemoryError_(f"{path} is damaged ({exc.__class__.__name__}). Nothing was changed. Restore it from "
                           f"{path.name}.bak if present, or move it aside to start a new memory.")


class locked:
    """Exclusive lock around read-modify-write so parallel `add` calls never lose memories or reuse ids."""

    def __init__(self, path):
        self.lock = path.with_name(path.name + ".lock")

    def __enter__(self):
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + 10
        while True:
            try:
                os.close(os.open(str(self.lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.lock.stat().st_mtime > 30:  # left behind by a crashed process
                        self.lock.unlink()
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise MemoryError_(f"memory is locked by another process ({self.lock}); try again")
                time.sleep(0.05)

    def __exit__(self, *exc):
        try:
            self.lock.unlink()
        except OSError:
            pass


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    try:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    except OSError:
        pass


def norm(base, p):
    p = p.strip().replace("\\", "/")
    try:
        q = Path(p)
        if q.is_absolute():
            p = q.resolve().relative_to(base).as_posix()
    except ValueError:
        pass
    while p.startswith("./"):
        p = p[2:]
    return p


def fingerprint(base, rel):
    f = base / rel
    if not f.is_file():
        return None
    try:
        return hashlib.sha1(f.read_bytes()).hexdigest()[:12]
    except OSError:
        return None


def words(text):
    return {w.lower() for w in WORD.findall(text) if w.lower() not in STOP}


ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b.")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩]")
MAX_TEXT = 300
# Comments and commit messages are written by anyone; text that addresses an AI assistant is a likely injection.
ADDRESSES_AI = re.compile(r"ignore (all |any )?(previous|prior|above) (instructions|rules)|\b(ai|llm) (assistant|agent|model)\b|"
                          r"\byou are now\b|\bsystem\s*:|\bassistant\s*:|disable (all |the )?hooks|\brm -rf\b|"
                          r"\bcurl\b[^\n]*\|\s*(sh|bash)\b|do not tell the user|without (asking|telling)", re.I)


def clean_text(text, limit=MAX_TEXT):
    """Memory text is shown to Claude: drop terminal escapes and invisible characters, collapse whitespace, cap length."""
    text = CONTROL.sub(" ", ANSI.sub("", str(text)))
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def find(data, i):
    for it in data["items"]:
        if it["id"] == i:
            return it
    sys.exit(f"no memory {i}")


def graph_neighbors(base, files):
    """Files one import-hop away, read from lean-navigation's cache if it exists."""
    gd = git(base, "rev-parse", "--absolute-git-dir")
    cache = (Path(gd.strip()) / "lean-graph.json") if gd and gd.strip() else base / ".lean-graph.json"
    try:
        g = json.loads(cache.read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError):
        return set(), False
    near = set()
    for rel, info in g.items():
        imports = set(info.get("imports", []))
        if rel in files:
            near |= imports
        if imports & files:
            near.add(rel)
    return near - files, True


def line(it, mark=""):
    status = " [done]" if it.get("done") else ""
    files = f"  files: {', '.join(it['files'][:4])}" + (" ..." if len(it["files"]) > 4 else "") if it.get("files") else ""
    links = f"  links: {', '.join('#' + str(x) for x in it['links'])}" if it.get("links") else ""
    src = " (inferred, unverified)" if it.get("src") == "inferred" else ""
    return f"#{it['id']} {it['kind']}{status}{src}{mark}: {clean_text(it['text'])}{files}{links}"


def score(it, q, files, near, today):
    s = 0.0
    if q:
        text_words = words(it["text"] + " " + " ".join(it.get("tags", [])) + " " + " ".join(it.get("files", [])))
        hit = len(q & text_words)
        if not hit:
            return 0, ""
        s += 3 * hit
    reason = ""
    item_files = set(it.get("files", []))
    if files:
        direct = item_files & files
        same_dir = {f for f in item_files for g in files if PurePosixPath(f).parent == PurePosixPath(g).parent} - direct
        nearby = item_files & near
        if direct:
            s += 6
        elif nearby:
            s += 3
            reason = " (nearby file)"
        elif same_dir:
            s += 1.5
            reason = " (same folder)"
        elif not q:
            return 0, ""
    s += WEIGHT.get(it["kind"], 1)
    if it.get("done"):
        s -= 2
    try:
        age = (today - datetime.date.fromisoformat(it["date"])).days
        s -= min(age / 90, 2)
    except (KeyError, ValueError):
        pass
    return s, reason


FIX_WORDS = re.compile(r"\b(fix(e[sd])?|bug|hotfix|revert(s|ed)?|regression|security|crash(es|ed)?|broke(n)?|incident)\b", re.I)
NOTE = re.compile(r"(?:#|//|/\*|<!--|\*|--)\s*(NOTE|IMPORTANT|WARNING|WARN|HACK|FIXME|XXX|SECURITY|DO NOT|DON'T|NEVER)\b[:!\s-]*(.{12,220})")
SEED_NOISE = re.compile(r"pre-commit|dependabot|renovate|\bbump\b|\blint|\btypos?\b|\bformat(ting)?\b|\bstyle\b|type ?hints?|"
                        r"\btyping\b|\bmypy\b|\bdocs?\b|\bchangelog\b|\bci\b|auto ?fix|whitespace|spelling|\breadme\b", re.I)
SEED_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".rs", ".java", ".kt", ".rb",
            ".php", ".cs", ".swift", ".sql", ".sh", ".yml", ".yaml", ".toml"}


def seed_candidates(base, commits):
    """Memories implied by the repo itself: fix/revert commits (bug) and warning comments (gotcha)."""
    found = []
    log = git(base, "log", "--no-merges", f"-n{commits}", "--name-only", "--date=short", "--pretty=format:%x1e%h|%ad|%s")
    if log:
        for block in log.split("\x1e")[1:]:
            block = block.strip()
            if not block:
                continue
            head, *names = block.splitlines()
            short, date, subject = (head.split("|", 2) + ["", ""])[:3]
            files = [n for n in names if n and PurePosixPath(n).suffix.lower() in SEED_EXT][:6]
            if files and FIX_WORDS.search(subject) and not SEED_NOISE.search(subject) and not ADDRESSES_AI.search(subject):
                found.append(("bug", clean_text(f"{subject.strip()} (commit {short}, {date})"), files, ["seeded", "git"]))
    listing = git(base, "ls-files")
    for rel in (listing or "").splitlines():
        p = base / rel
        if PurePosixPath(rel).suffix.lower() not in SEED_EXT or not p.is_file():
            continue
        try:
            if p.stat().st_size > 500_000:
                continue
            lines = p.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i, text in enumerate(lines, 1):
            m = NOTE.search(text)
            if m and "noqa" not in text and "pragma" not in text and not ADDRESSES_AI.search(text):
                note = clean_text(m.group(2).strip().rstrip("*/->").strip(), 200)
                found.append(("gotcha", f"{m.group(1).upper()}: {note} ({rel}:{i})", [rel], ["seeded", "code-note"]))
    return found


def changed_files(base):
    """Changed and untracked files, relative to BASE (which may be a subfolder of the repository)."""
    out = git(base, "status", "--porcelain", "-z", "--untracked-files=all")
    top = git(base, "rev-parse", "--show-toplevel")
    if out is None or not top:
        raise MemoryError_("not a Git work tree; pass --file instead of --changed")
    root = Path(top.strip()).resolve()
    names, parts, i = set(), out.split("\0"), 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            i += 1  # the original path of a rename/copy follows; we want the new one
        try:
            names.add((root / path).resolve().relative_to(base).as_posix())
        except ValueError:
            continue  # outside the --dir subfolder
    return names


for _stream in (sys.stdout, sys.stderr):  # never crash on non-ASCII output (Windows consoles default to cp1252)
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("kind", choices=KINDS)
    a.add_argument("text")
    a.add_argument("--files", nargs="*", action="extend", default=[], help="comma- or space-separated; repeatable")
    a.add_argument("--tags", default="")
    a.add_argument("--link", default="")
    a.add_argument("--src", choices=["user", "inferred"])
    r = sub.add_parser("recall")
    r.add_argument("query", nargs="*")
    r.add_argument("--file", action="append", default=[])
    r.add_argument("--changed", action="store_true")
    r.add_argument("--limit", type=int, default=8)
    sub.add_parser("show").add_argument("id", type=int)
    lk = sub.add_parser("link")
    lk.add_argument("a", type=int)
    lk.add_argument("b", type=int)
    sub.add_parser("done").add_argument("id", type=int)
    sub.add_parser("forget").add_argument("id", type=int)
    ls = sub.add_parser("list")
    ls.add_argument("--kind", choices=KINDS)
    sub.add_parser("stale")
    sd = sub.add_parser("seed", help="bootstrap memories from git fix commits and code warning comments")
    sd.add_argument("--commits", type=int, default=300, help="how many recent commits to scan")
    sd.add_argument("--limit", type=int, default=60, help="maximum memories to add in one run")
    sd.add_argument("--dry-run", action="store_true", help="show what would be added without saving")
    for sp in sub.choices.values():
        sp.add_argument("--dir", default=".")
        sp.add_argument("--max-chars", type=int, default=1600)
    x = p.parse_args()
    base = Path(x.dir).resolve()
    path = store_path(base)
    if x.cmd in ("add", "link", "done", "forget", "seed"):  # writers hold the lock from read to write
        lock = locked(path).__enter__()
        atexit.register(lock.__exit__)
    data = load(path)
    out = []

    if x.cmd == "add":
        if re.search(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S{8,}", x.text):
            sys.exit("refusing to store what looks like a secret value; record the setting's name instead")
        files = [norm(base, f) for part in x.files for f in part.split(",") if f.strip()]
        links = [int(v) for v in x.link.split(",") if v.strip()]
        for lid in links:
            find(data, lid)
        it = {"id": data["next"], "kind": x.kind, "text": clean_text(x.text), "date": datetime.date.today().isoformat(),
              "files": files, "fp": {f: fingerprint(base, f) for f in files},
              "tags": [t.strip().lower() for t in x.tags.split(",") if t.strip()], "links": links}
        if x.src:
            it["src"] = x.src
        for lid in links:
            other = find(data, lid)
            other.setdefault("links", [])
            if it["id"] not in other["links"]:
                other["links"].append(it["id"])
        data["items"].append(it)
        data["next"] += 1
        dropped = 0
        while len(data["items"]) > CAP:
            victims = [i for i in data["items"] if i.get("done") or i["kind"] in ("todo", "concept")] or data["items"]
            data["items"].remove(victims[0])
            dropped += 1
        save(path, data)
        out.append(f"added #{it['id']} {it['kind']}" + (f"; pruned {dropped} oldest" if dropped else "") + f" ({path})")
        missing = [f for f in files if it["fp"][f] is None]
        if missing:
            out.append("note: not found on disk: " + ", ".join(missing))

    elif x.cmd == "recall":
        raw_query = " ".join(x.query).strip().lower()
        q = words(raw_query)
        if raw_query and not q:  # only short or common words ("db", "api"): match them as plain text
            data = {**data, "items": [it for it in data["items"] if raw_query in
                                      (it["text"] + " " + " ".join(it.get("tags", []) + it.get("files", []))).lower()]}
            if not data["items"]:
                print(f"No memories mention '{raw_query}'.")
                return
        files = {norm(base, f) for f in x.file}
        if x.changed:
            files |= changed_files(base)
        near, has_graph = graph_neighbors(base, files) if files else (set(), False)
        today = datetime.date.today()
        ranked = []
        for it in data["items"]:
            s, why = score(it, q, files, near, today)
            if s > 0:
                ranked.append((s, it, why))
        ranked.sort(key=lambda t: (-t[0], -t[1]["id"]))
        if any(not why for _, _, why in ranked) and files:
            # exact-file or query matches exist: drop weaker same-folder matches, keep import neighbours
            ranked = [r for r in ranked if r[2] != " (same folder)"]
        scope = (f"{len(files)} files" if files else "") + (" + " if files and q else "") + (f"'{' '.join(x.query)}'" if q else "")
        if not ranked:
            out.append(f"No memories for {scope or 'that query'}." + ("" if data["items"] else " The memory is empty."))
        else:
            out.append(f"{len(ranked)} memories for {scope}" + (", ranked; nearby files from the code graph" if has_graph else ", ranked") + ".")
            shown = {it["id"] for _, it, _ in ranked[: x.limit]}
            for _, it, why in ranked[: x.limit]:
                out.append(line(it, why))
            linked = sorted({l for _, it, _ in ranked[: x.limit] for l in it.get("links", [])} - shown)
            for lid in linked[:4]:
                try:
                    out.append("  linked " + line(find(data, lid)))
                except SystemExit:
                    pass
            if len(ranked) > x.limit:
                out.append(f"({len(ranked) - x.limit} more; narrow the query or raise --limit)")

    elif x.cmd == "show":
        it = find(data, x.id)
        out.append(line(it))
        if it.get("tags"):
            out.append("tags: " + ", ".join(it["tags"]))
        out.append(f"recorded {it.get('date', '?')}")
        for lid in it.get("links", []):
            try:
                out.append("  -> " + line(find(data, lid)))
            except SystemExit:
                out.append(f"  -> #{lid} (forgotten)")

    elif x.cmd == "link":
        a_, b_ = find(data, x.a), find(data, x.b)
        for one, two in ((a_, b_), (b_, a_)):
            one.setdefault("links", [])
            if two["id"] not in one["links"]:
                one["links"].append(two["id"])
        save(path, data)
        out.append(f"linked #{x.a} <-> #{x.b}")

    elif x.cmd == "done":
        find(data, x.id)["done"] = True
        save(path, data)
        out.append(f"#{x.id} marked done")

    elif x.cmd == "forget":
        it = find(data, x.id)
        data["items"].remove(it)
        for other in data["items"]:
            if x.id in other.get("links", []):
                other["links"].remove(x.id)
        save(path, data)
        out.append(f"forgot #{x.id}")

    elif x.cmd == "list":
        items = [i for i in data["items"] if not x.kind or i["kind"] == x.kind]
        out.append(f"{len(items)} memories" + (f" of kind {x.kind}" if x.kind else "") + f" (cap {CAP}).")
        for it in sorted(items, key=lambda i: (i.get("done", False), -i["id"])):
            out.append(line(it))

    elif x.cmd == "stale":
        rows = []
        for it in data["items"]:
            for f, fp in it.get("fp", {}).items():
                now = fingerprint(base, f)
                if fp and now != fp:
                    rows.append(f"#{it['id']} {it['kind']}: {f} " + ("was deleted or moved" if now is None else "changed since recorded")
                                + f" -> {it['text'][:70]}")
        out.append(f"{len(rows)} possibly stale links." + (" Re-check each; update with forget + add, or keep if still true." if rows else ""))
        out += rows

    elif x.cmd == "seed":
        found = seed_candidates(base, x.commits)
        existing = {(it["text"], tuple(it.get("files", []))) for it in data["items"]}
        fresh = [c for c in found if (c[1], tuple(c[2])) not in existing][: x.limit]
        if not x.dry_run:
            for kind, text, files, tags in fresh:
                data["items"].append({"id": data["next"], "kind": kind, "text": text, "date": datetime.date.today().isoformat(),
                                      "files": files, "fp": {f: fingerprint(base, f) for f in files}, "tags": tags,
                                      "links": [], "src": "inferred"})
                data["next"] += 1
            while len(data["items"]) > CAP:
                victims = [i for i in data["items"] if "seeded" in i.get("tags", [])] or data["items"]
                data["items"].remove(victims[0])
            if fresh:
                save(path, data)
        bugs = sum(1 for c in fresh if c[0] == "bug")
        out.append(f"{'Would add' if x.dry_run else 'Added'} {len(fresh)} seeded memories ({bugs} from fix commits, "
                   f"{len(fresh) - bugs} from code warnings); {len(found) - len(fresh)} already known or over --limit. "
                   "Seeded memories are marked inferred: confirm or forget them as you meet them.")
        for kind, text, files, _ in fresh[:8]:
            out.append(f"  {kind}: {text[:110]}  ({', '.join(files[:2])})")

    text = "\n".join(out)
    if len(text) > x.max_chars:
        text = text[: x.max_chars - 60].rsplit("\n", 1)[0] + "\n[truncated: narrow the query or raise --max-chars]"
    print(text)


if __name__ == "__main__":
    try:
        main()
    except MemoryError_ as exc:
        sys.exit(str(exc))
