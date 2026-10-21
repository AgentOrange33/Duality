#!/usr/bin/env python3
"""Compare original vs revised skill runs from a CSV (Part 1 helper).

CSV columns (header required; extra columns ignored; blanks mean "not measured"):
    task, version, trial, success, errors, seconds, tool_calls,
    unnecessary_tool_calls, context_tokens, skill_used, notes

Scoring follows the SkillsBench convention: average trials within each task,
then average across tasks (task-macro). Deltas are paired by task.

Usage:
    python compare_runs.py runs.csv [--original original] [--revised revised]
        [--baseline NAME] [--min-gain 0.10] [--noise 0.05]
        [--cost-gain 0.20] [--regress 0.34] [--json]

The verdict is a heuristic aid, not a statistical test. With few tasks or
trials, one flipped task is within noise. A task counts as regressed when its
success rate drops by --regress or more (default 0.34: with 3 trials, losing
two or more runs; losing a single run is shown in the table but not flagged).
"""
import argparse
import csv
import json
import statistics as st
import sys
from collections import defaultdict

METRICS = ["success", "errors", "seconds", "tool_calls", "unnecessary_tool_calls", "context_tokens", "skill_used"]
COST_METRICS = ["seconds", "tool_calls", "unnecessary_tool_calls", "context_tokens"]


def num(x):
    x = (x or "").strip()
    if x == "":
        return None
    try:
        return float(x)
    except ValueError:
        low = x.lower()
        if low in ("true", "yes", "pass", "passed"):
            return 1.0
        if low in ("false", "no", "fail", "failed"):
            return 0.0
        raise


def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        missing = {"task", "version", "trial", "success"} - set(rd.fieldnames or [])
        if missing:
            sys.exit(f"CSV is missing required columns: {sorted(missing)}")
        for i, r in enumerate(rd, 2):
            if not (r.get("task") or "").strip():
                continue
            row = {"task": r["task"].strip(), "version": r["version"].strip(), "trial": (r.get("trial") or "").strip()}
            for m in METRICS:
                try:
                    row[m] = num(r.get(m))
                except ValueError:
                    sys.exit(f"Row {i}: column '{m}' has non-numeric value {r.get(m)!r}")
            if row["success"] is None:
                sys.exit(f"Row {i}: 'success' is blank; every run needs a recorded success value")
            rows.append(row)
    return rows


def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def per_task(rows, version):
    """{task: {metric: mean over trials, 'n': trials}}"""
    cells = defaultdict(list)
    for r in rows:
        if r["version"] == version:
            cells[r["task"]].append(r)
    out = {}
    for t, rs in cells.items():
        d = {m: mean([x[m] for x in rs]) for m in METRICS}
        d["n"] = len(rs)
        out[t] = d
    return out


def macro(pt, metric):
    return mean([d[metric] for d in pt.values()])


def fmt(x, nd=2, pct=False):
    if x is None:
        return "n/a"
    return f"{x*100:.0f}%" if pct else f"{x:.{nd}f}"


