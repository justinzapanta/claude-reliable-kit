#!/usr/bin/env python3
"""Run a command and print a compact version of its output. Stdlib only.

Usage: squeeze.py [--max-chars 2000] [--timeout 600] [--shell] -- COMMAND [ARGS...]

Keeps what decides the next step (failures, errors, tracebacks, warnings, summary lines, the end of the
output), drops noise (ANSI colors, progress bars, repeated lines, passing-test chatter, diff context), and
exits with the command's own exit code. The full output is saved to a file named in the last line, so
nothing is lost: read it only if the compact view is not enough.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
IMPORTANT = re.compile(
    r"error|fail|exception|traceback|panic|fatal|assert|expected|received|warning|warn\b|denied|"
    r"not found|cannot|can't|undefined|refused|timed? ?out|segmentation|✗|✘|×|\bE\s{2,}|^E\s|^>\s", re.I)
SUMMARY = re.compile(
    r"\b(\d+ (passed|failed|errors?|skipped|tests?|warnings?|deselected|xfailed|xpassed|pending|todo))\b|"
    r"^(OK|FAILED|PASS|FAIL|ok|FAIL:|ERROR:)\b|^Ran \d+ tests?|Tests?:\s|Test Suites?:|test result:|"
    r"^\s*(BUILD|Build) (SUCCESS|FAILED|succeeded|failed)|compiled|webpack \d|^Done in", re.I)
NOISE = re.compile(r"^\s*(PASSED|PASS|ok|✓|✔|√)\b|\bPASSED\b\s*(\[\s*\d+%\])?\s*$|^\s*\.+\s*(\[\s*\d+%\])?\s*$|"
                   r"^\s*(Downloading|Downloaded|Fetching|Resolving|Compiling|Checking|Collecting|Installing)\b|"
                   r"^\s*[#=>\-\s]*\d{1,3}%|^\s*\[[#=\->\s.]+\]", re.I)
DIGITS = re.compile(r"\d+")


def is_noise(line):
    return bool(NOISE.search(line)) and not SUMMARY.search(line) and not IMPORTANT.search(line)


def clean(text):
    lines = []
    for raw in ANSI.sub("", text).replace("\r\n", "\n").split("\n"):
        line = raw.rsplit("\r", 1)[-1].rstrip()
        lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    out, prev_shape, run = [], None, 0
    for line in lines:
        shape = DIGITS.sub("#", line)
        if shape == prev_shape and line.strip() and not IMPORTANT.search(line):
            run += 1
            continue
        if run:
            out.append(f"  ... ({run} similar lines)")
            run = 0
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line)
        prev_shape = shape
    if run:
        out.append(f"  ... ({run} similar lines)")
    return out


def squeeze_diff(lines):
    out, ctx = [], 0
    for line in lines:
        if line.startswith(("diff --git", "+++", "---", "@@", "+", "-", "Binary files", "rename ", "new file", "deleted file")):
            out.append(line)
            ctx = 0
        elif line.startswith(" ") and ctx < 1:
            out.append(line)
            ctx += 1
    return out


def squeeze_git_status(lines):
    staged, unstaged, untracked, branch = [], [], [], ""
    section = None
    for line in lines:
        s = line.strip()
        if s.startswith("On branch") or s.startswith("HEAD detached") or "Your branch" in s:
            branch += (" " if branch else "") + s
        elif s.startswith("Changes to be committed"):
            section = staged
        elif s.startswith("Changes not staged"):
            section = unstaged
        elif s.startswith("Untracked files"):
            section = untracked
        elif s.startswith(("no changes added", "nothing added", "nothing to commit")):
            section = None
        elif section is not None and s and not s.startswith("("):
            section.append(s)
    if not (staged or unstaged or untracked):
        return [branch or "clean", "nothing to commit"] if "nothing to commit" in "\n".join(lines) else lines
    out = [branch] if branch else []
    for name, items in (("staged", staged), ("unstaged", unstaged), ("untracked", untracked)):
        if items:
            out.append(f"{name} ({len(items)}): " + ", ".join(i.replace("modified:", "M").replace("new file:", "A")
                                                         .replace("deleted:", "D").replace("renamed:", "R").replace("  ", " ")
                                                         for i in items[:25]) + (" ..." if len(items) > 25 else ""))
    return out


def select(lines, budget):
    """Keep head, important lines with context, summary lines, and the tail, within budget."""
    if sum(len(l) + 1 for l in lines) <= budget:
        return [l for l in lines if not is_noise(l)] or lines
    keep = set(range(min(5, len(lines))))
    tail = 15
    keep.update(range(max(0, len(lines) - tail), len(lines)))
    for i, line in enumerate(lines):
        if is_noise(line):
            continue
        if SUMMARY.search(line):
            keep.add(i)
        if IMPORTANT.search(line):
            keep.update(range(max(0, i - 2), min(len(lines), i + 4)))
    out, last = [], -1
    for i in sorted(keep):
        if i > last + 1:
            out.append(f"  ... ({i - last - 1} lines omitted)")
        out.append(lines[i])
        last = i
    if last < len(lines) - 1:
        out.append(f"  ... ({len(lines) - last - 1} lines omitted)")
    text = "\n".join(out)
    if len(text) > budget:
        head = text[: budget // 3]
        tail_text = text[-(budget - len(head) - 40):]
        text = head + "\n  ... (middle cut to fit budget) ...\n" + tail_text
        out = text.split("\n")
    return out


def kind_of(cmd):
    words = [Path(c).name.lower() for c in cmd[:2]]
    if words == ["git", "status"] and len(cmd) == 2:
        return "git-status"
    if words[:1] == ["git"] and len(cmd) > 1 and cmd[1] in ("diff", "show"):
        return "diff"
    return "generic"


def kill_tree(proc):
    """Stop the command and everything it started (shells, npm .cmd wrappers, test workers)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=15)
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def _state_dir():
    try:
        r = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path(tempfile.gettempdir())


