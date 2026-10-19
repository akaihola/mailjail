#!/usr/bin/env python3
"""Check the structure of TASKS.md.

Usage: python3 scripts/check_tasks_md.py [TASKS.md]

Verifies that the lifecycle sections appear once and in order, that each
issue bullet sits under exactly one ``##`` heading, that Hai identifiers are
unique, that relative links resolve, that ``[~]`` appears only under
``## In Progress``, and that acceptance checkboxes appear only under
``## Completed / Accepted``. Prints each problem and exits with
status 1 if any was found, else 0.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SECTIONS = [
    "Unverified proposals",
    "Ordered backlog",
    "Scheduled",
    "In Progress",
    "Completed / Accepted",
    "Rules",
]
COMPLETED = "Completed / Accepted"
_BULLET = re.compile(r"^- (\[[ x~]\] )?(\[(?:\*|\d+)\])")
_HAI = re.compile(r"<!-- hai:(\{.*?\}) -->")
_LINK = re.compile(r"\]\((?!https?://|#)([^)\s]+)\)|^\[\d+\]: (\S+)", re.MULTILINE)


def check(path: Path) -> list[str]:
    """Return a list of problems found in the tracker at ``path``."""
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    headings = [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]
    if headings != SECTIONS:
        problems.append(f"section order must be {SECTIONS}, found {headings}")
    issues: dict[str, set[str]] = {}
    hai_ids: dict[str, set[str]] = {}
    heading = ""
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            heading = line[3:].strip()
            continue
        if heading == "Rules" or not heading:
            continue
        match = _HAI.search(line)
        if match:
            hai_ids.setdefault(json.loads(match.group(1))["id"], set()).add(heading)
        if not line.startswith("- "):
            continue
        match = _BULLET.match(line)
        if match is None:
            problems.append(f"line {number}: bullet must start with [*] or [N]: {line}")
            continue
        if match.group(1) == "[~] ":
            if heading != "In Progress":
                problems.append(f"line {number}: in-progress checkbox misplaced in {heading}: {line}")
        elif (heading == COMPLETED) != (match.group(1) is not None):
            problems.append(f"line {number}: acceptance checkbox misplaced in {heading}: {line}")
        issues.setdefault(line[match.end() :].strip(), set()).add(heading)
    for summary, found in issues.items():
        if len(found) > 1:
            problems.append(f"issue under several headings {sorted(found)}: {summary}")
    for hai_id, found in hai_ids.items():
        if len(found) > 1:
            problems.append(f"Hai id {hai_id} under several headings {sorted(found)}")
    for match in _LINK.finditer(text):
        target = match.group(1) or match.group(2)
        if not (path.parent / target).exists():
            problems.append(f"link target does not exist: {target}")
    return problems


def main(argv: list[str]) -> int:
    """Run the check and report; return the process exit status."""
    path = Path(argv[0]) if argv else Path("TASKS.md")
    problems = check(path)
    for problem in problems:
        print(problem)
    if not problems:
        print(f"OK: {path} is well-formed.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
