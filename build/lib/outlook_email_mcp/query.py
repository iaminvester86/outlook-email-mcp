"""Small deterministic message query language, independent of mail APIs."""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from .errors import QueryError
from .models import Message


@dataclass(frozen=True)
class MessageQuery:
    text: tuple[str, ...] = ()
    sender: str | None = None
    recipient: str | None = None
    subject: str | None = None
    unread: bool | None = None
    has_attachment: bool | None = None

    def matches(self, message: Message) -> bool:
        haystack = " ".join((message.subject, message.sender, *message.to, *message.cc, message.body)).lower()
        if any(term.lower() not in haystack for term in self.text):
            return False
        if self.sender and self.sender.lower() not in message.sender.lower():
            return False
        if self.recipient and not any(self.recipient.lower() in value.lower() for value in (*message.to, *message.cc)):
            return False
        if self.subject and self.subject.lower() not in message.subject.lower():
            return False
        if self.unread is not None and message.unread is not self.unread:
            return False
        if self.has_attachment is not None and message.has_attachments is not self.has_attachment:
            return False
        return True


def parse_query(value: str | None) -> MessageQuery:
    if value and any(ord(char) < 32 for char in value):
        raise QueryError("query cannot contain control characters")
    try:
        tokens = shlex.split(value or "")
    except ValueError as exc:
        raise QueryError("query has unmatched quotes") from exc
    text: list[str] = []
    fields: dict[str, object] = {}
    for token in tokens:
        if ":" not in token:
            text.append(token)
            continue
        key, val = token.split(":", 1)
        key, val = key.lower(), val.strip()
        if any(ord(char) < 32 for char in val):
            raise QueryError("query values cannot contain control characters")
        if key in {"from", "sender"}:
            if not val:
                raise QueryError("from: requires a value")
            fields["sender"] = val
        elif key in {"to", "cc"}:
            if not val:
                raise QueryError("to: requires a value")
            fields["recipient"] = val
        elif key == "subject":
            if not val:
                raise QueryError("subject: requires a value")
            fields["subject"] = val
        elif key == "is" and val in {"read", "unread"}:
            fields["unread"] = val == "unread"
        elif key in {"has", "has_attachment"} and val == "attachment":
            fields["has_attachment"] = True
        else:
            text.append(token)
    return MessageQuery(text=tuple(text), **fields)
