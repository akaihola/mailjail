"""Draft composition (RFC 2822 / MIME) and IMAP APPEND."""

import datetime
import email.message
import email.policy
import logging
import re
from typing import Any

from imap_tools import MailBox, MailMessageFlags

from .fetch import folder_uid_to_email_id

logger = logging.getLogger(__name__)


def _format_message_id(mid: str) -> str:
    """Wrap a bare JMAP message-id in angle brackets for RFC 5322 headers."""
    mid = mid.strip()
    if mid.startswith("<") and mid.endswith(">"):
        return mid
    return f"<{mid}>"


def _format_address(addr: dict[str, Any]) -> str:
    """Format an address dict {'name': ..., 'email': ...} as an RFC 2822 address."""
    name = addr.get("name", "")
    email_addr = addr.get("email", "")
    if name:
        return f"{name} <{email_addr}>"
    return email_addr


def compose_draft(
    create_obj: dict[str, Any],
    from_address: str,
) -> bytes:
    """Build RFC 2822 message bytes from a JMAP Email/set create object.

    Supports text/plain body (textBody + bodyValues).
    Copies any explicit headers from create_obj["headers"] list.
    """
    msg = email.message.EmailMessage(policy=email.policy.SMTP)

    # From header — prefer the create_obj's from field
    from_addrs = create_obj.get("from", [])
    if from_addrs:
        msg["From"] = _format_address(from_addrs[0])
    else:
        msg["From"] = from_address

    # To header
    to_addrs = create_obj.get("to", [])
    if to_addrs:
        msg["To"] = ", ".join(_format_address(a) for a in to_addrs)

    # Cc header
    cc_addrs = create_obj.get("cc", [])
    if cc_addrs:
        msg["Cc"] = ", ".join(_format_address(a) for a in cc_addrs)

    # Subject
    subject = create_obj.get("subject", "")
    msg["Subject"] = subject

    # MIME-Version is set automatically by EmailMessage with SMTP policy
    msg["MIME-Version"] = "1.0"

    # Reply threading: JMAP exposes ``inReplyTo`` / ``references`` (RFC 8621
    # §4.1.4) as lists of bare message-ids without angle brackets. Convert to
    # the angle-bracket form RFC 5322 expects for In-Reply-To / References.
    in_reply_to = create_obj.get("inReplyTo") or []
    references = create_obj.get("references") or []
    if in_reply_to:
        msg["In-Reply-To"] = " ".join(_format_message_id(mid) for mid in in_reply_to)
    if references:
        msg["References"] = " ".join(_format_message_id(mid) for mid in references)

    # Extra headers (e.g. explicit In-Reply-To, References, Message-ID overrides)
    for header in create_obj.get("headers", []):
        name = header.get("name", "")
        value = header.get("value", "")
        if name and value:
            msg[name] = value

    # Body content
    body_values = create_obj.get("bodyValues", {})
    text_body_parts = create_obj.get("textBody", [])
    html_body_parts = create_obj.get("htmlBody", [])

    if text_body_parts and html_body_parts:
        # Multipart/alternative
        text_part_id = text_body_parts[0].get("partId", "")
        html_part_id = html_body_parts[0].get("partId", "")
        text_content = body_values.get(text_part_id, {}).get("value", "")
        html_content = body_values.get(html_part_id, {}).get("value", "")

        msg.make_alternative()
        msg.add_alternative(text_content, subtype="plain", charset="utf-8")
        msg.add_alternative(html_content, subtype="html", charset="utf-8")
    elif text_body_parts:
        part_id = text_body_parts[0].get("partId", "")
        body_text = body_values.get(part_id, {}).get("value", "")
        msg.set_content(body_text, subtype="plain", charset="utf-8")
    elif html_body_parts:
        part_id = html_body_parts[0].get("partId", "")
        body_html = body_values.get(part_id, {}).get("value", "")
        msg.set_content(body_html, subtype="html", charset="utf-8")

    return bytes(msg)


def append_draft(
    mb: MailBox,
    folder: str,
    message_bytes: bytes,
) -> str:
    """APPEND message_bytes to folder with \\Draft flag.

    Returns the email_id of the appended message.
    Primary path: parse APPENDUID from server response.
    Fallback: STATUS UIDNEXT before/after comparison.
    """
    # Get UIDNEXT before append as fallback
    pre_status = mb.folder.status(folder)
    pre_uidnext = pre_status.get("UIDNEXT", 1)

    # Append to folder with Draft and Seen flags
    result = mb.append(
        message_bytes,
        folder=folder,
        dt=datetime.datetime.now().astimezone(),
        flag_set=[MailMessageFlags.DRAFT, MailMessageFlags.SEEN],
    )

    # Try to parse APPENDUID from untagged responses (Dovecot and many servers)
    uid: int | None = None
    for key, responses in mb.client.untagged_responses.items():
        pass  # untagged_responses is a dict of {type: [data]}

    # Look for APPENDUID in the raw response
    # result is a tuple like ('OK', [b'[APPENDUID 1234567890 42]'])
    if result:
        for item in result:
            if isinstance(item, (list, tuple)):
                for part in item:
                    if isinstance(part, bytes):
                        match = re.search(rb"\[APPENDUID\s+\d+\s+(\d+)\]", part)
                        if match:
                            uid = int(match.group(1))
                            break
            if uid is not None:
                break

    if uid is None:
        # Fallback: use pre-append UIDNEXT (Dovecot assigns UIDs sequentially)
        uid = pre_uidnext

    return folder_uid_to_email_id(folder, str(uid))
