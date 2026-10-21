# Part 1: Improve an Existing Skill

Use this file only when the user asked to improve a skill they already have. Do not adapt the skill to another agent or to the user's personal workflow here.

**Contents**
1. Goal and ground rules
2. Phase 0: Snapshot and scope
3. Phase 1: Inspect the skill
4. Phase 2: Gather evidence (failures, corrections, real tasks)
5. Phase 3: Diagnose weaknesses
6. Phase 4: Revise
7. Phase 5: Test original vs revised
8. Phase 6: Decide
9. Phase 7: Report
10. Stop conditions
11. What the SkillsBench paper does and does not tell you

---

## 1. Goal and ground rules

Goal: a revised skill that measurably does better than the original on real tasks, with the same model and the same agent harness, or else the original is kept.

- The revision is a hypothesis. Do not assume it is correct.
- Keep a copy of the original. Never overwrite it.
- Keep the revision only when test results justify it.
- Do not put task-specific answers in the skill. A skill should teach a class of problems, not hand over the solution to one instance. SkillsBench rejects skills that contain task-specific filenames, paths, magic numbers, verbatim solution commands, or expected outputs, because that turns the skill into an answer key and the measurement into a test of copying.
- Do not add instructions unrelated to the skill's tasks.

## 2. Phase 0: Snapshot and scope

1. Resolve the exact path of the skill folder. Confirm `SKILL.md` exists.
2. Copy the whole folder to `<skill-name>.original/` (writable location). Everything after this happens on a separate working copy, `<skill-name>.revised/`. Note both paths in the report.
3. Note the skill's `name` and folder name. Keep them unchanged.
4. Record the test conditions you will hold fixed: **the model, the agent harness (and version if visible), and the settings**. Both versions must run under identical conditions. If you cannot learn the model or harness, write "unknown" and say so in the report.
5. Ask the user, only if not already visible: what tasks is this skill supposed to handle, and where has it failed or needed correction? If they have logs, transcripts, or corrected outputs, ask for them.

## 3. Phase 1: Inspect the skill

Run the static audit:

```bash
python scripts/audit_skill.py <path-to-original-skill>          # markdown report
python scripts/audit_skill.py <path-to-original-skill> --json   # machine-readable
```

The audit checks frontmatter, description length, body length, broken file references, user-specific absolute paths, TODO markers, and whether task-selection, ordered steps, prerequisites, fallbacks, stop conditions, and success checks appear to be present. Those last checks are keyword heuristics. A "not detected" result is a prompt to read the skill, not proof the item is missing, and a "detected" result does not prove the item is good.

Then read the skill yourself, all of it including bundled scripts and references, and write down:
- **Intended tasks**: what job each part of the skill is meant to do, and what is out of scope.
- **Trigger surface**: does the `description` say what the skill does and when to use it, with the phrases a real user would say?
- **Procedure shape**: ordered or loose? simplest method first? any step that assumes something not stated?
- **Weight**: how much the agent must read and do before it can start the task.

## 4. Phase 2: Gather evidence

Revisions must be driven by evidence. Collect, in this order of preference:

1. **Past failures**: transcripts, error logs, outputs the user rejected.
2. **Repeated corrections**: things the user had to tell the agent more than once while using the skill.
3. **Real task examples**: actual prompts the user runs, with the real inputs.

Build a **test set** from this evidence:

- At least **5 tasks** is a sensible default (this number is a recommendation, not from the paper). Include:
  - one or more tasks that **failed before** (target of the improvement),
  - one or more tasks that **worked before** (regression guard),
  - one **near-miss prompt where the skill should not be used** (tests the task-selection rule),
  - an **edge case** that exercises a fallback or stop condition.
- Each task needs an **objective success check** written before any run: a command that exits 0, a file that must exist with required content, a numeric value within tolerance, a schema that must validate, a checklist of required items the user agrees on. Prefer checks a script can run. When only human judgement works, write the rubric first and have the user judge blind to which version produced the output.
- Do not name the skill in the task prompt. The test must include the agent discovering the skill by itself, as real use does.
- Real inputs only. Do not invent toy data to make tasks easy to pass.

