"""Bounded wire models used by both backends and MCP responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
class Draft:
    to: tuple[str, ...]
    subject: str
    body: str
    cc: tuple[str, ...] = ()
    bcc: tuple[str, ...] = ()
    attachments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "to", _recipients(self.to))
        object.__setattr__(self, "cc", _recipients(self.cc))
        object.__setattr__(self, "bcc", _recipients(self.bcc))
        object.__setattr__(self, "subject", bounded(self.subject, 10_000))
        object.__setattr__(self, "body", bounded(self.body))
        object.__setattr__(self, "attachments", tuple(bounded(p, 4_000) for p in self.attachments)[:MAX_ATTACHMENTS])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    return Draft(tuple(to), data.get("subject", ""), data.get("body", ""), tuple(cc), tuple(bcc), tuple(attachments))
