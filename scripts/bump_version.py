#!/usr/bin/env python3
"""
bump_version.py — Update version across adaptive-harness release files.

Usage:
    python3 scripts/bump_version.py <new_version>

Example:
    python3 scripts/bump_version.py 1.2.0

Updates:
  - .claude-plugin/plugin.json        (version field)
  - .claude-plugin/marketplace.json   (root version + plugins[0].version)
  - CLAUDE.md                         (Current Version line)
"""

import json
import re
import sys
from pathlib import Path


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def validate_semver(version: str) -> bool:
    """Return True if version is a valid X.Y.Z semver string."""
    return bool(SEMVER_RE.match(version))


def bump_plugin_json(repo_root: Path, new_version: str) -> None:
    path = repo_root / ".claude-plugin" / "plugin.json"
    with open(path) as fh:
        data = json.load(fh)
    data["version"] = new_version
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def bump_marketplace_json(repo_root: Path, new_version: str) -> None:
    path = repo_root / ".claude-plugin" / "marketplace.json"
    with open(path) as fh:
        data = json.load(fh)
    data["version"] = new_version
    if "plugins" in data and len(data["plugins"]) > 0:
        data["plugins"][0]["version"] = new_version
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def bump_claude_md(repo_root: Path, new_version: str) -> None:
    path = repo_root / "CLAUDE.md"
    content = path.read_text()
    # Replace the bold version line directly after "### Current Version"
    new_content = re.sub(
        r"(\*\*)\d+\.\d+\.\d+(\*\*)",
        rf"\g<1>{new_version}\g<2>",
        content,
    )
    path.write_text(new_content)


def main() -> int:
    if len(sys.argv) < 2:
        print("Error: no version argument provided.", file=sys.stderr)
        print("Usage: python3 scripts/bump_version.py <new_version>", file=sys.stderr)
        return 1

    new_version = sys.argv[1]

    if not validate_semver(new_version):
        msg = (
            f"Error: invalid semver '{new_version}'. "
            "Expected format: X.Y.Z (e.g. 1.2.3)"
        )
        print(msg, file=sys.stderr)
        return 1

    # Allow running from a different working directory by checking cwd first.
    # If cwd has the expected structure, use it; otherwise fall back to script location.
    cwd = Path.cwd()
    if (cwd / ".claude-plugin" / "plugin.json").exists():
        repo_root = cwd
    else:
        repo_root = Path(__file__).resolve().parent.parent

    bump_plugin_json(repo_root, new_version)
    bump_marketplace_json(repo_root, new_version)
    bump_claude_md(repo_root, new_version)

    print(f"Version bumped to {new_version}")
    print(f"  Updated: .claude-plugin/plugin.json")
    print(f"  Updated: .claude-plugin/marketplace.json (root + plugins[0])")
    print(f"  Updated: CLAUDE.md (Current Version)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
