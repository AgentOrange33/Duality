# Skill improvement report: <skill-name>

**Outcome (1-2 sentences, lead with the result):** <kept revision / kept original / inconclusive, and why>

## 1. What was inspected
- Original copy (untouched): `<path>`
- Revised copy: `<path>`
- Intended tasks of the skill: <...>
- Audit findings that mattered: <...>

## 2. Evidence used
| Source (failure log / user correction / real task) | What happened |
|---|---|
| | |

## 3. Diagnosis
| Evidence | Cause | Intended change |
|---|---|---|
| | | |

## 4. Changes made
| Change | Evidence behind it | Principle applied (selection rule / ordered steps / prerequisites / simplest-first / fallback & stop / success checks / removed unrelated) |
|---|---|---|
| | | |

## 5. Test conditions
- Model: <...>   Agent harness (and version): <...>   (same for all runs)
- Fresh-session method: <subagent / headless CLI / manual new session / not isolated>
- Tasks: <n> (failed-before: <n>, worked-before: <n>, should-not-trigger: <n>, edge: <n>)
- Trials per task per version: <n>
- Arms: original, revised<, no-skill>
- Success checks were written before running: <yes/no>

## 6. Results
| version | tasks | runs | success | errors/run | seconds | tool calls | unnecessary calls | context tokens | skill used |
|---|---|---|---|---|---|---|---|---|---|
| original | | | | | | | | | |
| revised | | | | | | | | | |

Per-task paired results and regressions: <table or link to compare_runs output>
Not measured: <e.g., context tokens unavailable>

## 7. Failures
- <task / version / what failed / cause if known>

## 8. Verdict
<KEEP REVISION | KEEP ORIGINAL | MIXED | INCONCLUSIVE> — <reasons, thresholds used>

## 9. Remaining risks and untested areas
- <e.g., one model only; small task set; costs not measured; runs not independent>

## 10. Next steps offered
- <...>
