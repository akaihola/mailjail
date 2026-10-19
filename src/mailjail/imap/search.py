"""Plan a JMAP Email/query as one IMAP SEARCH or SORT in one folder."""

import datetime
from typing import Any

from imap_tools import AND, NOT, OR
from pydantic import BaseModel

from ..models.core import JMAPErrorType

# Folder searched when the filter names no inMailbox
DEFAULT_FOLDER = "INBOX"

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


class QueryPlan(BaseModel):
    """One IMAP command in one folder that answers an Email/query."""

    folder: str
    criterion: str
    sort: list[str]  # IMAP SORT keys; empty means SEARCH, which yields UID order
    reverse: bool  # reverse the UID order SEARCH yields


class UnsupportedQuery(ValueError):
    """A filter or sort that one IMAP command in one folder cannot answer."""

    def __init__(self, type_: JMAPErrorType, description: str) -> None:
        super().__init__(description)
        self.type = type_


def plan_query(
    filter_cond: dict[str, Any],
    sort: list[dict[str, Any]],
    *,
    server_sort: bool,
) -> QueryPlan:
    """Plan an Email/query, or raise UnsupportedQuery.

    One pass over the filter both translates it and collects the folder, so
    no condition is dropped. ``inMailbox`` is honoured where it bounds the
    whole query (top level or under AND) and rejected under OR and NOT.
    ``server_sort`` says whether the server has the IMAP SORT extension;
    without it only a single receivedAt comparator is supported, by UID order.
    """
    folders: set[str] = set()
    criterion = str(_criterion(filter_cond, folders, bounds_query=True))
    if len(folders) > 1:
        raise UnsupportedQuery(
            JMAPErrorType.UNSUPPORTED_FILTER,
            f"a query searches one mailbox; inMailbox names {sorted(folders)}",
        )
    folder = folders.pop() if folders else DEFAULT_FOLDER

    if not sort:
        return QueryPlan(folder=folder, criterion=criterion, sort=[], reverse=True)
    if server_sort:
        keys = [_sort_key(comparator) for comparator in sort]
        return QueryPlan(folder=folder, criterion=criterion, sort=keys, reverse=False)
    if len(sort) == 1 and sort[0].get("property") == "receivedAt":
        reverse = not sort[0].get("isAscending", True)
        return QueryPlan(folder=folder, criterion=criterion, sort=[], reverse=reverse)
    raise UnsupportedQuery(
        JMAPErrorType.UNSUPPORTED_SORT,
        "without the IMAP SORT extension only one receivedAt comparator is supported",
    )


def _sort_key(comparator: dict[str, Any]) -> str:
    """Translate one JMAP Comparator to an IMAP SORT key."""
    prop = comparator.get("property")
    key = _SORT_MAP.get(prop)
    if key is None:
        raise UnsupportedQuery(
            JMAPErrorType.UNSUPPORTED_SORT, f"unsupported sort property: {prop!r}"
        )
    return key if comparator.get("isAscending", True) else f"REVERSE {key}"


def _criterion(
    filter_cond: dict[str, Any], folders: set[str], bounds_query: bool
) -> Any:
    """Translate a JMAP FilterOperator or FilterCondition to an imap_tools criterion.

    Adds each inMailbox to ``folders``. ``bounds_query`` is false under OR
    and NOT, where a folder condition would need a cross-folder search.
    """
    operator = filter_cond.get("operator")
    if operator is not None:
        if operator not in ("AND", "OR", "NOT"):
            raise UnsupportedQuery(
                JMAPErrorType.UNSUPPORTED_FILTER,
                f"unknown filter operator: {operator!r}",
            )
        extra = sorted(set(filter_cond) - {"operator", "conditions"})
        if extra:
            raise UnsupportedQuery(
                JMAPErrorType.UNSUPPORTED_FILTER,
                f"a filter with an operator takes only conditions, not {extra}",
            )
        bounds = bounds_query and operator == "AND"
        conditions = filter_cond.get("conditions") or []
        sub = [_criterion(c, folders, bounds) for c in conditions]
        if not sub:
            # AND and NOT of no conditions match every message, OR matches none
            return NOT(AND(all=True)) if operator == "OR" else AND(all=True)
        if operator == "AND":
            return AND(*sub)
        inner = sub[0] if len(sub) == 1 else OR(*sub)
        return inner if operator == "OR" else NOT(inner)

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
                # IMAP SINCE/BEFORE compare dates only: the time of day is dropped
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
                if not bounds_query:
                    raise UnsupportedQuery(
                        JMAPErrorType.UNSUPPORTED_FILTER,
                        "inMailbox under OR or NOT would need a cross-folder search",
                    )
                folders.add(value)
            case _:
                raise UnsupportedQuery(
                    JMAPErrorType.UNSUPPORTED_FILTER,
                    f"unsupported filter property: {key!r}",
                )

    if not kwargs:
        return AND(all=True)

    return AND(**kwargs)
