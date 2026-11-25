"""Lint checks for every SKILL.md. Run from the kit root: python -m unittest discover -s tests -v

Keeps skills portable (Claude Code, claude.ai upload, API), cheap to keep installed, and free of broken links.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
NAMES = {p.name for p in SKILLS}
# Fields accepted by claude.ai uploads and the Skills API; anything else fails there.
PORTABLE_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
MAX_DESCRIPTION = 200        # characters; descriptions are loaded in every session
MAX_ALL_DESCRIPTIONS = 1800  # whole kit, characters
MAX_BODY_TOKENS = 1200       # rough estimate (chars / 4); body stays in context once loaded


def parse(skill):
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        raise AssertionError(f"{skill.name}: missing frontmatter")
    fields = dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)
    return fields, m.group(2), text


class SkillLint(unittest.TestCase):
    def test_kit_is_not_empty(self):
        self.assertGreater(len(SKILLS), 0)

    def test_frontmatter(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                fields, _, _ = parse(skill)
                self.assertEqual(fields.get("name"), skill.name)
                self.assertRegex(skill.name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
                self.assertLessEqual(len(skill.name), 64)
                self.assertNotRegex(skill.name, "anthropic|claude")
                self.assertLessEqual(set(fields), PORTABLE_FIELDS)

    def test_descriptions(self):
        total = 0
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                desc = parse(skill)[0].get("description", "")
                total += len(desc)
                self.assertTrue(desc)
                self.assertLessEqual(len(desc), MAX_DESCRIPTION)
                self.assertNotRegex(desc, r"[<>]")
                self.assertIn("Use ", desc, "say when to use it")
                self.assertNotRegex(desc, r"^(I|You) ", "write in the third person")
        self.assertLessEqual(total, MAX_ALL_DESCRIPTIONS)

    def test_body_size(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                _, body, _ = parse(skill)
                self.assertLess(body.count("\n"), 500)
                self.assertLessEqual(len(body) // 4, MAX_BODY_TOKENS)

    def test_links_and_scripts_exist(self):
        for skill in SKILLS:
            _, body, _ = parse(skill)
            for target in re.findall(r"\]\(([^)#]+)\)", body):
                if "://" not in target:
                    with self.subTest(skill=skill.name, link=target):
                        self.assertTrue((skill / target).exists())
            for script in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+\.py)", body):
                with self.subTest(skill=skill.name, script=script):
                    self.assertTrue((skill / script).exists())

    def test_cross_skill_references_exist(self):
        pattern = re.compile(r"`([a-z]+(?:-[a-z]+)+)`")
        allowed_non_skills = {"allowed-tools", "add-replace"}
        for skill in SKILLS:
            _, body, _ = parse(skill)
            for ref in pattern.findall(body):
                if ref in allowed_non_skills:
                    continue
                with self.subTest(skill=skill.name, ref=ref):
                    self.assertIn(ref, NAMES, "backticked kebab-case name should be a skill in this kit")

    def test_readme_catalog_matches_skills(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        listed = set(re.findall(r"\| \[([a-z-]+)\]\(skills/", readme))
        self.assertEqual(listed, NAMES)
        self.assertIn(f"collection of {len(SKILLS)} developer skills", readme)

    def test_no_stray_control_characters_in_sources(self):
        """Catches escaping slips such as a regex \b written as a backspace character."""
        allowed = {9, 10, 13}
        sources = [*ROOT.glob("skills/*/scripts/*.py"), *ROOT.glob("tools/*.py"), *ROOT.glob("tests/*.py"), ROOT / "install.py",
                   *ROOT.glob("evals/fixtures/*.py"), *ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("skills/*/references/*.md")]
        for path in sources:
            with self.subTest(file=path.relative_to(ROOT).as_posix()):
                text = path.read_text(encoding="utf-8")
                bad = sorted({hex(ord(c)) for c in text if ord(c) < 32 and ord(c) not in allowed})
                self.assertEqual(bad, [], "control characters in source")

    def test_release_archive_per_skill(self):
        zips = {p.stem for p in (ROOT / "releases").glob("*.zip")}
        self.assertEqual(zips, NAMES)


if __name__ == "__main__":
    unittest.main()
