"""mailjail operation policy — allowlist-based.

This is the security core. Keep it simple and auditable.
"""

from typing import Any

# Methods that are unconditionally allowed
ALLOWED_METHODS: frozenset[str] = frozenset(
    {
        "Mailbox/get",
        "Email/query",
        "Email/get",
        "Email/changes",  # Phase 2
    }
)

# Methods with restricted sub-operations
RESTRICTED_METHODS: frozenset[str] = frozenset(
    {
        "Email/set",
        # Intercepted: fakes success but retains the draft instead of sending.
        # Response always includes mailjail:intercepted and mailjail:message.
        "EmailSubmission/set",
    }
)

# Permanently blocked — these methods never exist in this proxy
BLOCKED_METHODS: frozenset[str] = frozenset(
    {
        "Email/copy",
        "EmailSubmission/get",
        "EmailSubmission/query",
        "EmailSubmission/changes",
        "Identity/get",
        "Identity/set",
        "VacationResponse/get",
        "VacationResponse/set",
        "Mailbox/set",  # no folder create/delete/rename
        "Mailbox/changes",
        "Thread/get",  # Phase 2 maybe
        "Thread/changes",
    }
)


def check_email_set(args: dict[str, Any]) -> list[str]:
    """Validate Email/set arguments. Returns list of violations (empty = permitted)."""
    violations: list[str] = []

    if "destroy" in args:
        violations.append("Email/set destroy is forbidden")

    for uid, patch in args.get("update", {}).items():
        for key in patch:
            if not key.startswith("keywords/") and not key.startswith("keywords"):
                violations.append(
                    f"Email/set update only allows keywords/* patches, "
                    f"got '{key}' for message {uid}"
                )
            # Reject mailboxIds changes explicitly
            if key == "mailboxIds" or key.startswith("mailboxIds/"):
                violations.append(
                    f"Email/set update of mailboxIds is forbidden for message {uid}"
                )

    for create_id, obj in args.get("create", {}).items():
        keywords = obj.get("keywords", {})
        if "$draft" not in keywords:
            violations.append(
                f"Email/set create '{create_id}' must include $draft keyword"
            )

    return violations