If the user has no failures, corrections, or tasks and cannot supply any: stop at Phase 2, tell the user the revision cannot be validated, and offer to continue with a clearly labeled **"unvalidated draft"** if they want one. Do not claim improvement.

Save the test set as a small file (task id, prompt, input files, success check, category: `failed-before | worked-before | should-not-trigger | edge`).

## 5. Phase 3: Diagnose weaknesses

Map each failure or correction to a cause. These categories come from the user's checklist plus the failure patterns that SkillsBench documented.

| Symptom | Likely cause | Fix direction |
|---|---|---|
| Skill not opened for tasks it should handle | `description` is vague or lacks the phrases users say | Rewrite description: what it does + concrete trigger contexts (and what it is *not* for) |
| Skill opened for tasks it should not handle | `description` too broad, no exclusions | Add scope limits and a "do not use for" line |
| Agent reads the skill but ignores or half-follows it | Procedure is buried in prose, long, or contradictory | Short ordered steps, one idea per step |
| Agent runs a heavy pipeline where a simple method would do (SkillsBench "Pattern A") | Only one elaborate method is described | Put the simplest valid method first; label optional steps; add a lightweight fast path |
| Skill makes the agent worse than its own default approach (Pattern B) | Generic recipe displaces a stronger native strategy | Add applicability boundaries: when to use this procedure and when not to |
| Agent gets stuck debugging a mandated tool or framework (Pattern C) | Skill requires a brittle solver, schema, or library with no escape | Add debugging fallbacks, validation checks, and an alternative route |
| Right steps, wrong output (format, units, thresholds) | Missing verifier-facing detail the agent cannot infer | Add exact output format, units, canonical data source, parsing quirks, invariants, calibrated defaults |
| Repeats the same wrong assumption | Skill states a wrong "gotcha" with confidence | Verify each claim against an authoritative source or a run; remove or correct |
| Loops, or keeps going after it should stop | No stop conditions | Add explicit stop and ask-the-user conditions |
| Reports success that is not real | No objective checks | Add success checks the agent must run before claiming done |
| Slow, many tool calls, large context | Too much text loaded, unrelated instructions, repeated exploration | Cut unrelated text; move detail to `references/` with a pointer; ship a script for repeated work |

For each diagnosed cause, write one line: *evidence → cause → intended change*. Changes without a line of evidence do not go in.

## 6. Phase 4: Revise

Edit only the working copy. Apply these principles, in this order of priority:

1. **Clear task-selection rules.** The `description` states what the skill does and when to use it. The body states scope, in-scope task types, and out-of-scope cases (with where to go instead if known). Make the description specific enough to match on first scan; a slightly "pushy" description helps against under-triggering.
2. **Short, ordered procedures.** Numbered steps in imperative form. One action per step. Put the decision points where they happen.
3. **Important prerequisites and constraints.** Tools, files, permissions, versions, inputs that must exist, and limits (what must never be done). Check for them as step 0 rather than discovering the problem midway.
4. **Simplest valid method first.** Lead with the lightest approach that satisfies the success check. Offer heavier methods only for cases that need them, and say what triggers the escalation.
5. **Fallback steps and stop conditions.** For each step that can fail: what to try next, how many times, and when to stop and ask the user or report the blocker. Include a clear "do not continue if X".
6. **Objective checks for success.** List the exact checks (commands, files, values, formats) that define done. The agent runs them and reports the actual result.
7. **No unrelated instructions and no task-specific answers.** Remove anything not needed by the skill's tasks. Remove hard-coded values that belong to one instance. Keep examples generic and mark them as examples.

Additional authoring patterns that SkillsBench's audit of its highest-gain skills found:
- **Ship an executable script with calibrated defaults** instead of only describing an algorithm, when the work is mechanical and repeated.
- **Name the canonical data source and its parsing quirks.**
- **State the exact file-format constraint** the output will be checked against.
- **State the invariant** the result must satisfy (a sanity check the agent can run on its own output).
- **Make the `description` task-specific** so it matches on the first scan.

