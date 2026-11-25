#!/usr/bin/env python3
"""Install Claude Reliable Kit in one command. Stdlib only; every step is reversible and previewable.

  python install.py                       # copy the 10 skills to ~/.claude/skills (all your projects)
  python install.py --project PATH        # copy them into PATH/.claude/skills instead (commit them for your team)
  python install.py --all --project PATH  # skills + CLAUDE.md rules + memory hook + memory seeded from git history

Options (combine freely):
  --claude-md     add the kit's rules to PATH/CLAUDE.md inside a marked block (replaced on re-run)
  --lean-replies  also add the optional shorter-replies rules
  --hook          register the memory hook: Claude sees recorded decisions before editing a file
  --seed          bootstrap project memory from fix commits and warning comments in PATH
  --dry-run       show what would change without writing anything
  --uninstall     remove the kit's skills, CLAUDE.md block, and hook from the chosen scope
Without --project, rules, hook settings, and seed apply to the current directory as the project, and the hook is
registered in ~/.claude/settings.json; with --project, the hook goes in PATH/.claude/settings.json.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
SKILLS = sorted(p for p in (KIT / "skills").iterdir() if (p / "SKILL.md").is_file())
OBSOLETE = ["minimal-change", "read-before-write", "verify-before-done"]
BEGIN, END = "<!-- claude-reliable-kit:begin -->", "<!-- claude-reliable-kit:end -->"
HOOK_MARK = "memory_hook.py"


class Plan:
    def __init__(self, dry):
        self.dry, self.done = dry, []

    def note(self, text):
        self.done.append(("would " if self.dry else "") + text)


def rules(skills_ref, lean):
    text = (KIT / "templates" / "CLAUDE.md").read_text(encoding="utf-8")
    core, _, optional = text.partition("## Optional: shorter replies")
    lines = [l for l in core.splitlines() if l.startswith("- ")]
    if lean:
        lines += [l for l in optional.splitlines() if l.startswith("- ")]
    return [l.replace("~/.claude/skills", skills_ref) for l in lines]


MARKER = ".claude-reliable-kit"  # written into each installed skill folder; never shipped in release ZIPs


def is_link(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def ours(target, name):
    """True if the folder holds a kit skill (marker file, or a SKILL.md declaring the kit skill's name)."""
    if (target / MARKER).exists():
        return True
    skill_md = target / "SKILL.md"
    try:
        return skill_md.is_file() and f"name: {name}" in skill_md.read_text(encoding="utf-8")
    except OSError:
        return False


def preflight_skills(dest, force):
    problems = []
    for skill in SKILLS:
        target = dest / skill.name
        if is_link(target):
            problems.append(f"{target} is a symbolic link or junction; remove it or install elsewhere")
        elif target.exists() and not ours(target, skill.name) and not force:
            problems.append(f"{target} exists and is not a Claude Reliable Kit skill; rename it or pass --force")
    return problems


def copy_skills(dest, plan):
    for old in OBSOLETE:
        target = dest / old
        if not is_link(target) and ours(target, old):
            plan.note(f"remove obsolete skill {target}")
            if not plan.dry:
                shutil.rmtree(target)
    for skill in SKILLS:
        target = dest / skill.name
        plan.note(f"{'update' if target.exists() else 'install'} skill {target}")
        if not plan.dry:
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(skill, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (target / MARKER).write_text("Installed by Claude Reliable Kit's install.py; safe to delete.\n", encoding="utf-8")


def backup_once(path):
    """Keep the user's original file the first time the kit changes it; later runs never overwrite that copy."""
    backup = path.with_name(path.name + ".before-claude-reliable-kit")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)


def split_block(text, where):
    """Return (before, after) around the kit block, (text, None) if absent; refuse on malformed markers."""
    b, e = text.count(BEGIN), text.count(END)
    if b == 0 and e == 0:
        return text, None
    if b != 1 or e != 1 or text.index(BEGIN) > text.index(END):
        raise SystemExit(f"{where}: the Claude Reliable Kit markers are damaged ({b} begin, {e} end). "
                         f"Fix or remove them by hand; nothing was changed.")
    before, rest = text.split(BEGIN, 1)
    return before, rest.split(END, 1)[1]


def write_block(claude_md, lines, plan, remove=False):
    current = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""
    before, after = split_block(current, claude_md)
    base = current if after is None else before.rstrip("\n") + ("\n" if before.strip() else "") + after.lstrip("\n")
    if remove:
        new = base
    else:
        block = "\n".join([BEGIN, "## Claude Reliable Kit rules", "", *lines, END])
        new = (base.rstrip("\n") + "\n\n" if base.strip() else "") + block + "\n"
    if new != current:
        plan.note(f"{'remove the kit block from' if remove else 'write the kit block in'} {claude_md}")
        if not plan.dry:
            claude_md.parent.mkdir(parents=True, exist_ok=True)
            backup_once(claude_md)
            claude_md.write_text(new, encoding="utf-8")


def load_settings(settings):
    if not settings.exists():
        return {}
    try:
        data = json.loads(settings.read_text(encoding="utf-8") or "{}")
    except ValueError:
        raise SystemExit(f"{settings} is not valid JSON (comments are not allowed); fix it or add the hook by hand. "
                         "Nothing was changed.")
    if data is None:
        return {}
    hooks = data.get("hooks") if isinstance(data, dict) else None
    groups = hooks.get("PreToolUse", []) if isinstance(hooks, dict) else []
    if (not isinstance(data, dict) or (hooks is not None and not isinstance(hooks, dict)) or not isinstance(groups, list)
            or not all(isinstance(g, dict) and isinstance(g.get("hooks", []), list) for g in groups)):
        raise SystemExit(f"{settings} has an unexpected structure; add the hook by hand (see README). Nothing was changed.")
    return data


def edit_settings(settings, command, plan, remove=False):
    data = load_settings(settings)
    hooks = data.get("hooks") or {}
    groups = hooks.get("PreToolUse", [])
    kept = []
    for group in groups:
        entries = [h for h in group.get("hooks", []) if HOOK_MARK not in str(h.get("command", ""))]
        if entries or not group.get("hooks"):
            kept.append({**group, "hooks": entries} if group.get("hooks") else group)
    if not remove:
        kept.append({"matcher": "Edit|Write|MultiEdit", "hooks": [{"type": "command", "command": command, "timeout": 10}]})
    if kept == groups:
        return
    if kept:
        hooks["PreToolUse"] = kept
    else:
        hooks.pop("PreToolUse", None)
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    plan.note(f"{'remove the memory hook from' if remove else 'register the memory hook in'} {settings}")
    if not plan.dry:
        settings.parent.mkdir(parents=True, exist_ok=True)
        backup_once(settings)
        settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


for _stream in (sys.stdout, sys.stderr):  # never crash on non-ASCII output (Windows consoles default to cp1252)
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", help="install into this project (PATH/.claude/skills) instead of ~/.claude/skills")
    p.add_argument("--claude-md", action="store_true")
    p.add_argument("--lean-replies", action="store_true")
    p.add_argument("--hook", action="store_true")
    p.add_argument("--seed", action="store_true")
    p.add_argument("--all", action="store_true", help="--claude-md --hook --seed")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--force", action="store_true", help="replace same-named skill folders that are not from this kit")
    p.add_argument("--home", help=argparse.SUPPRESS)  # for tests
    a = p.parse_args()
    if a.all:
        a.claude_md = a.hook = a.seed = True
    home = Path(a.home or Path.home())
    project = Path(a.project or os.getcwd()).resolve()
    in_project = bool(a.project)
    skills_dir = project / ".claude" / "skills" if in_project else home / ".claude" / "skills"
    skills_ref = ".claude/skills" if in_project else "~/.claude/skills"
    settings = project / ".claude" / "settings.json" if in_project else home / ".claude" / "settings.json"
    portable_py = "python" if os.name == "nt" else ("python3" if shutil.which("python3") else "python")
    py = portable_py if in_project else f'"{Path(sys.executable).as_posix()}"'
    hook_path = ('"$CLAUDE_PROJECT_DIR/.claude/skills/task-ledger/scripts/memory_hook.py"' if in_project
                 else f'"{(skills_dir / "task-ledger" / "scripts" / "memory_hook.py").as_posix()}"')
    plan = Plan(a.dry_run)

    # Validate everything before changing anything, so a problem never leaves a half-done install or uninstall.
    split_block((project / "CLAUDE.md").read_text(encoding="utf-8") if (project / "CLAUDE.md").exists() else "",
                project / "CLAUDE.md")
    load_settings(settings)
    if not a.uninstall:
        problems = preflight_skills(skills_dir, a.force)
        if problems:
            raise SystemExit("Nothing was changed:\n - " + "\n - ".join(problems))

    if a.uninstall:
        for skill in SKILLS:
            target = skills_dir / skill.name
            if target.exists() and not is_link(target) and ours(target, skill.name):
                plan.note(f"remove skill {skills_dir / skill.name}")
                if not plan.dry:
                    shutil.rmtree(skills_dir / skill.name)
        write_block(project / "CLAUDE.md", [], plan, remove=True)
        edit_settings(settings, "", plan, remove=True)
    else:
        if sys.version_info < (3, 9):
            raise SystemExit("Python 3.9 or newer is required.")
        copy_skills(skills_dir, plan)
        if a.claude_md or a.lean_replies:
            write_block(project / "CLAUDE.md", rules(skills_ref, a.lean_replies), plan)
        if a.hook:
            edit_settings(settings, f"{py} {hook_path}", plan)
        if a.seed:
            if (project / ".git").exists():
                plan.note(f"seed project memory from git history in {project}")
                if not plan.dry:
                    r = subprocess.run([sys.executable, str(skills_dir / "task-ledger" / "scripts" / "memory.py"), "seed",
                                        "--dir", str(project)], capture_output=True, text=True, encoding="utf-8", errors="replace")
                    plan.done.append("  " + (r.stdout.strip().splitlines() or ["(no output)"])[0])
            else:
                plan.done.append(f"skipped seed: {project} is not a Git repository")
    print(("Dry run. " if a.dry_run else "") + f"Claude Reliable Kit ({len(SKILLS)} skills):")
    for line in plan.done or ["nothing to change"]:
        print(" - " + line)
    if not a.dry_run and not a.uninstall:
        print("Restart Claude Code (or start a new session) so it loads the skills" + (" and the hook." if a.hook else "."))


if __name__ == "__main__":
    main()
