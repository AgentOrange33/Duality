#!/usr/bin/env python3
"""Static audit of an agent skill folder (Part 1 helper).

Read-only. Checks structure and a few keyword heuristics. The heuristics
("detected / not detected") are prompts for a human or agent to read the
skill, not proof that something is good or missing.

Usage:
    python audit_skill.py <skill-folder> [--json]

Exit codes: 0 = audit ran, 2 = SKILL.md missing or unreadable.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TEXT_EXT = {".md", ".txt", ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".csv"}
MAX_READ = 1_000_000  # bytes


def parse_frontmatter(text):
    """Return (dict, body, error). Minimal parser, no PyYAML dependency."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)$", text, re.S)
    if not m:
        return {}, text, "No YAML frontmatter block found at top of SKILL.md"
    raw, body = m.group(1), m.group(2)
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(raw)
        if isinstance(data, dict):
            return {str(k): ("" if v is None else str(v)) for k, v in data.items()}, body, None
        return {}, body, "Frontmatter is not a key: value mapping"
    except ImportError:
        pass
    except Exception as exc:  # yaml error
        return {}, body, f"Frontmatter YAML error: {exc}"
    data, key = {}, None
    for line in raw.splitlines():
        km = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if km:
            key = km.group(1)
            val = km.group(2).strip()
            data[key] = "" if val in (">", "|", ">-", "|-") else val.strip("\"'")
        elif key and line.startswith((" ", "\t")):
            data[key] = (data[key] + " " + line.strip()).strip()
    return data, body, None


HEURISTICS = {
    "task selection (when to use / not use)": r"when to use|use this skill|use when|use only|trigger|do not use|don't use|not for|out of scope|scope|routing|route\b",
    "prerequisites / constraints": r"prerequisite|requires?\b|before you (start|begin)|dependenc|must have|install|constraint|never\b",
    "fallback steps": r"fallback|fall back|if .{0,60}(fails|errors|missing|unavailable)|otherwise|alternatively|instead",
    "stop conditions": r"\bstop\b|\babort\b|ask the user|do not proceed|don't proceed|escalate|give up|report (the )?(blocker|failure)",
    "success checks": r"verif|check that|success|validate|assert|expected output|must pass|exit code|done when|acceptance",
}

PATH_REF = re.compile(r"(?<![\w/.-])((?:references|scripts|assets|templates|examples|resources)/[\w./-]+\.[A-Za-z0-9]+)")
ABS_USER_PATH = re.compile(r"(/Users/[\w.-]+|/home/[\w.-]+|[A-Za-z]:\\Users\\[\w.-]+)")
TODO = re.compile(r"\b(TODO|FIXME|XXX|TBD)\b\s*[:(\-]")


def list_files(root):
    return [p for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts]