def pct_change(new, old):
    if new is None or old is None or old == 0:
        return None
    return (new - old) / old


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--original", default="original")
    ap.add_argument("--revised", default="revised")
    ap.add_argument("--baseline", default=None, help="optional no-skill arm name")
    ap.add_argument("--min-gain", type=float, default=0.10)
    ap.add_argument("--noise", type=float, default=0.05)
    ap.add_argument("--cost-gain", type=float, default=0.20)
    ap.add_argument("--regress", type=float, default=0.34, help="per-task success drop that counts as a regression")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rows = load(a.csv)
    versions = [a.original, a.revised] + ([a.baseline] if a.baseline else [])
    pts = {v: per_task(rows, v) for v in versions}
    for v in versions:
        if not pts[v]:
            sys.exit(f"No rows found for version '{v}'. Versions present: {sorted({r['version'] for r in rows})}")

    warnings = []
    tasks_o, tasks_r = set(pts[a.original]), set(pts[a.revised])
    shared = sorted(tasks_o & tasks_r)
    if tasks_o != tasks_r:
        warnings.append(f"Task sets differ (only original: {sorted(tasks_o - tasks_r)}; only revised: {sorted(tasks_r - tasks_o)}). Comparison uses the {len(shared)} shared tasks.")
    if not shared:
        sys.exit("No tasks in common between original and revised.")
    for v in versions:
        low = sorted(t for t, d in pts[v].items() if d["n"] < 3)
        if low:
            warnings.append(f"{v}: {len(low)} task(s) have fewer than 3 trials ({', '.join(low[:5])}{'...' if len(low) > 5 else ''}); confidence is low.")
    if len(shared) < 5:
        warnings.append(f"Only {len(shared)} shared task(s); fewer than the recommended 5.")
    mism = [t for t in shared if pts[a.original][t]["n"] != pts[a.revised][t]["n"]]
    if mism:
        warnings.append(f"Trial counts differ between versions for: {', '.join(mism[:5])}.")

    # restrict to shared tasks
    sub = {v: {t: d for t, d in pts[v].items() if t in shared or v == a.baseline} for v in versions}

    summary = {}
    for v in versions:
        pt = sub[v] if v != a.baseline else {t: d for t, d in pts[v].items() if t in shared}
        summary[v] = {m: macro(pt, m) for m in METRICS}
        summary[v]["tasks"] = len(pt)
        summary[v]["runs"] = sum(d["n"] for d in pt.values())

    # paired per-task deltas
    deltas, regress, improved = [], [], []
    for t in shared:
        so, sr = pts[a.original][t]["success"], pts[a.revised][t]["success"]
        d = sr - so
        deltas.append((t, so, sr, d))
        if d <= -a.regress:
            regress.append(t)
        elif d >= a.regress:
            improved.append(t)
    gain = mean([d for *_, d in deltas])

    # cost changes (per-task paired, median % change)
    cost = {}
    for m in COST_METRICS:
        chs = []
        for t in shared:
            c = pct_change(pts[a.revised][t][m], pts[a.original][t][m])
            if c is not None:
                chs.append(c)
        cost[m] = {"median_pct_change": st.median(chs) if chs else None, "tasks_measured": len(chs)}
    cost_wins = [m for m in COST_METRICS if m in ("seconds", "tool_calls", "context_tokens") and
                 cost[m]["median_pct_change"] is not None and cost[m]["median_pct_change"] <= -a.cost_gain]

    used_o, used_r = summary[a.original]["skill_used"], summary[a.revised]["skill_used"]
    discovery_drop = used_o is not None and used_r is not None and used_r < used_o - 0.15
    if used_r is None:
        warnings.append("skill_used not recorded for the revised version; cannot confirm the skill was discovered.")
    elif used_r < 0.8:
        warnings.append(f"Revised skill was used in only {used_r*100:.0f}% of runs; results may reflect discovery, not content.")
    if used_o is not None and used_o < 0.8:
        warnings.append(f"Original skill was used in only {used_o*100:.0f}% of runs.")

    reasons = []
    if gain >= a.min_gain and not regress and not discovery_drop:
        verdict = "KEEP_REVISION"
        reasons.append(f"Macro success gain {gain:+.2f} (>= {a.min_gain}), no regressed task, no big drop in skill use.")
    elif abs(gain) <= a.noise and len(cost_wins) >= 2 and not regress:
        verdict = "KEEP_REVISION"
        reasons.append(f"Success within noise ({gain:+.2f}); cost improved by >= {a.cost_gain*100:.0f}% on: {', '.join(cost_wins)}; no regressed task.")
    elif gain < -a.noise or (regress and gain <= 0):
        verdict = "KEEP_ORIGINAL"
        reasons.append(f"Macro success change {gain:+.2f}" + (f"; regressed tasks: {', '.join(regress)}" if regress else "") + ".")
    elif gain >= a.min_gain and (regress or discovery_drop):
        verdict = "MIXED"
        if regress:
            reasons.append(f"Gain {gain:+.2f} but regressed task(s): {', '.join(regress)}.")
        if discovery_drop:
            reasons.append("Skill-use rate dropped noticeably for the revision.")
    else:
        verdict = "INCONCLUSIVE"
        reasons.append(f"Macro success change {gain:+.2f} is within the gray zone; add tasks or trials, or keep the original.")

    if a.baseline:
        b = summary[a.baseline]["success"]
        if b is not None:
            for v in (a.original, a.revised):
                if summary[v]["success"] is not None and summary[v]["success"] < b - a.noise:
                    warnings.append(f"'{v}' scores below the no-skill baseline ({fmt(summary[v]['success'], pct=True)} vs {fmt(b, pct=True)}): the skill may be hurting.")

    low_conf = []
    if len(shared) < 5:
        low_conf.append(f"only {len(shared)} shared task(s)")
    few = [v for v in versions if any(d["n"] < 3 for d in pts[v].values())]
    if few:
        low_conf.append("some tasks have fewer than 3 trials")
    if used_r is None:
        low_conf.append("skill use not recorded")
    confidence = "low" if low_conf else "ok"

    result = {
        "verdict": verdict, "confidence": confidence, "confidence_notes": low_conf, "reasons": reasons, "macro_success_gain": gain,
        "summary": summary, "per_task": [{"task": t, "original": so, "revised": sr, "delta": d} for t, so, sr, d in deltas],
        "regressed": regress, "improved": improved, "cost_change": cost, "warnings": warnings,
        "thresholds": {"min_gain": a.min_gain, "noise": a.noise, "cost_gain": a.cost_gain, "regress": a.regress},
    }
    if a.json:
        print(json.dumps(result, indent=2))
        return 0

    o = []
    o.append(f"# Skill comparison: {a.original} vs {a.revised}")
    o.append("")
    o.append(f"**Suggested verdict: {verdict}** (heuristic; thresholds in --help)")
    o.append(f"**Confidence: {confidence}**" + (f" ({'; '.join(low_conf)}). Do not treat this as proof; add tasks or trials." if low_conf else ""))
    for r in reasons:
        o.append(f"- {r}")
    o.append("")
    o.append("## Aggregate (task-macro; averaged per task, then across tasks)")
    o.append("| version | tasks | runs | success | errors/run | seconds | tool calls | unnecessary calls | context tokens | skill used |")
    o.append("|---|---|---|---|---|---|---|---|---|---|")
    for v in versions:
        s = summary[v]
        o.append(f"| {v} | {s['tasks']} | {s['runs']} | {fmt(s['success'], pct=True)} | {fmt(s['errors'])} | {fmt(s['seconds'], 1)} | {fmt(s['tool_calls'], 1)} | {fmt(s['unnecessary_tool_calls'], 1)} | {fmt(s['context_tokens'], 0)} | {fmt(s['skill_used'], pct=True)} |")
    o.append("")
    o.append(f"Macro success change (revised - original): **{gain:+.2f}**")
    o.append("")
    o.append("## Cost change (median per-task % change, revised vs original; negative is cheaper)")
    for m in COST_METRICS:
        c = cost[m]
        pc = c["median_pct_change"]
        pc_txt = "n/a" if pc is None else "{:+.0f}%".format(pc * 100)
        o.append("- {}: {} (tasks measured: {})".format(m, pc_txt, c["tasks_measured"]))
    o.append("")
    o.append("## Per-task paired success")
    o.append("| task | original | revised | delta | flag |")
    o.append("|---|---|---|---|---|")
    for t, so, sr, d in deltas:
        flag = "REGRESSION" if t in regress else ("improved" if t in improved else "")
        o.append(f"| {t} | {fmt(so, pct=True)} | {fmt(sr, pct=True)} | {d:+.2f} | {flag} |")
    if warnings:
        o.append("")
        o.append("## Warnings")
        for w in warnings:
            o.append(f"- {w}")
    o.append("")
    o.append("Reminder: report failures and remaining risks in the final report; do not install a revision on an INCONCLUSIVE or KEEP_ORIGINAL result.")
    print("\n".join(o))
    return 0


if __name__ == "__main__":
    sys.exit(main())
