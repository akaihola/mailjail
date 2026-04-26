"""JMAP filter → IMAP SEARCH translation."""

import datetime
from typing import Any

from imap_tools import AND, NOT, OR

# IMAP SORT criteria names for known JMAP sort properties
_SORT_MAP: dict[str, str] = {
    "receivedAt": "ARRIVAL",
    "sentAt": "DATE",
    "from": "FROM",
    "subject": "SUBJECT",
    "size": "SIZE",
}

# JMAP keywords that map to dedicated IMAP search flags (not KEYWORD/UNKEYWORD)
_KEYWORD_FLAG_MAP: dict[str, str] = {
    "$seen": "seen",
    "$flagged": "flagged",
    "$answered": "answered",
    "$draft": "draft",
}


def jmap_filter_to_imap(filter_cond: dict[str, Any]) -> Any:
    """Translate a JMAP EmailFilterCondition dict to an imap_tools criterion.

    Supports compound operators per RFC 8621 §4.4.1::

        {"operator": "AND" | "OR" | "NOT", "conditions": [<filter>, ...]}

    Returns AND(all=True) for an empty filter or when only inMailbox is
    specified (folder selection is handled externally via mb.folder.set()).
    """
    operator = filter_cond.get("operator")
    if operator is not None:
        conditions = filter_cond.get("conditions") or []
        sub = [jmap_filter_to_imap(c) for c in conditions]
        if operator == "AND":
            if not sub:
                return AND(all=True)
            return AND(*sub)
        if operator == "OR":
            if not sub:
                return AND(all=True)
            if len(sub) == 1:
                return sub[0]
            return OR(*sub)
        if operator == "NOT":
            if not sub:
                return AND(all=True)
            inner = sub[0] if len(sub) == 1 else OR(*sub)
            return NOT(inner)
        raise ValueError(f"unknown filter operator: {operator!r}")

    kwargs: dict[str, Any] = {}

    for key, value in filter_cond.items():
        match key:
            case "from":
                kwargs["from_"] = value
            case "to":
                kwargs["to"] = value
            case "cc":
                kwargs["cc"] = value
            case "bcc":
                kwargs["bcc"] = value
            case "subject":
                kwargs["subject"] = value
            case "body":
                kwargs["body"] = value
            case "text":
                kwargs["text"] = value
            case "after":
                dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
                kwargs["date_gte"] = dt.date()
            case "before":
                dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
                kwargs["date_lt"] = dt.date()
            case "hasKeyword":
                flag_kwarg = _KEYWORD_FLAG_MAP.get(value)
                if flag_kwarg is not None:
                    kwargs[flag_kwarg] = True
                else:
                    kwargs["keyword"] = value
            case "notKeyword":
                flag_kwarg = _KEYWORD_FLAG_MAP.get(value)
                if flag_kwarg is not None:
                    kwargs[flag_kwarg] = False
                else:
                    kwargs["no_keyword"] = value
            case "minSize":
                kwargs["size_gt"] = value
            case "maxSize":
                kwargs["size_lt"] = value
            case "inMailbox":
                # Handled externally by mb.folder.set(); ignore here
                pass
            case _:
                # Unknown filter properties are silently ignored for forward compatibility
                pass

    if not kwargs:
        return AND(all=True)

    return AND(**kwargs)


def jmap_sort_to_imap(sort: list[dict[str, Any]]) -> str | None:
    """Translate JMAP sort spec to IMAP SORT criteria string, or None if empty/unsupported.

    Phase 1: always return None (client-side sort on receivedAt).
    Phase 3 can enable server-side SORT if the server advertises the capability.
    """
    if not sort:
        return None

    # Build IMAP SORT criteria string for the first sort key
    first = sort[0]
    prop = first.get("property", "receivedAt")
    ascending = first.get("isAscending", True)

    imap_key = _SORT_MAP.get(prop)
    if imap_key is None:
        return None

    if ascending:
        return imap_key
    return f"REVERSE {imap_key}"