Structure and size:
- Keep `SKILL.md` focused; around 500 lines or fewer is the usual guideline. Move long reference material to `references/` and point to it from `SKILL.md` with *when* to read it. Give files over ~300 lines a table of contents.
- Prefer a few focused pieces over many overlapping ones. In SkillsBench, tasks with one Skill or two to three Skills gained more than tasks with four or more, and compact or standard-length documentation gained more than very long documentation. That evidence is correlational (see section 11), so use it to be suspicious of bloat, not as a hard limit.
- Explain *why* a rule matters when it is not obvious. Avoid piles of ALL-CAPS commands; a model follows a reasoned rule more flexibly.

Add a short **complexity note** where it applies (the paper proposes this as a direction, not an established standard): expected cost of the heavy path, when it is justified, and the lightweight fallback.

Cross-check every claim you add: where did it come from (failure log, user, documentation, a run you did)? Remove any claim you cannot trace.

After editing, rerun `scripts/audit_skill.py` on the working copy and fix broken references or new warnings.

## 7. Phase 5: Test original vs revised

Both versions, same tasks, same model, same harness, **fresh session for every run**.

### 7.1 Setup
- Install or point the agent at one version at a time, so that exactly one of `original` or `revised` is discoverable in a run. If both would be visible at once, rename the folders so only one is, or run them in separate environments.
- Optional third arm: **no skill**. Include it when you suspect the skill may be hurting (SkillsBench found 13 of 87 tasks had negative deltas) or when the user wants to know whether the skill is worth having at all.
- Run each (task, version) cell **at least 3 times** (SkillsBench used three trials per cell; sampling randomness persists even at temperature 0). If runs are expensive, say so and use fewer, and label the confidence lower.
- Randomize or interleave order to avoid drift (rate limits, caches, changing files). Reset the working directory and inputs for every run.