def audit(root):
    findings = []  # (severity, message)
    info = {}

    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        return None, [("error", "SKILL.md not found")], {}
    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception as exc:
        return None, [("error", f"Cannot read SKILL.md: {exc}")], {}

    fm, body, err = parse_frontmatter(text)
    if err:
        findings.append(("error", err))
    name = fm.get("name", "")
    desc = fm.get("description", "")

    if not name:
        findings.append(("error", "Frontmatter has no 'name'"))
    else:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            findings.append(("warn", f"name '{name}' is not lowercase-hyphen style"))
        if name != root.name and not root.name.endswith((".original", ".revised", ".source", ".adapted")):
            findings.append(("info", f"name '{name}' differs from folder name '{root.name}'"))
    if not desc:
        findings.append(("error", "Frontmatter has no 'description' (the main trigger for discovery)"))
    else:
        if len(desc) < 80:
            findings.append(("warn", f"description is short ({len(desc)} chars); may be too vague to match user requests"))
        if len(desc) > 1024:
            findings.append(("warn", f"description is long ({len(desc)} chars); some agents limit it (commonly 1024)"))
        if not re.search(r"\b(use|when|whenever|trigger)\b", desc, re.I):
            findings.append(("warn", "description does not say when to use the skill"))

    lines = body.splitlines()
    n_lines = len(lines)
    n_words = len(body.split())
    approx_tokens = len(text.encode("utf-8")) // 4
    if n_lines > 500:
        findings.append(("warn", f"SKILL.md body is {n_lines} lines (guideline is about 500 or fewer); move detail into references/"))

    # Heuristic structure checks
    corpus = [desc, body]
    ref_dir = root / "references"
    if ref_dir.is_dir():
        for rp in sorted(ref_dir.rglob("*.md")):
            try:
                if rp.stat().st_size <= MAX_READ:
                    corpus.append(rp.read_text(encoding="utf-8"))
            except Exception:
                pass
    lower = "\n".join(corpus).lower()
    detected = {}
    for label, pattern in HEURISTICS.items():
        hit = re.search(pattern, lower) is not None
        detected[label] = hit
        if not hit:
            findings.append(("hint", f"not detected (keyword heuristic): {label}"))
    numbered = sum(1 for ln in "\n".join(corpus).splitlines() if re.match(r"^\s*\d+[.)]\s+\S", ln))
    detected["ordered steps (3+ numbered lines)"] = numbered >= 3
    if numbered < 3:
        findings.append(("hint", f"not detected (keyword heuristic): ordered steps; found {numbered} numbered lines"))

    # Emphasis density
    caps = len(re.findall(r"\b(ALWAYS|NEVER|MUST|CRITICAL|IMPORTANT)\b", body))
    if caps >= 8:
        findings.append(("hint", f"{caps} ALL-CAPS directive words; consider explaining the reason instead of shouting"))

    # Markers and paths
    for i, ln in enumerate(lines, 1):
        if TODO.search(ln):
            findings.append(("warn", f"SKILL.md body line {i}: TODO/FIXME marker: {ln.strip()[:80]}"))
    for i, ln in enumerate(lines, 1):
        m = ABS_USER_PATH.search(ln)
        if m:
            findings.append(("warn", f"SKILL.md body line {i}: user-specific absolute path '{m.group(1)}' will not work on other machines"))

    # Referenced files exist?
    files = list_files(root)
    rels = {str(p.relative_to(root)).replace("\\", "/") for p in files}
    refs = set(PATH_REF.findall(text))
    broken = sorted(r for r in refs if r not in rels and not any(x in r for x in ("<", ">", "*", "{", "}")))
    for r in broken:
        findings.append(("warn", f"SKILL.md mentions '{r}' but the file does not exist"))

    # Orphans (bundled but never mentioned)
    all_text = "\n".join(corpus + [text])
    refs = set(PATH_REF.findall(all_text)) | refs
    mentioned = {r for r in refs}
    for rel in sorted(rels):
        if rel == "SKILL.md" or rel.startswith("evals/"):
            continue
        if rel.split("/")[0] in {"references", "scripts", "assets"} and rel not in mentioned:
            base = rel.split("/")[-1]
            if base not in all_text:
                findings.append(("hint", f"bundled file '{rel}' is never mentioned in SKILL.md (agent may never discover it)"))

    # Other text files: TODO and user paths, long files without TOC
    for p in files:
        if p.suffix.lower() not in TEXT_EXT or p.name == "SKILL.md" or p.stat().st_size > MAX_READ:
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(p.relative_to(root))
        n = len(t.splitlines())
        if p.suffix.lower() == ".md" and n > 300 and not re.search(r"(?i)^#+\s*(table of )?contents|^\*\*contents\*\*", t, re.M):
            findings.append(("hint", f"{rel} is {n} lines with no table of contents"))
        for i, ln in enumerate(t.splitlines(), 1):
            if TODO.search(ln):
                findings.append(("warn", f"{rel} line {i}: TODO/FIXME marker"))
                break
        m = ABS_USER_PATH.search(t)
        if m:
            findings.append(("warn", f"{rel}: user-specific absolute path '{m.group(1)}'"))

    info.update({
        "name": name,
        "description_chars": len(desc),
        "skill_md_lines": n_lines,
        "skill_md_words": n_words,
        "skill_md_approx_tokens_incl_frontmatter": approx_tokens,
        "total_files": len(files),
        "total_bytes": sum(p.stat().st_size for p in files),
        "scripts": sorted(r for r in rels if r.startswith("scripts/")),
        "references": sorted(r for r in rels if r.startswith("references/")),
        "heuristics_detected": detected,
    })
    return info, findings, {}


def render_markdown(root, info, findings):
    order = {"error": 0, "warn": 1, "hint": 2, "info": 3}
    out = [f"# Skill audit: {root}", ""]
    out.append("## Facts")
    out.append(f"- name: `{info.get('name') or '(missing)'}`")
    out.append(f"- description length: {info['description_chars']} chars")
    out.append(f"- SKILL.md body: {info['skill_md_lines']} lines, {info['skill_md_words']} words, about {info['skill_md_approx_tokens_incl_frontmatter']} tokens (bytes/4 estimate)")
    out.append(f"- files: {info['total_files']} ({info['total_bytes']} bytes); scripts: {len(info['scripts'])}; references: {len(info['references'])}")
    out.append("")
    out.append("## Keyword heuristics over description, SKILL.md and references/*.md (a match does not mean the content is good)")
    for k, v in info["heuristics_detected"].items():
        out.append(f"- [{'x' if v else ' '}] {k}")
    out.append("")
    out.append("## Findings")
    if not findings:
        out.append("- none")
    for sev, msg in sorted(findings, key=lambda f: order[f[0]]):
        out.append(f"- **{sev}**: {msg}")
    out.append("")
    out.append("Next: read the skill yourself. This audit cannot judge whether steps are correct, simplest-first, or tied to real failures.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = ap.parse_args()
    root = Path(args.skill_dir).resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2
    info, findings, _ = audit(root)
    if info is None:
        print(f"ERROR: {findings[0][1]}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"path": str(root), "facts": info, "findings": [{"severity": s, "message": m} for s, m in findings]}, indent=2))
    else:
        print(render_markdown(root, info, findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
