#!/usr/bin/env python3
"""
generate_changelog.py — Generate a structured changelog from git log.

Usage:
    python3 scripts/generate_changelog.py [FROM_TAG] [TO_REF]

Examples:
    python3 scripts/generate_changelog.py v1.0.0 v1.1.0
    python3 scripts/generate_changelog.py v1.0.0 HEAD
    python3 scripts/generate_changelog.py          # All commits on HEAD

Groups commits by conventional prefix:
  feat    → Features
  fix     → Bug Fixes
  chore   → Chores
  docs    → Documentation
  refactor → Refactoring
  test    → Tests
  perf    → Performance
  ci      → CI/CD

Outputs structured markdown to stdout.
"""

import re
import subprocess
import sys
from collections import defaultdict

# Human-readable section titles (ordered for output)
SECTION_ORDER = ["feat", "fix", "refactor", "perf", "docs", "test", "ci", "chore"]

SECTION_TITLES = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "refactor": "Refactoring",
    "perf": "Performance",
    "docs": "Documentation",
    "test": "Tests",
    "ci": "CI/CD",
    "chore": "Chores",
}

COMMIT_PREFIX_RE = re.compile(r"^(feat|fix|chore|docs|refactor|test|perf|ci)(?:\([^)]+\))?: (.+)$")


def get_commits(from_tag: str | None, to_ref: str) -> list[str]:
    """Return list of commit subject lines between from_tag and to_ref."""
    if from_tag:
        rev_range = f"{from_tag}..{to_ref}"
    else:
        rev_range = to_ref

    result = subprocess.run(
        ["git", "log", "--pretty=format:%s", rev_range],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error running git log: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines


def group_commits(commits: list[str]) -> dict[str, list[str]]:
    """Group commit subjects by conventional prefix."""
    groups: dict[str, list[str]] = defaultdict(list)
    for subject in commits:
        m = COMMIT_PREFIX_RE.match(subject)
        if m:
            prefix, message = m.group(1), m.group(2)
            groups[prefix].append(message)
        else:
            groups.setdefault("other", [])
            groups["other"].append(subject)
    return dict(groups)


def format_changelog(
    groups: dict[str, list[str]],
    from_tag: str | None,
    to_ref: str,
) -> str:
    """Format grouped commits as markdown changelog."""
    lines: list[str] = []

    if from_tag:
        lines.append(f"## Changes from {from_tag} to {to_ref}\n")
    else:
        lines.append(f"## Changelog\n")

    has_content = False
    for prefix in SECTION_ORDER:
        entries = groups.get(prefix, [])
        if not entries:
            continue
        has_content = True
        title = SECTION_TITLES[prefix]
        lines.append(f"### {title}\n")
        for entry in entries:
            lines.append(f"- {entry}")
        lines.append("")

    # Uncategorized commits
    other = groups.get("other", [])
    if other:
        has_content = True
        lines.append("### Other\n")
        for entry in other:
            lines.append(f"- {entry}")
        lines.append("")

    if not has_content:
        lines.append("_No changes found._\n")

    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    from_tag: str | None = None
    to_ref = "HEAD"

    if len(args) == 0:
        pass
    elif len(args) == 1:
        from_tag = args[0]
    elif len(args) == 2:
        from_tag = args[0]
        to_ref = args[1]
    else:
        print("Usage: generate_changelog.py [FROM_TAG] [TO_REF]", file=sys.stderr)
        return 1

    commits = get_commits(from_tag, to_ref)
    groups = group_commits(commits)
    changelog = format_changelog(groups, from_tag, to_ref)
    print(changelog)
    return 0


if __name__ == "__main__":
    sys.exit(main())
