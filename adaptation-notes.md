# Adaptation notes: <skill-name> for <target agent>

**Outcome (lead with whether it works):** <e.g., installed in the agent's skill folder; activation check passed; one real task passed; fallbacks untested>

## 1. Provenance and safety review
- Source: <URL/path>, author: <...>, version/commit: <...>, license: <...>
- Source copy (unchanged): `<path>`   Adapted copy: `<path>`
- Scripts reviewed (one line each: what it does / reads / writes / network):
  - <script>: <...>
- Inventory scan result: <risky patterns found / none>; human review decision: <approved / approved with conditions / stopped>
- Approvals needed from the user before running: <installs, network use, scripts>

## 2. Target agent profile (summary)
<paste key rows from target-agent-profile.md with verified / documented / assumed marks>

## 3. Mapping table (Layer 2)
| Source item (file:line) | Class (portable / replaceable / no equivalent / removable) | Target equivalent or fallback | Verified how |
|---|---|---|---|
| | | | |

## 4. Removed or changed assumptions
- <item, reason>

## 5. Fixes to core knowledge (Layer 1), if any
- <defect, minimal fix, why. "None" is a fine answer.>

## 6. User configuration (Layer 3)
| Setting | Value | Origin (user said / found / default) |
|---|---|---|
| | | |

## 7. Validation (Layer 4)
| Check | Result | Notes |
|---|---|---|
| Install check (location, format, frontmatter) | | |
| Activation check (fresh session, skill not named) | | |
| Non-activation check (unrelated prompt) | | |
| Real task(s): <what, with what success check> | | |
| Output verification against success criteria | | |
| Failure recovery / fallback exercised | | |
| Cost (tool calls, time, context) | | |
| Regression vs source skill (if it can run) | | |

**Not tested:** <...>

## 8. Remaining risks
- <...>

## 9. What the user needs to do
- <approvals, tool installs, settings to fill in>
