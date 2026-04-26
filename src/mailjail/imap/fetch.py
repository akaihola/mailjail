"""IMAP FETCH → JMAP Email translation."""

import re
from typing import Any

from imap_tools import MailMessage

from .flags import imap_flags_to_jmap_keywords


def email_id_to_folder_uid(email_id: str) -> tuple[str, str]:
    """Split 'INBOX:42' → ('INBOX', '42'). Raises ValueError on bad format."""
    parts = email_id.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Invalid email ID format: {email_id!r} — expected 'FOLDER:UID'"
        )
    return parts[0], parts[1]


def folder_uid_to_email_id(folder: str, uid: str) -> str:
    """Build 'INBOX:42' from folder='INBOX', uid='42'."""
    return f"{folder}:{uid}"


_TAG_RE = re.compile(r"<[^>]+>")
_STYLE_OR_SCRIPT_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)
_HTML_ENTITY_MAP = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&apos;": "'",
}


def html_to_text(html: str) -> str:
    """Strip HTML tags / scripts / styles and decode common entities.

    This is a best-effort conversion used for preview text and for
    populating ``textBody`` when an email is HTML-only. It is intentionally
    dependency-free; agents that need full fidelity can request ``htmlBody``
    instead.
    """
    if not html:
        return ""
    cleaned = _STYLE_OR_SCRIPT_RE.sub("", html)
    # Replace block-level breaks with newlines so paragraphs survive.
    cleaned = re.sub(r"<\s*br\s*/?\s*>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</\s*p\s*>", "\n\n", cleaned, flags=re.IGNORECASE)
    cleaned = _TAG_RE.sub("", cleaned)
    for entity, replacement in _HTML_ENTITY_MAP.items():
        cleaned = cleaned.replace(entity, replacement)
    return cleaned


def make_preview(text: str, max_chars: int = 256) -> str:
    """Return the first max_chars characters of text with whitespace collapsed."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed[:max_chars]


def _address_list(addr_values: Any) -> list[dict[str, str]]:
    """Convert imap_tools EmailAddress objects to JMAP address dicts."""
    if addr_values is None:
        return []
    # Handle both single EmailAddress and tuples/lists of them
    if not hasattr(addr_values, "__iter__") or isinstance(addr_values, str):
        items = [addr_values]
    else:
        items = list(addr_values)
    result = []
    for a in items:
        if a is None:
            continue
        result.append(
            {
                "name": getattr(a, "name", "") or "",
                "email": getattr(a, "email", "") or "",
            }
        )
    return result


def imap_message_to_jmap_email(
    msg: MailMessage,
    folder: str,
    properties: list[str] | None = None,
) -> dict[str, Any]:
    """Map imap_tools MailMessage to a JMAP Email dict.

    If properties is None, return all properties.
    'id' is always included regardless of the properties list.
    """
    if msg.uid is None:
        raise ValueError(
            f"MailMessage has no UID — cannot construct email ID for folder {folder!r}"
        )

    email_id = folder_uid_to_email_id(folder, msg.uid)

    # Build full property map
    full: dict[str, Any] = {
        "id": email_id,
        "blobId": email_id,  # Phase 1 simplification
        "threadId": email_id,  # Phase 1 simplification — no thread grouping
        "mailboxIds": {folder: True},
        "keywords": imap_flags_to_jmap_keywords(msg.flags),
        "from": _address_list([msg.from_values] if msg.from_values is not None else []),
        "to": _address_list(msg.to_values),
        "cc": _address_list(msg.cc_values),
        "bcc": _address_list(msg.bcc_values),
        "replyTo": _address_list(msg.reply_to_values),
        "subject": msg.subject or "",
        "sentAt": msg.date.isoformat() if msg.date else None,
        "receivedAt": msg.date.isoformat() if msg.date else None,
        "size": msg.size_rfc822,
        "preview": make_preview(msg.text or html_to_text(msg.html or "")),
        "hasAttachment": bool(msg.attachments),
        "headers": [
            {"name": k, "value": v} for k, vs in (msg.headers or {}).items() for v in vs
        ],
        "textBody": [],
        "htmlBody": [],
        "bodyValues": {},
    }

    # Build body parts. If the message is HTML-only, derive a plain-text
    # rendering so agents that only request textBody still get readable
    # content.
    text = msg.text
    if not text and msg.html:
        text = html_to_text(msg.html)
    if text:
        full["textBody"] = [{"partId": "1", "type": "text/plain"}]
        full["bodyValues"]["1"] = {
            "value": text,
            "isEncodingProblem": False,
            "isTruncated": False,
        }
    if msg.html:
        full["htmlBody"] = [{"partId": "2", "type": "text/html"}]
        full["bodyValues"]["2"] = {
            "value": msg.html,
            "isEncodingProblem": False,
            "isTruncated": False,
        }

    if properties is None:
        return full

    # Filter to requested properties, always include 'id'
    result: dict[str, Any] = {"id": email_id}
    for prop in properties:
        if prop in full and prop != "id":
            result[prop] = full[prop]
    return result
