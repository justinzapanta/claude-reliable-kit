---
name: edge-case-security
description: Check security boundaries and failure paths when requested or when a change touches sensitive input, auth, secrets, or payments.
---

# Edge Cases and Security

Most bugs live off the happy path. Spend a short, systematic pass on failure and abuse before finishing.

## Edge-case pass (every function that takes input)

Ask of each input:
- **Empty / null / missing?** Zero, empty string, empty list, `None`.
- **Wrong type or shape?** String instead of number, extra or missing fields.
- **Boundaries?** Off-by-one, min/max, first/last item, single item.
- **Huge?** Very large input, deep nesting, many items. Is there a limit?
- **Odd text?** Unicode, whitespace, very long strings, special characters, different time zones and locales.
- **Repeated or concurrent?** Duplicate submits, retries, race conditions.
- **Failure of dependencies?** Network timeout, disk full, DB down, partial writes. Are errors handled and cleaned up?

Add or run a test for the two or three most likely ones.

## Security pass (when input is untrusted)

- **Injection:** SQL (use parameterized queries), shell commands (avoid `shell=True`, pass argument lists), template and HTML output (escape to prevent XSS).
- **Authentication and authorization:** every protected path checks who the user is and whether they may access *this* object (not just that they're logged in).
- **Secrets:** none hardcoded, none logged, none committed. Use environment variables or a secret manager.
- **Paths and files:** block `../` traversal, validate file names and types and sizes.
- **Deserialization and eval:** don't `eval`/`exec`/unpickle untrusted data.
- **Passwords:** use a slow salted hash (bcrypt, scrypt, argon2). Never roll your own crypto.
- **Dependencies:** pinned versions, no abandoned packages.
- **Errors:** don't leak stack traces or internals to users.
- **SSRF and redirects:** validate URLs the server fetches.

## Reporting

List findings by severity: **High / Medium / Low**. For each: where (`path:line`), what could go wrong in one sentence, and a concrete fix. Skip theoretical noise. Say clearly what you did not check.

## Boundaries

Help the user find and fix weaknesses in their own code. Don't write exploits or attack tooling.
