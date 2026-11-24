"""Tests for the kit's helper scripts. Run from the kit root: python -m unittest discover -s tests -v

Standard library only. Each test builds its own temporary project, so nothing in the kit is modified.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = ROOT / "skills" / "lean-navigation" / "scripts"
LEDGER = ROOT / "skills" / "task-ledger" / "scripts" / "ledger.py"
PRICING = ROOT / "evals" / "fixtures" / "pricing-project"
HAS_GIT = shutil.which("git") is not None


def run(script, *args, cwd=None, stdin=None, env=None):
    proc = subprocess.run([sys.executable, "-I", str(script), *map(str, args)], cwd=cwd, input=stdin,
                          capture_output=True, text=True, encoding="utf-8", timeout=60,
                          env={**os.environ, **(env or {})})
    return proc


def write(base, rel, text):
    path = Path(base) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})


class TempProject(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kit-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def web_project(base):
    write(base, "src/components/Cart.tsx",
          'import { useCart } from "../hooks";\nexport function Cart() {\n  const cart = useCart();\n'
          "  return <div>{cart.items.map(i => i.name)}</div>;\n}\n")
    write(base, "src/hooks/index.ts", "export function useCart() {\n  return { items: [] };\n}\n"
          "export const useTotals = async () => 1;\n")
    write(base, "src/cart.test.ts", 'import { useCart } from "./hooks";\ntest("x", () => useCart());\n')
    write(base, "server/routes/orders.js",
          'router.get("/api/orders/:id/items", async (req, res) => {\n'
          '  if (!req.user) throw new Error("Order access denied for this account");\n});\n')
    write(base, "server/main.go", "package main\n\nfunc HandleOrders(w Writer) {\n}\n")
    write(base, "server/lib.rs", "pub fn parse_total(s: &str) -> u32 {\n    0\n}\n")
    write(base, "node_modules/react/index.js", "export function useCart() {}\n")


class FindTests(TempProject):
    def test_python_definition_ranks_first(self):
        out = run(NAV / "find.py", "tax_cents", PRICING, "--symbol", "--ext", "py").stdout
        self.assertIn("4 [definition]: def tax_cents", out)
        self.assertLess(out.index("pricing.py"), out.index("test_pricing.py"))

    def test_js_go_rust_definitions(self):
        web_project(self.tmp)
        for name, expected in [("useCart", "[definition]: export function useCart"),
                               ("useTotals", "[definition]: export const useTotals"),
                               ("HandleOrders", "[definition]: func HandleOrders"),
                               ("parse_total", "[definition]: pub fn parse_total")]:
            with self.subTest(name=name):
                self.assertIn(expected, run(NAV / "find.py", name, self.tmp, "--symbol").stdout)

    def test_tests_rank_after_source_and_vendor_skipped(self):
        web_project(self.tmp)
        out = run(NAV / "find.py", "useCart", self.tmp, "--symbol").stdout
        self.assertLess(out.index("Cart.tsx"), out.index("cart.test.ts"))
        self.assertNotIn("node_modules", out)

    def test_near_miss_suggestion(self):
        web_project(self.tmp)
        out = run(NAV / "find.py", "useCarts", self.tmp, "--symbol").stdout
        self.assertIn("0 matches", out)
        self.assertIn("Similar names in scanned files: useCart", out)

    def test_no_suggestion_for_regex(self):
        web_project(self.tmp)
        out = run(NAV / "find.py", "zz+q", self.tmp).stdout
        self.assertNotIn("Similar names", out)

    def test_output_budget_and_truncation_notice(self):
        write(self.tmp, "big.py", "".join(f"value_{i} = 'needle {i}'\n" for i in range(200)))
        out = run(NAV / "find.py", "needle", self.tmp, "--max-chars", "400").stdout
        self.assertLessEqual(len(out.rstrip("\n")), 400)
        self.assertIn("Truncated", out)

    def test_invalid_regex_is_reported(self):
        proc = run(NAV / "find.py", "(", self.tmp)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("invalid regex", proc.stderr)

    @unittest.skipUnless(HAS_GIT, "git not installed")
    def test_changed_only_searches_local_edits(self):
        write(self.tmp, "a.py", "TOKEN = 1\n")
        write(self.tmp, "b.py", "TOKEN = 2\n")
        git(self.tmp, "init", "-q")
        git(self.tmp, "add", ".")
        git(self.tmp, "commit", "-qm", "init")
        write(self.tmp, "b.py", "TOKEN = 3\n")
        write(self.tmp, "c.py", "TOKEN = 4\n")
        out = run(NAV / "find.py", "TOKEN", self.tmp, "--changed").stdout
        self.assertIn("Local changes only", out)
        self.assertIn("b.py", out)
        self.assertIn("c.py", out)
        self.assertNotIn("a.py", out)

    def test_map_option(self):
        out = run(NAV / "find.py", "tax_cents", PRICING, "--map").stdout
        self.assertIn("Repo overview", out)


class TraceTests(TempProject):
    BROWSER_ERROR = (
        "Uncaught TypeError: Cannot read properties of undefined (reading 'items')\n"
        "    at Cart (http://localhost:5173/src/components/Cart.tsx?t=1712:4:22)\n"
        "    at renderWithHooks (http://localhost:5173/node_modules/.vite/deps/chunk-ABC.js:1200:3)\n"
        "GET http://localhost:5173/api/orders/8812/items 500 (Internal Server Error)\n"
        "Error: Order access denied for this account\n")

    def test_browser_error_maps_every_clue(self):
        web_project(self.tmp)
        out = run(NAV / "trace.py", "--dir", self.tmp, self.BROWSER_ERROR).stdout
        self.assertIn("frame: src/components/Cart.tsx:4", out)
        self.assertIn("src/components/Cart.tsx:4: return <div>{cart.items", out)
        self.assertIn("route: /api/orders/8812/items", out)
        self.assertIn('server/routes/orders.js:1: router.get("/api/orders/:id/items"', out)
        self.assertIn("identifier: items", out)
        self.assertIn("message: Order access denied for this account", out)
        self.assertNotIn("node_modules", out)
        self.assertNotIn("chunk-ABC", out)

    def test_reads_stdin(self):
        web_project(self.tmp)
        out = run(NAV / "trace.py", "--dir", self.tmp, stdin=self.BROWSER_ERROR).stdout
        self.assertIn("frame: src/components/Cart.tsx:4", out)

    def test_route_styles(self):
        for route_src in ['app.get("/api/users/:id")', "@app.get('/api/users/{user_id}')",
                          "// pages/api/users/[id].ts handles /api/users/[id]"]:
            with self.subTest(route=route_src):
                d = self.tmp / str(abs(hash(route_src)))
                write(d, "routes.txt.js", route_src + "\n")
                out = run(NAV / "trace.py", "--dir", d, "PATCH /api/users/42 404").stdout
                self.assertIn("routes.txt.js:1", out)

    def test_python_traceback(self):
        err = ('Traceback (most recent call last):\n  File "/srv/app/pricing.py", line 8, in tax_cents\n'
               "NameError: name 'tax_cents' is not defined\n")
        out = run(NAV / "trace.py", "--dir", PRICING, err).stdout
        self.assertIn("frame: srv/app/pricing.py:8", out)
        self.assertIn("pricing.py:8: return subtotal_cents", out)
        self.assertNotIn("tests/test_pricing.py:8", out.split("identifier")[0])

    def test_frame_does_not_match_similar_filename(self):
        write(self.tmp, "tests/test_pricing.py", "x = 1\n")
        out = run(NAV / "trace.py", "--dir", self.tmp, 'File "pricing.py", line 1').stdout
        self.assertIn("No match: frame pricing.py:1", out)

    def test_line_beyond_file_is_explained(self):
        write(self.tmp, "src/app.js", "one\n")
        out = run(NAV / "trace.py", "--dir", self.tmp, "at x (src/app.js:99:1)").stdout
        self.assertIn("line beyond file end", out)

    def test_no_clues(self):
        out = run(NAV / "trace.py", "--dir", self.tmp, "oops").stdout
        self.assertIn("No usable clues", out)

    def test_budget(self):
        web_project(self.tmp)
        out = run(NAV / "trace.py", "--dir", self.tmp, "--max-chars", "300", self.BROWSER_ERROR).stdout
        self.assertLessEqual(len(out.rstrip("\n")), 300)

    @unittest.skipUnless(HAS_GIT, "git not installed")
    def test_changed_mode(self):
        web_project(self.tmp)
        git(self.tmp, "init", "-q")
        git(self.tmp, "add", ".")
        git(self.tmp, "commit", "-qm", "init")
        write(self.tmp, "server/routes/new.js", 'throw new Error("Order access denied for this account")\n')
        out = run(NAV / "trace.py", "--dir", self.tmp, "--changed", "Error: Order access denied for this account").stdout
        self.assertIn("local changes only", out)
        self.assertIn("server/routes/new.js", out)
        self.assertNotIn("orders.js", out)


class OutlineMapTests(TempProject):
    def test_outline_python_and_js(self):
        out = run(NAV / "outline.py", PRICING / "pricing.py").stdout
        self.assertIn("4: def tax_cents", out)
        web_project(self.tmp)
        out = run(NAV / "outline.py", self.tmp / "src").stdout
        self.assertIn("export function useCart", out)

    def test_outline_missing_target(self):
        self.assertNotEqual(run(NAV / "outline.py", self.tmp / "nope").returncode, 0)

    def test_map(self):
        web_project(self.tmp)
        out = run(NAV / "map.py", self.tmp).stdout
        self.assertIn("Files indexed:", out)
        self.assertIn("TypeScript", out)
        self.assertNotIn("node_modules", out)


class LedgerTests(TempProject):
    def ledger(self, *args, env=None, cwd=None):
        proc = run(LEDGER, *args, cwd=cwd or self.tmp, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    @unittest.skipUnless(HAS_GIT, "git not installed")
    def test_git_default_location_never_committed(self):
        git(self.tmp, "init", "-q")
        out = self.ledger("init", env={"LEDGER_FILE": ""})
        self.assertIn(str(Path(".git") / "task-ledger.json"), out)
        self.ledger("add", "req", "keep API", env={"LEDGER_FILE": ""})
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.tmp, capture_output=True, text=True).stdout
        self.assertEqual(status.strip(), "")

    @unittest.skipUnless(HAS_GIT, "git not installed")
    def test_default_from_subdirectory_uses_same_ledger(self):
        git(self.tmp, "init", "-q")
        (self.tmp / "sub").mkdir()
        self.ledger("init", env={"LEDGER_FILE": ""})
        self.ledger("add", "req", "from root", env={"LEDGER_FILE": ""})
        out = self.ledger("summary", env={"LEDGER_FILE": ""}, cwd=self.tmp / "sub")
        self.assertIn("from root", out)

    def test_full_workflow_with_ledger_file(self):
        env = {"LEDGER_FILE": str(self.tmp / "l.json")}
        self.ledger("init", env=env)
        self.ledger("add", "req", "keep API", env=env)
        self.ledger("add", "open", "check rounding", env=env)
        self.ledger("add", "pref", "likes short answers", "--src", "user", env=env)
        self.ledger("verify", "2", "unit test", env=env)
        self.ledger("done", "1", env=env)
        out = self.ledger("summary", env=env)
        self.assertIn("3 entries, 0 pending", out)
        self.assertIn("verified check rounding -> unit test", out)
        self.ledger("add", "pref", "likes detailed answers", "--src", "user", "--replace", "3", env=env)
        data = json.loads((self.tmp / "l.json").read_text(encoding="utf-8"))
        self.assertEqual([i["text"] for i in data["items"] if i["kind"] == "pref"], ["likes detailed answers"])
        out = self.ledger("export", env=env)
        self.assertTrue((self.tmp / "ledger-export.md").exists(), out)

    def test_cap_keeps_open_and_pref(self):
        env = {"LEDGER_FILE": str(self.tmp / "l.json")}
        self.ledger("add", "open", "must survive", env=env)
        self.ledger("add", "pref", "keep me", env=env)
        for i in range(35):
            self.ledger("add", "loc", f"file{i}.py:1", env=env)
        data = json.loads((self.tmp / "l.json").read_text(encoding="utf-8"))
        self.assertLessEqual(len(data["items"]), 30)
        kinds = [i["kind"] for i in data["items"]]
        self.assertIn("open", kinds)
        self.assertIn("pref", kinds)

    def test_full_ledger_refuses_new_requirement(self):
        env = {"LEDGER_FILE": str(self.tmp / "l.json")}
        for i in range(30):
            self.ledger("add", "req", f"r{i}", env=env)
        proc = run(LEDGER, "add", "req", "one too many", cwd=self.tmp, env=env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("ledger full", proc.stderr)

    def test_unknown_id(self):
        env = {"LEDGER_FILE": str(self.tmp / "l.json")}
        proc = run(LEDGER, "done", "9", cwd=self.tmp, env=env)
        self.assertIn("no entry 9", proc.stderr)


class PackagingTests(unittest.TestCase):
    def test_release_archives_match_sources(self):
        proc = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "package_skills.py"), "--check"],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class FixtureTests(unittest.TestCase):
    def test_pricing_fixture_suite_passes(self):
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=PRICING,
                              capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
