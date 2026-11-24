---
name: read-before-write
description: Inspect nearby examples first when unfamiliar project conventions, APIs, or test patterns could affect a code change.
---

# Read Before Write

Start with the closest working example in the affected module. Reuse evidence already gathered during planning or debugging. Follow the project's naming, data contracts, and test conventions.

Look up a manifest, configuration file, or helper only when a specific decision remains unresolved. If nearby examples disagree, check which one serves the current code path. Record a convention only when it explains a consequential choice or helps someone resume the work.
