"""Tests for the TASKS.md structure checker."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from textwrap import dedent

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "check_tasks_md.py"
_spec = importlib.util.spec_from_file_location("check_tasks_md", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

VALID = dedent(
    """\
    # Tasks

    ## Unverified proposals

    - [*] An idea nobody reviewed yet

    ## Ordered backlog

    - [*] [Detailed issue](docs/tasks/detailed.md)
        - Blocked on: a live IMAP account

    ## Scheduled

    ## In Progress

    - [*] Something in flight
      <!-- hai:{"id":"simple-1"} -->

    ## Completed / Accepted

    ### Phase 1

    - [ ] [*] Done, awaiting acceptance
    - [x] [*] Accepted

    ## Rules

    - [ ] rule text is not an issue
    """
)


def _write(tmp_path: Path, text: str) -> Path:
    (tmp_path / "docs" / "tasks").mkdir(parents=True)
    (tmp_path / "docs" / "tasks" / "detailed.md").write_text("# Detailed\n")
    path = tmp_path / "TASKS.md"
    path.write_text(text)
    return path


def test_valid_tracker_has_no_problems(tmp_path: Path) -> None:
    assert checker.check(_write(tmp_path, VALID)) == []


def test_real_tracker_is_valid() -> None:
    assert checker.check(Path(__file__).resolve().parent.parent / "TASKS.md") == []


def test_wrong_section_order_is_reported(tmp_path: Path) -> None:
    text = VALID.replace("## Scheduled\n\n## In Progress", "## In Progress\n\n## Scheduled")
    assert any("order" in p for p in checker.check(_write(tmp_path, text)))


def test_duplicate_section_is_reported(tmp_path: Path) -> None:
    text = VALID.replace("## Scheduled\n", "## Scheduled\n\n## Scheduled\n")
    assert any("order" in p for p in checker.check(_write(tmp_path, text)))


def test_issue_under_two_headings_is_reported(tmp_path: Path) -> None:
    text = VALID.replace("## Scheduled\n", "## Scheduled\n\n- [*] Something in flight\n")
    problems = checker.check(_write(tmp_path, text))
    assert any("Something in flight" in p and "Scheduled" in p for p in problems)


def test_duplicate_hai_id_is_reported(tmp_path: Path) -> None:
    text = VALID.replace(
        "## Scheduled\n", '## Scheduled\n\n- [*] Other\n  <!-- hai:{"id":"simple-1"} -->\n'
    )
    assert any("simple-1" in p for p in checker.check(_write(tmp_path, text)))


def test_broken_link_is_reported(tmp_path: Path) -> None:
    text = VALID.replace("docs/tasks/detailed.md", "docs/tasks/missing.md")
    assert any("docs/tasks/missing.md" in p for p in checker.check(_write(tmp_path, text)))


def test_acceptance_checkbox_outside_completed_is_reported(tmp_path: Path) -> None:
    text = VALID.replace("- [*] Something in flight", "- [ ] [*] Something in flight")
    assert any("checkbox" in p for p in checker.check(_write(tmp_path, text)))


def test_missing_acceptance_checkbox_in_completed_is_reported(tmp_path: Path) -> None:
    text = VALID.replace("- [x] [*] Accepted", "- [*] Accepted")
    assert any("checkbox" in p for p in checker.check(_write(tmp_path, text)))


@pytest.mark.parametrize("text, code", [(VALID, 0), (VALID.replace("## Rules", "## Notes"), 1)])
def test_main_exit_code(tmp_path: Path, text: str, code: int) -> None:
    assert checker.main([str(_write(tmp_path, text))]) == code
