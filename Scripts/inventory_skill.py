#!/usr/bin/env python3
"""Inventory a skill's agent-specific dependencies and flag risky patterns (Part 2 helper).

Read-only: it opens text files and matches regular expressions. It never
executes anything from the skill. Results are heuristics: a clean scan is not
proof of safety, and a hit is not proof of malice or of a real dependency.

Usage:
    python inventory_skill.py <skill-folder> [--json]

Exit codes: 0 = scan ran, 2 = path problem.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TEXT_EXT = {".md", ".txt", ".py", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".js", ".mjs", ".ts", ".json",
            ".yaml", ".yml", ".toml", ".cfg", ".ini", ".html", ".css", ".csv", ".rb", ".go", ".rs", ".lua", ".mdc", ".xml", ".xsd"}
MAX_BYTES = 1_000_000

# category -> list of (label, regex)
DEPENDENCY_PATTERNS = {
    "Agent config paths and instruction files": [
        ("Claude-style path/file", r"~?/?\.claude\b|\bCLAUDE\.md\b"),
        ("Codex/AGENTS-style path/file", r"~?/?\.codex\b|\bAGENTS\.md\b"),
        ("OpenCode path/file", r"\.opencode\b|\bopencode\.json\b"),
        ("Gemini path/file", r"~?/?\.gemini\b|\bGEMINI\.md\b"),
        ("Hermes path/file", r"~?/?\.hermes\b"),
        ("Cursor/other IDE rules", r"\.cursor(rules)?\b|\.windsurf\b|\.clinerules\b|\.continue\b"),
        ("OpenHands path", r"\.openhands\b"),
    ],
    "Tool names (agent-specific)": [
        ("Task/Agent/subagent tool", r"\bTask tool\b|\bAgent tool\b|\bsub-?agents?\b|\bspawn(ing)? (an? )?(agent|worker)\b"),
        ("Todo tool", r"\bTodoWrite\b|\btodo list tool\b"),
        ("Web tools", r"\bWebSearch\b|\bWebFetch\b|\bweb_search\b|\bweb_fetch\b"),
        ("File/edit tools", r"\b(Read|Edit|Write|MultiEdit|NotebookEdit) tool\b|\bstr_replace\b|\bcreate_file\b|\bpresent_files\b"),
        ("Search tools", r"\bGrep tool\b|\bGlob tool\b|\bGrep\b|\bGlob\b"),
        ("User-question tool", r"\bAskUserQuestion\b|\bask_user_input\b"),
        ("Bash/shell tool by name", r"\bBash tool\b|\bbash_tool\b"),
    ],
    "Slash commands, hooks, MCP": [
        ("Slash command", r"(?:^|[\s`(])/(?!usr\b|etc\b|tmp\b|home\b|mnt\b|var\b|bin\b|opt\b|app\b|dev\b|proc\b|sys\b|lib\b|root\b|Users\b)[a-z][a-z0-9_-]{2,}(?=[\s`).,:;]|$)"),
        ("Hooks", r"\bPreToolUse\b|\bPostToolUse\b|\bSessionStart\b|\bhooks?\b"),
        ("MCP / tool server", r"\bMCP\b|\bmcp__|\bmodel context protocol\b"),
    ],
    "Model names": [
        ("Model family names", r"\bclaude-[\w.-]+|\bgpt-[\w.-]+|\bgemini[-\w.]*|\bgrok[-\w.]*|\bqwen[-\w.]*|\bllama[-\w.]*|\bglm[-\w.]*|\bdeepseek[-\w.]*|\bmistral[-\w.]*|\b(opus|sonnet|haiku)\b"),
    ],
    "OS, shell, installs": [
        ("Package managers / installers", r"\bapt(-get)?\b|\bbrew\b|\byum\b|\bdnf\b|\bpacman\b|\bchoco\b|\bwinget\b|\bpip3? install\b|\bnpm (i|install)\b|\byarn add\b|\bcargo install\b|\bgo install\b"),
        ("Shell/OS specifics", r"\bsudo\b|\bpowershell\b|\bcmd\.exe\b|\bchmod\b|\bchown\b|\.bat\b|\.ps1\b|\bWSL\b|C:\\\\|/mnt/|\bsystemctl\b|\blaunchctl\b"),
        ("Dependency manifests", r"requirements\.txt|package\.json|pyproject\.toml|Cargo\.toml|go\.mod|Gemfile|Dockerfile"),
    ],
    "Network and secrets": [
        ("URLs / network calls", r"https?://[^\s)>\"']+|\bcurl\b|\bwget\b|requests\.(get|post|put)|\bfetch\(|urllib|\bhttpx\b|\baiohttp\b|\bsocket\b"),
        ("Environment variables / keys", r"os\.environ|getenv|process\.env|\$\{?[A-Z][A-Z0-9_]{3,}\}?|API_KEY|SECRET|TOKEN|PASSWORD|\.env\b"),
    ],
}

RISK_PATTERNS = [
    ("Pipes a download into a shell", r"(curl|wget)[^|\n]*\|\s*(sudo\s+)?(ba|z)?sh\b"),
    ("eval/exec of dynamic code", r"(?<![.\w])(eval|exec)\s*\(|\bnew Function\s*\("),
    ("Base64 decode (possible hidden payload)", r"base64\s+(-d|--decode)|b64decode|atob\s*\("),
    ("Recursive/forced deletion", r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r|shutil\.rmtree|Remove-Item[^\n]*-Recurse"),
    ("World-writable permissions", r"chmod\s+(-R\s+)?(0?777|a\+rwx)"),
    ("Credential or key file access", r"\.ssh\b|id_rsa|id_ed25519|\.aws/credentials|\.netrc|\.npmrc|\.pypirc|\.git-credentials|keychain|credentials\.json|Login Data|cookies\.sqlite"),
    ("Process/command execution from code", r"os\.system|subprocess\.|child_process|\bPopen\b|Runtime\.getRuntime|shell=True"),
    ("Reverse-shell or raw socket patterns", r"/dev/tcp/|\bnc\s+-|netcat|socket\.socket|bash\s+-i"),
    ("Persistence mechanisms", r"\bcrontab\b|systemctl\s+enable|launchctl\s+load|schtasks|\.bashrc|\.zshrc|\.profile\b|authorized_keys|startup folder"),
    ("Text trying to override instructions", r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules)|disregard (all |any )?(the )?(previous|prior|above) |you are now |do not tell the user|don't tell the user|without (telling|informing) the user"),
    ("Long encoded blob", r"[A-Za-z0-9+/]{200,}={0,2}"),
    ("Hidden/zero-width characters", "[\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]"),
    ("Writes outside the skill folder (heuristic)", r"open\([^)]*['\"](/etc/|/usr/|~/|/root/)|>\s*~/|>\s*/etc/"),
]


def list_text_files(root):
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".git" in p.parts or "__pycache__" in p.parts:
            continue
        yield p


def scan(root):
    dep = defaultdict(lambda: defaultdict(list))   # category -> label -> [(file, line, snippet)]
    risk = defaultdict(list)
    files_info = []
    skipped = []
    langs = defaultdict(int)
    for p in list_text_files(root):
        rel = str(p.relative_to(root)).replace("\\", "/")
        ext = p.suffix.lower()
        size = p.stat().st_size
        executable = bool(p.stat().st_mode & 0o111)
        files_info.append({"file": rel, "bytes": size, "executable": executable})
        langs[ext or "(none)"] += 1
        if ext not in TEXT_EXT and ext != "":
            skipped.append(f"{rel} (binary or unscanned type {ext})")
            continue
        if size > MAX_BYTES:
            skipped.append(f"{rel} (over {MAX_BYTES} bytes)")
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append(f"{rel} (not UTF-8)")
            continue
        lines = text.splitlines()
        for cat, items in DEPENDENCY_PATTERNS.items():
            for label, rx in items:
                cre = re.compile(rx, re.I if label in ("Model family names",) else 0)
                for i, ln in enumerate(lines, 1):
                    m = cre.search(ln)
                    if m:
                        dep[cat][label].append((rel, i, ln.strip()[:140]))
        for label, rx in RISK_PATTERNS:
            cre = re.compile(rx, re.I)
            for i, ln in enumerate(lines, 1):
                m = cre.search(ln)
                if m and label == "Hidden/zero-width characters" and i == 1 and m.start() == 0 and m.group(0) == "\ufeff" and not cre.search(ln[1:]):
                    m = None  # a byte-order mark at the very start of a file is routine
                if m:
                    snippet = ln.strip()
                    if label == "Long encoded blob":
                        snippet = snippet[:60] + "... (blob)"
                    elif label == "Hidden/zero-width characters":
                        snippet = "contains U+%04X" % ord(m.group(0))
                    risk[label].append((rel, i, snippet[:140]))
    return dep, risk, files_info, skipped, langs


def md_report(root, dep, risk, files_info, skipped, langs, max_per_label=8):
    o = [f"# Skill inventory: {root}", ""]
    o.append("Read-only heuristic scan. Nothing was executed. Hits need human judgment.")
    o.append("")
    o.append("## Files")
    o.append(f"- {len(files_info)} files; types: " + ", ".join(f"{k}: {v}" for k, v in sorted(langs.items())))
    code_ext = (".py", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".js", ".mjs", ".ts", ".rb", ".go", ".rs", ".lua")
    scripts = [f["file"] for f in files_info if f["file"].lower().endswith(code_ext) or f["executable"]]
    shown = ", ".join(scripts[:15]) + (f" ... (+{len(scripts) - 15} more)" if len(scripts) > 15 else "")
    o.append("- code files / executables: " + (shown if scripts else "none"))
    if skipped:
        o.append("- not scanned: " + "; ".join(skipped[:10]) + (" ..." if len(skipped) > 10 else ""))
    o.append("")
    o.append("## Security review (do this before running or installing anything)")
    if not risk:
        o.append("- No risky patterns matched. This does not prove the skill is safe; still read its scripts.")
    for label, hits in risk.items():
        o.append(f"- **{label}**: {len(hits)} hit(s)")
        for f, ln, sn in hits[:max_per_label]:
            o.append(f"    - `{f}:{ln}` {sn}")
        if len(hits) > max_per_label:
            o.append(f"    - ... {len(hits) - max_per_label} more")
    o.append("")
    o.append("## Dependencies and assumptions (candidates for the Layer 2 / Layer 3 mapping table)")
    if not dep:
        o.append("- none matched")
    for cat, labels in dep.items():
        o.append(f"### {cat}")
        for label, hits in labels.items():
            o.append(f"- **{label}**: {len(hits)} hit(s)")
            for f, ln, sn in hits[:max_per_label]:
                o.append(f"    - `{f}:{ln}` {sn}")
            if len(hits) > max_per_label:
                o.append(f"    - ... {len(hits) - max_per_label} more (use --json for all)")
    o.append("")
    o.append("Next: classify each item as portable, replaceable, no-equivalent, or removable, then fill the mapping table.")
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = Path(a.skill_dir).resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2
    dep, risk, files_info, skipped, langs = scan(root)
    if a.json:
        conv = lambda d: {k: [{"file": f, "line": l, "text": t} for f, l, t in v] for k, v in d.items()}
        print(json.dumps({
            "path": str(root),
            "files": files_info,
            "not_scanned": skipped,
            "risk": conv(risk),
            "dependencies": {c: conv(l) for c, l in dep.items()},
        }, indent=2))
    else:
        print(md_report(root, dep, risk, files_info, skipped, langs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
