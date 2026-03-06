"""JMAP keywords ↔ IMAP flags mapping."""

# Standard JMAP keyword → IMAP system flag mapping
JMAP_TO_IMAP: dict[str, str] = {
    "$seen": "\\Seen",
    "$flagged": "\\Flagged",
    "$answered": "\\Answered",
    "$draft": "\\Draft",
    "$forwarded": "$Forwarded",
}

# Reverse mapping: IMAP flag → JMAP keyword
IMAP_TO_JMAP: dict[str, str] = {v: k for k, v in JMAP_TO_IMAP.items()}


def jmap_keyword_to_imap(keyword: str) -> str:
    """Convert a JMAP keyword to the corresponding IMAP flag string.

    Unknown keywords pass through unchanged — they're custom IMAP keywords
    and must not start with a backslash (system flag prefix).
    """
    return JMAP_TO_IMAP.get(keyword, keyword)


def imap_flag_to_jmap(flag: str) -> str:
    """Convert an IMAP flag string to the corresponding JMAP keyword.

    Unknown flags pass through unchanged.
    """
    return IMAP_TO_JMAP.get(flag, flag)


def imap_flags_to_jmap_keywords(flags: tuple[str, ...]) -> dict[str, bool]:
    """Convert a tuple of IMAP flags to a JMAP keywords dict (all values True)."""
    return {imap_flag_to_jmap(flag): True for flag in flags}