### 7.2 Fresh sessions
Choose the first method available:
1. **Agent with subagents or task workers**: start one clean worker per run, with no memory of earlier runs and no access to your analysis.
2. **Headless or non-interactive mode** of the agent CLI (check the agent's `--help`): one invocation per run in a clean directory.
3. **Manual**: ask the user to open a new session for each run and paste the prompt.
4. **No isolation possible** (same chat only): runs share context and results are contaminated. Say so, treat results as a weak sanity check only, and do not recommend keeping the revision on that basis.

### 7.3 Confirm the skill is discovered and used
For every with-skill run, check the transcript or trajectory: did the agent read `SKILL.md` or invoke the skill? Record `skill_used = 1/0`. A run where the skill was never touched does not test the skill. In SkillsBench's analysis, discovery was usually not the main bottleneck, but invocation rates varied a lot by agent setup (roughly 46% to 99%), so check rather than assume. If the original is rarely discovered, that is a finding in itself: fix the description first.

### 7.4 Record per run
Save to a CSV (`assets/runs_template.csv` has the columns):

`task, version, trial, success, errors, seconds, tool_calls, unnecessary_tool_calls, context_tokens, skill_used, notes`

- **success**: 1 or 0 from the pre-written objective check (a fraction 0..1 is fine if the check has several parts).
- **errors**: count of tool or runtime errors in the run.
- **seconds**: wall-clock time of the run.
- **tool_calls**: total tool calls. **unnecessary_tool_calls**: calls that repeated earlier ones, explored irrelevant files, or retried a known-failing approach. Decide this by reading the transcript and use the same standard for both versions. If you cannot count it, leave it blank.
- **context_tokens**: tokens used, if the harness reports them. Leave blank if not.
- **skill_used**: 1/0 from 7.3.

Do not fill in numbers you did not observe. Blank is correct when unknown.

### 7.5 Compare

```bash
python scripts/compare_runs.py runs.csv --original original --revised revised [--baseline none]
```

The script reports task-macro success per version (average per task, then across tasks, like SkillsBench), per-task paired deltas, regressions, skill-use rate, cost changes (time, tool calls, unnecessary calls, context), data-quality warnings, and a suggested verdict using the rules below.

## 8. Phase 6: Decide

Default thresholds (adjustable with the user, and they are heuristics, not statistics):

| Verdict | Condition |
|---|---|
| **KEEP REVISION** | Success gain of at least 0.10 (macro) with no regressed task and no big drop in skill use; **or** success within ±0.05 and at least two cost measures (seconds, tool calls, context tokens) improved by 20% or more, with no regressed task |
| **KEEP ORIGINAL** | Success dropped by more than 0.05, or a worked-before task now fails in most trials |
| **MIXED** | Success gain but one or more tasks regressed. Look at the regressed tasks, fix the cause, and retest |
| **INCONCLUSIVE** | Differences within noise. Add tasks or trials, or keep the original |

A task counts as **regressed** when its success rate drops by 0.34 or more (with 3 trials that means losing two or more runs; losing a single run is shown in the table but treated as noise). The script also prints a **confidence** line: it reads "low" when there are fewer than 5 tasks, fewer than 3 trials in some cell, or no skill-use data. Report a low-confidence KEEP REVISION as "promising, not established".

Rules:
- With few tasks and trials, one task flipping is within noise. Say so rather than claiming a win.
- If the verdict is KEEP ORIGINAL or INCONCLUSIVE, do not install the revision. Report what you learned. Offer to iterate: apply fixes aimed at the regressed tasks, then retest with fresh sessions.
- When iterating, keep the same test set for comparability, and add new tasks for new problems. Beware of fitting the revision to the test tasks: a final check on a few tasks not used during revision is more trustworthy.
- If the user wants the revision installed, do it only after they confirm, and keep the original copy.

## 9. Phase 7: Report

Fill in `assets/improvement-report.md`. It must contain:
- what was inspected and the paths of original and revised copies,
- the evidence used and the diagnosis table,
- the list of changes with the evidence behind each,
- test conditions (model, harness, trials, fresh-session method),
- results table (success, errors, time, unnecessary tool calls, context use, skill-use rate), per-task deltas, and failures,
- the verdict and whether the revision was kept,
- **remaining risks and untested areas** (for example: only one model tested, small task set, cost counts unavailable, contaminated runs).

Lead with the outcome in one or two sentences. Do not hide a negative result.

## 10. Stop conditions

Stop and tell the user (do not push on) when:
- `SKILL.md` is missing or unreadable, or the path cannot be resolved.
- You cannot make a copy of the original.
- There are no failures, corrections, or tasks, and the user cannot provide any (see Phase 2).
- The skill is not discovered in with-skill runs and you cannot tell why. Fix discovery first.
- You cannot run fresh sessions of any kind. Report revisions as unvalidated.
- A revision step would require running unreviewed scripts of unknown origin. Review them first, or ask the user.
- The user asks you to keep a revision that the tests show is worse. State the result plainly; the decision is theirs, and you do not hide the data.

## 11. What the SkillsBench paper does and does not tell you

Use these as guidance. They come from one benchmark of 87 terminal-based tasks with curated skills, run on 18 model and agent combinations.

- Curated skills raised average pass rate from 33.9% to 50.5% (+16.6 points), with a spread of +4.1 to +25.7 depending on the agent setup. The same skill helps different setups by different amounts, so test on **your** agent and model.
- Skills help most on specialized procedural work that models know less well, and least where the model already does well.
- Some skills hurt: 13 of 87 tasks showed negative deltas. Heavy pipelines, displaced stronger defaults, and brittle mandated solvers were the repeated causes, all of which lacked applicability boundaries or a lightweight fallback.
- Skills the agent wrote for itself did worse than no skill on all three setups where it was tested (about −8 to −11 points). Reasons found: the solver never discovered them, authoring displaced real work, and packs that were used locked in confidently wrong content. This is the reason Part 1 insists on evidence-based edits and testing.
- The quantity and length comparisons (one skill versus four or more; compact versus comprehensive documentation) are observational comparisons across different tasks. They suggest focus beats exhaustiveness but do not prove that cutting a given skill's length will help. Test the cut.
- The paper's tasks are containerized terminal tasks with deterministic verifiers. Results may not carry over to GUI agents, multi-agent work, or very long tasks, and the benchmark's skills are high quality, which is more favorable than the typical skill in the wild.
