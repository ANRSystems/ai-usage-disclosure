#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
ai-usage-gen — draft an ai-usage.yml from git history.

Scans commit trailers (Co-authored-by:, Assisted-by:) and known AI-agent
signatures, maps the files those commits touched to disclosure areas, and
emits a DRAFT ai-usage.yml for a human to review.

What it can know:  *which areas* AI touched, and *which tools* were involved.
What it cannot know: how much was human-edited (the level) or whether output
was reviewed. Those are proposed conservatively and flagged for confirmation.

Zero dependencies. Requires only python3 and git.

Usage:
    python3 ai-usage-gen.py                  # print draft to stdout
    python3 ai-usage-gen.py --write          # write ./ai-usage.yml
    python3 ai-usage-gen.py --repo ../proj --write
                                             # write ../proj/ai-usage.yml
    python3 ai-usage-gen.py --since 2025-01-01
    python3 ai-usage-gen.py --repo ../proj --default-level assisted
"""

import argparse
import datetime
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# --- AI agent identities -----------------------------------------------------
# (substring, pretty-name). Matched case-insensitively against trailer values,
# author name/email, and signature lines in the commit body.
AI_SIGNATURES = [
    ("claude", "Claude (Anthropic)"),
    ("anthropic", "Claude (Anthropic)"),
    ("copilot", "GitHub Copilot"),
    ("openai", "OpenAI"),
    ("chatgpt", "OpenAI"),
    ("gemini", "Google Gemini"),
    ("cursor", "Cursor"),
    ("codeium", "Codeium / Windsurf"),
    ("windsurf", "Codeium / Windsurf"),
    ("devin", "Devin (Cognition)"),
    ("cognition", "Devin (Cognition)"),
    ("aider", "Aider"),
    ("sourcegraph", "Sourcegraph Cody"),
    (" cody", "Sourcegraph Cody"),
    ("tabnine", "Tabnine"),
    ("codewhisperer", "Amazon Q / CodeWhisperer"),
    ("amazon q", "Amazon Q / CodeWhisperer"),
]

TRAILER_RE = re.compile(r"^\s*(co-authored-by|assisted-by|co-author)\s*:\s*(.+)$", re.I)

LEVELS = ["none", "assisted", "collaborative", "generated"]

# --- file -> area classification --------------------------------------------
DOC_EXT = (".md", ".rst", ".adoc", ".txt")
ASSET_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
             ".mp3", ".wav", ".mp4", ".mov", ".ttf", ".otf", ".woff", ".woff2")
DATA_EXT = (".csv", ".tsv", ".parquet", ".sqlite", ".db", ".jsonl")
CODE_EXT = (".py", ".rs", ".c", ".h", ".cpp", ".cc", ".hpp", ".js", ".ts",
            ".jsx", ".tsx", ".go", ".java", ".rb", ".cs", ".swift", ".kt",
            ".scala", ".sh", ".sql", ".vue", ".php", ".m", ".mm")
CONFIG_EXT = (".toml", ".yaml", ".yml", ".ini", ".cfg", ".lock")
CONFIG_FILES = {
    "dockerfile", "makefile", "cmakelists.txt", "package.json", "package-lock.json",
    "pyproject.toml", "poetry.lock", "requirements.txt", "cargo.toml", "cargo.lock",
    "go.mod", "go.sum", "tsconfig.json", "webpack.config.js",
}


def classify(path: str) -> str:
    p = path.lower()
    base = p.rsplit("/", 1)[-1]
    # Tests first: a .py under tests/ is tests, not code.
    if (re.search(r"(^|/)tests?(/|$)", p) or "__tests__" in p or "/spec/" in p
            or re.search(r"\.(test|spec)\.", base) or re.search(r"_test\.", base)
            or re.search(r"_spec\.", base)):
        return "tests"
    # Design / architecture docs.
    if "/adr/" in p or "architecture" in p or re.search(r"(^|/)design(/|$)", p):
        return "design"
    # Documentation.
    if p.endswith(DOC_EXT) or "/docs/" in p or p.startswith("docs/") \
            or "readme" in base or "changelog" in base or "contributing" in base:
        return "documentation"
    # Assets.
    if p.endswith(ASSET_EXT) or "/assets/" in p or "/static/" in p or "/public/" in p:
        return "assets"
    # Data.
    if p.endswith(DATA_EXT) or re.search(r"(^|/)data(/|$)", p):
        return "data"
    # Source and project configuration are treated as code/runtime-maintenance work.
    if p.endswith(CODE_EXT) or p.endswith(CONFIG_EXT) or base in CONFIG_FILES:
        return "code"
    # Conservative fallback: unknown files are part of the code/repo maintenance surface.
    return "code"


# --- git ---------------------------------------------------------------------
def git_log(repo, since, until):
    fmt = "%x1e%H%x1f%an%x1f%ae%x1f%b%x1f"
    cmd = ["git", "-C", repo, "log", "--no-merges", "--no-color",
           f"--pretty=format:{fmt}", "--name-only"]
    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        sys.exit(f"git error: {out.stderr.strip()}")
    return out.stdout


def parse_commits(raw):
    commits = []
    for chunk in raw.split("\x1e"):
        if not chunk.strip():
            continue
        parts = chunk.split("\x1f")
        if len(parts) < 5:
            continue
        h, an, ae, body, files_blob = parts[0], parts[1], parts[2], parts[3], parts[4]
        files = [ln.strip() for ln in files_blob.splitlines() if ln.strip()]
        commits.append({"hash": h.strip(), "an": an, "ae": ae,
                        "body": body, "files": files})
    return commits


def detect_ai(commit):
    """Return set of pretty tool names if this commit shows AI involvement."""
    hits = set()
    haystacks = [commit["an"], commit["ae"]]
    # Trailer values.
    for line in commit["body"].splitlines():
        m = TRAILER_RE.match(line)
        if m:
            haystacks.append(m.group(2))
    # Whole body for "Generated with X" style signature lines.
    haystacks.append(commit["body"])
    blob = "\n".join(haystacks).lower()
    for sub, pretty in AI_SIGNATURES:
        if sub in blob:
            hits.add(pretty)
    return hits


# --- yaml emit (tiny, dependency-free) --------------------------------------
def render_yaml(overall, areas, human_reviewed, tools):
    today = datetime.date.today().isoformat()
    L = []
    L.append("# AI Usage Disclosure — DRAFT generated by ai-usage-gen")
    L.append("# Review every value before committing. Levels and review status")
    L.append("# CANNOT be inferred from git history and are proposed conservatively.")
    L.append('version: "0.1"')
    L.append(f"overall: {overall}    # PROPOSED — confirm")
    L.append("")
    L.append("areas:")
    for area in ["code", "tests", "documentation", "design", "assets", "data"]:
        if area in areas:
            L.append(f"  {area}:")
            L.append(f"    level: {areas[area]}    # PROPOSED — confirm/adjust")
            L.append("    reviewed: false    # CONFIRM — set true only if a human reviewed it")
        else:
            L.append(f"  {area}: none")
    L.append("")
    L.append(f"human_reviewed: {str(human_reviewed).lower()}    # DERIVED — leave to tooling")
    L.append("")
    if tools:
        L.append("tools:")
        for t in sorted(tools):
            L.append(f'  - "{t}"')
    else:
        L.append("tools: []")
    L.append("")
    L.append('disclosed_by: "TODO"')
    L.append(f'updated: "{today}"')
    L.append("notes: >")
    L.append("  TODO — describe in your own words how AI was used and what a human owns.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Draft an ai-usage.yml from git history.")
    ap.add_argument("--repo", default=".", help="repo path (default: .)")
    ap.add_argument("--since", help="git --since date, e.g. 2025-01-01")
    ap.add_argument("--until", help="git --until date")
    ap.add_argument("--default-level", default="collaborative", choices=LEVELS,
                    help="proposed level for AI-touched areas (default: collaborative)")
    ap.add_argument("--write", action="store_true",
                    help="write ai-usage.yml to the target repo root instead of stdout")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.exists():
        sys.exit(f"repo path does not exist: {repo}")

    commits = parse_commits(git_log(str(repo), args.since, args.until))
    if not commits:
        sys.exit("No commits found.")

    area_files = defaultdict(set)   # area -> set(paths) AI touched
    area_commits = defaultdict(set) # area -> set(commit hashes)
    tools = set()
    ai_commit_count = 0

    for c in commits:
        hits = detect_ai(c)
        if not hits:
            continue
        ai_commit_count += 1
        tools |= hits
        for f in c["files"]:
            a = classify(f)
            area_files[a].add(f)
            area_commits[a].add(c["hash"])

    if not area_files:
        sys.exit(f"Scanned {len(commits)} commits — no AI-attributed commits found.\n"
                 "If your agents do not emit Co-authored-by trailers, add them, "
                 "or fill ai-usage.yml by hand.")

    areas = {a: args.default_level for a in area_files}
    present = [areas[a] for a in areas]
    overall = max(present, key=LEVELS.index)
    # Derived: with reviewed defaulting false, human_reviewed is false whenever any AI area exists.
    human_reviewed = False

    yaml_text = render_yaml(overall, areas, human_reviewed, tools)

    # Evidence report -> stderr so stdout stays clean for piping.
    print("── evidence ─────────────────────────────────────────", file=sys.stderr)
    print(f"repo                   : {repo}", file=sys.stderr)
    print(f"commits scanned        : {len(commits)}", file=sys.stderr)
    print(f"AI-attributed commits  : {ai_commit_count}", file=sys.stderr)
    print(f"tools detected         : {', '.join(sorted(tools)) or '—'}", file=sys.stderr)
    for a in sorted(area_files, key=lambda x: -len(area_files[x])):
        print(f"  {a:<14}: {len(area_files[a]):>4} files, "
              f"{len(area_commits[a]):>3} commits", file=sys.stderr)
    print("─────────────────────────────────────────────────────", file=sys.stderr)

    if args.write:
        out_path = repo / "ai-usage.yml"
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(yaml_text)
        print(f"wrote {out_path} (DRAFT — review before committing)", file=sys.stderr)
    else:
        sys.stdout.write(yaml_text)


if __name__ == "__main__":
    main()