def record_gain(raw_chars, compact_chars):
    """Keep running totals in .git/lean-squeeze-stats.json (never committed)."""
    path = _state_dir() / "lean-squeeze-stats.json"
    try:
        stats = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        stats = {}
    stats["runs"] = stats.get("runs", 0) + 1
    stats["raw_chars"] = stats.get("raw_chars", 0) + raw_chars
    stats["compact_chars"] = stats.get("compact_chars", 0) + compact_chars
    try:
        path.write_text(json.dumps(stats), encoding="utf-8")
    except OSError:
        pass


def show_gain():
    path = _state_dir() / "lean-squeeze-stats.json"
    try:
        stats = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("[squeeze] no runs recorded in this repository yet.")
        return
    raw, compact, runs = stats.get("raw_chars", 0), stats.get("compact_chars", 0), stats.get("runs", 0)
    saved = raw - compact
    pct = f" ({saved * 100 / raw:.1f}%)" if raw else ""
    print(f"[squeeze] {runs} runs: {raw:,} -> {compact:,} chars; saved {saved:,} chars{pct}, "
          f"about {saved // 4:,} tokens (estimate: 4 characters per token).")


def save_full(text):
    try:
        r = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        folder = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else Path(tempfile.gettempdir())
    except (OSError, subprocess.SubprocessError):
        folder = Path(tempfile.gettempdir())
    path = folder / "lean-last-output.txt"
    try:
        path.write_text(text, encoding="utf-8")
        return str(path)
    except OSError:
        return None


for _stream in (sys.stdout, sys.stderr):  # never crash on non-ASCII output (Windows consoles default to cp1252)
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max-chars", type=int, default=2000)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--shell", action="store_true", help="run COMMAND as one shell string (pipes, &&)")
    p.add_argument("--gain", action="store_true", help="show how much output squeeze has saved in this repository")
    p.add_argument("command", nargs=argparse.REMAINDER)
    a = p.parse_args()
    cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
    if a.gain:
        show_gain()
        return
    if not cmd:
        p.error("give a command after --, e.g. squeeze.py -- python -m pytest -q")
    if a.max_chars < 300:
        p.error("--max-chars must be at least 300")
    env = {**os.environ, "NO_COLOR": "1", "CI": os.environ.get("CI", "1"), "PYTHONUNBUFFERED": "1"}
    env["PYTHONUTF8"] = "1"  # child Python tools must write UTF-8: that is what we decode
    env["PYTHONIOENCODING"] = "utf-8"
    budget = a.max_chars - 220  # room for the [squeeze] footer line
    popen_kw = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "env": env}
    if os.name == "nt":
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kw["start_new_session"] = True
    try:
        if a.shell:
            proc = subprocess.Popen(" ".join(cmd), shell=True, **popen_kw)
        else:
            proc = subprocess.Popen([shutil.which(cmd[0]) or cmd[0], *cmd[1:]], **popen_kw)
    except FileNotFoundError:
        print(f"[squeeze] command not found: {cmd[0]}")
        sys.exit(127)
    try:
        out_b, err_b = proc.communicate(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        try:
            out_b, err_b = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:  # a grandchild still holds the pipes; give up on its output
            out_b, err_b = b"", b""
        partial = out_b.decode("utf-8", "replace") + err_b.decode("utf-8", "replace")
        lines = select(clean(partial), budget)
        print("\n".join(lines))
        print(f"[squeeze] TIMED OUT after {a.timeout}s; process tree stopped; output above is partial.")
        sys.exit(124)
    raw = out_b.decode("utf-8", "replace")
    err = err_b.decode("utf-8", "replace")
    full = raw + (("\n" if raw and not raw.endswith("\n") else "") + err if err else "")
    lines = clean(full)
    kind = kind_of(cmd)
    if kind == "git-status":
        lines = squeeze_git_status(lines)
    elif kind == "diff":
        lines = squeeze_diff(lines)
    lines = select(lines, budget)
    compact = "\n".join(lines)
    if compact:
        print(compact)
    record_gain(len(full), len(compact))
    saved = save_full(full) if len(full) > len(compact) else None
    pct = f", -{100 - len(compact) * 100 / len(full):.1f}%" if full and len(compact) < len(full) else ""
    note = f"[squeeze] exit {proc.returncode}; {len(full):,} -> {len(compact):,} chars{pct}"
    print(note + (f"; full output: {saved}" if saved else ""))
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
