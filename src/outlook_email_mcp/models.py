"""Bounded wire models used by both backends and MCP responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from email.headerregistry import Address
from email.utils import getaddresses
from typing import Any

MAX_STRING = 200_000
MAX_RECIPIENTS = 100
MAX_ATTACHMENTS = 100


def bounded(value: Any, limit: int = MAX_STRING) -> str:
    text = "" if value is None else str(value)
    return text[:limit]


def _recipients(values: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    return tuple(bounded(v, 320) for v in (values or ()) if str(v).strip())[:MAX_RECIPIENTS]


@dataclass(frozen=True)
class Store:
    id: str
    name: str
    provider: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Folder:
    id: str
    name: str
    store_id: str
    parent_id: str | None = None
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Attachment:
    id: str
    filename: str
    content_type: str = "application/octet-stream"
    size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Message:
    id: str
    subject: str
    sender: str
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    received_at: str | None = None
    body: str = ""
    unread: bool = False
    has_attachments: bool = False
    folder_id: str | None = None
    preview: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", bounded(self.id, 1024))
        object.__setattr__(self, "subject", bounded(self.subject, 10_000))
        object.__setattr__(self, "sender", bounded(self.sender, 1_000))
        object.__setattr__(self, "to", _recipients(self.to))
        object.__setattr__(self, "cc", _recipients(self.cc))
        object.__setattr__(self, "body", bounded(self.body))
        object.__setattr__(self, "preview", bounded(self.preview, 1_000))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AttachmentPayload:
    filename: str
    data: bytes = field(repr=False)


@dataclass(frozen=True)
class Draft:
    to: tuple[str, ...]
    subject: str
    body: str
    cc: tuple[str, ...] = ()
    bcc: tuple[str, ...] = ()
    attachments: tuple[str, ...] = ()
    payloads: tuple[AttachmentPayload, ...] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if sum(len(v) for v in (self.to, self.cc, self.bcc)) > MAX_RECIPIENTS:
            raise ValueError("too many recipients")
        for value in (*self.to, *self.cc, *self.bcc):
            if not isinstance(value, str) or len(value) > 320 or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError("invalid recipient")
            parsed = getaddresses([value])
            if len(parsed) != 1 or "@" not in parsed[0][1]:
                raise ValueError("each recipient must contain exactly one email address")
            try:
                Address(addr_spec=parsed[0][1])
            except (ValueError, IndexError) as exc:
                raise ValueError("invalid recipient address") from exc
        if (
            not isinstance(self.subject, str)
            or len(self.subject) > 10_000
            or any(ord(c) < 32 or ord(c) == 127 for c in self.subject)
        ):
            raise ValueError("invalid subject")
        if not isinstance(self.body, str) or len(self.body) > MAX_STRING:
            raise ValueError("draft body exceeds the safety limit")
        if len(self.attachments) > MAX_ATTACHMENTS or any(
            not isinstance(p, str) or len(p) > 4_000 for p in self.attachments
        ):
            raise ValueError("invalid attachment list")
        object.__setattr__(self, "to", tuple(getaddresses([v])[0][1] for v in self.to))
        object.__setattr__(self, "cc", tuple(getaddresses([v])[0][1] for v in self.cc))
        object.__setattr__(self, "bcc", tuple(getaddresses([v])[0][1] for v in self.bcc))
        object.__setattr__(self, "subject", bounded(self.subject, 10_000))
        object.__setattr__(self, "body", bounded(self.body))
        object.__setattr__(self, "attachments", tuple(bounded(p, 4_000) for p in self.attachments)[:MAX_ATTACHMENTS])

    def to_dict(self) -> dict[str, Any]:
        return {
            "to": self.to,
            "subject": self.subject,
            "body": self.body,
            "cc": self.cc,
            "bcc": self.bcc,
            "attachments": self.attachments,
        }


def draft_from_dict(data: dict[str, Any]) -> Draft:
    if not isinstance(data, dict):
        raise ValueError("draft must be an object")
    to = data.get("to", ())
    if isinstance(to, str):
        to = (to,)
    cc = data.get("cc", ())
    bcc = data.get("bcc", ())
    attachments = data.get("attachments", ())
    if isinstance(cc, str):
        cc = (cc,)
    if isinstance(bcc, str):
        bcc = (bcc,)
    if isinstance(attachments, str):
        attachments = (attachments,)
    if not to:
        raise ValueError("draft requires at least one recipient")
    if not all(isinstance(value, (list, tuple)) for value in (to, cc, bcc, attachments)):
        raise ValueError("recipients and attachments must be strings or arrays")
    return Draft(tuple(to), data.get("subject", ""), data.get("body", ""), tuple(cc), tuple(bcc), tuple(attachments))
