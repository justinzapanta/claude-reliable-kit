# Contributing

Start with one observed failure. Include the smallest shareable prompt and fixture, the expected behavior, what Claude actually did, and which skill was installed. Include the model and runtime version if available. Replace private code or credentials with a synthetic example before sharing.

For a workflow change, edit the relevant folder under `skills/`. Add a case in `evals/cases.json` with an unused ID and observable pass conditions. Include a situation where the workflow should be skipped if your change broadens when the skill activates. Keep each evaluation fixture unchanged between comparison runs.

For claims about cost or reliability, run the same prompt in fresh sessions with and without the skill. Capture correctness, tool calls and reported token usage for both, including failures. Use the [benchmark plan](evals/benchmark-plan.md) for comparisons across models or projects.

## Package a change

Run these commands from the kit directory with Python 3. They use the standard library.

```sh
python tools/package_skills.py
python tools/package_skills.py --check
```

The builder puts one ZIP per skill under `releases/`, including the MIT license. The check compares packaged file names and contents with the editable sources. In your pull request, include the failure that motivated the change, the affected skill and the checks you actually ran.
