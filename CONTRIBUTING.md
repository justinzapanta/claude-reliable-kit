# Contributing

Start with one observed failure. Include the smallest shareable prompt and fixture, the expected behavior, what Claude actually did, and which skill was installed. Include the model and runtime version if available. Replace private code or credentials with a synthetic example before sharing.

For a workflow change, edit the relevant folder under `skills/`. Add a case in `evals/cases.json` with an unused ID and observable pass conditions. Include a situation where the workflow should be skipped if your change broadens when the skill activates. Keep each evaluation fixture unchanged between comparison runs.

For claims about cost or reliability, run the same prompt in fresh sessions with and without the skill. Capture correctness, tool calls and reported token usage for both, including failures. Use the [benchmark plan](evals/benchmark-plan.md) for comparisons across models or projects.

## Test and package a change

Everything runs with Python 3.9+ and the standard library. One command runs the whole process:

```sh
python tools/check.py                 # before every commit: tests, lint, release ZIP check, quick fuzz (~1-2 min)
python tools/check.py --full          # before a release: + deep fuzz on two seeds + 6,000-file stress test
python tools/check.py --repos <dir>   # + the workbench on real Git checkouts in <dir> (e.g. clones of flask, express)
```

| Tool | What it proves |
|---|---|
| `tests/test_scripts.py` | Each script's behavior, plus one regression test per fixed bug (`HardeningTests`) |
| `tests/test_skills.py` | Skill files: portable frontmatter, description and body size, links, script paths, README catalog, no control characters |
| `tools/fuzz.py` | Thousands of random and malformed inputs to every script never cause a traceback, a wrong exit code, or output over budget; dry runs never write |
| `tools/stress.py` | A generated 6,000-file repository with long lines, odd encodings, a 3 MB log, and 300 commits: every command within its time and output budget |
| `tools/workbench.py` | The same commands on real repositories you choose |
| `tools/package_skills.py --check` | Release ZIPs match the sources |

CI (`.github/workflows/ci.yml`) runs the fast check on Windows, macOS, and Linux with Python 3.9 and 3.13 for every push and pull request, and the full check weekly. When something fails, add a test that reproduces it before fixing it.

The builder puts one ZIP per skill under `releases/`, including the MIT license. The check compares packaged file names and contents with the editable sources. In your pull request, include the failure that motivated the change, the affected skill and the checks you actually ran.
