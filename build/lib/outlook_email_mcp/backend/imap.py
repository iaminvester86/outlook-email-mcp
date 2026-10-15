"""TLS-only IMAP/SMTP fallback backend using Python's standard library."""

from __future__ import annotations

import email
import imaplib
import logging
import mimetypes
import os
import smtplib
import ssl
import time
from email import policy as email_policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any

from ..config import Settings
from ..errors import BackendError, ConfigurationError
from ..models import Attachment, Draft, Folder, Message, Store
from ..policy import SafePathPolicy
from ..query import parse_query

logger = logging.getLogger(__name__)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    return str(email.header.make_header(email.header.decode_header(value)))


def _imap_quote(value: str) -> str:
    """Quote a search value without allowing IMAP command syntax injection."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class ImapBackend:
    name = "imap"

    def __init__(self, settings: Settings, policy: SafePathPolicy) -> None:
        if not settings.imap_configured:
            raise ConfigurationError("IMAP_HOST, IMAP_USERNAME, and IMAP_PASSWORD are required")
        if not settings.smtp_configured:
            raise ConfigurationError("SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD are required")
        settings.validate()
        self.settings = settings
        self.policy = policy
        self._imap_password = self._secret("IMAP_PASSWORD")
        self._smtp_password = self._secret("SMTP_PASSWORD")

    def _secret(self, name: str) -> str | None:
        if self.settings.credential_backend == "env":
            return getattr(self.settings, name.lower(), None)
        try:
            import keyring  # type: ignore
        except ImportError as exc:
            raise ConfigurationError("install the windows extra to use keyring credentials") from exc
        username = self.settings.imap_username if name.startswith("IMAP") else self.settings.smtp_username
        return keyring.get_password(self.settings.credential_service or "outlook-email-mcp", username or "")

    def close(self) -> None:
        return None

    def status(self) -> dict:
        return {
            "backend": self.name,
            "available": True,
            "transport": "IMAP over TLS and SMTP over TLS",
            "imap_host": self.settings.imap_host,
            "smtp_host": self.settings.smtp_host,
        }

    def _connect(self) -> imaplib.IMAP4_SSL:
        try:
            client = imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port, timeout=self.settings.network_timeout, ssl_context=ssl.create_default_context())
            client.login(self.settings.imap_username or "", self._imap_password or "")
            return client
        except Exception as exc:
            raise BackendError("IMAP connection or authentication failed") from exc

    @staticmethod
    def _folder_id(name: str) -> str:
        return "imap:folder:" + name.encode("utf-8").hex()

    @staticmethod
    def _folder_name(folder_id: str | None, default: str) -> str:
        if not folder_id:
            return default
        prefix = "imap:folder:"
        if not folder_id.startswith(prefix):
            raise BackendError("invalid IMAP folder_id")
        try:
            return bytes.fromhex(folder_id[len(prefix):]).decode("utf-8")
        except ValueError as exc:
            raise BackendError("invalid IMAP folder_id") from exc

    @staticmethod
    def _logout(client: imaplib.IMAP4_SSL) -> None:
        try:
            client.logout()
        except Exception:
            logger.debug("IMAP logout failed", exc_info=True)

    def list_stores(self) -> list[Store]:
        return [Store("imap:store:account", self.settings.imap_username or "IMAP account", self.name)]

    def list_folders(self, store_id: str | None = None) -> list[Folder]:
        if store_id and store_id != "imap:store:account":
            return []
        client = self._connect()
        try:
            typ, rows = client.list()
            if typ != "OK":
                raise BackendError("IMAP folder listing failed")
            result: list[Folder] = []
            for row in rows or []:
                text = row.decode("utf-8", "replace") if isinstance(row, bytes) else str(row)
                name = text.rsplit(' "', 1)[-1].strip('"')
                if name:
                    result.append(Folder(self._folder_id(name), name.rsplit("/", 1)[-1], "imap:store:account", path=name))
            return result
        finally:
            self._logout(client)

    def _select(self, client: imaplib.IMAP4_SSL, folder_id: str | None) -> str:
        folder = self._folder_name(folder_id, self.settings.default_mailbox)
        typ, _ = client.select(folder, readonly=True)
        if typ != "OK":
            raise BackendError("IMAP mailbox selection failed")
        return folder

    def _criteria(self, query: str) -> list[str]:
        parsed = parse_query(query)
        criteria: list[str] = []
        if parsed.sender:
            criteria.extend(["FROM", _imap_quote(parsed.sender)])
        if parsed.recipient:
            criteria.extend(["TO", _imap_quote(parsed.recipient)])
        if parsed.subject:
            criteria.extend(["SUBJECT", _imap_quote(parsed.subject)])
        if parsed.unread is True:
            criteria.append("UNSEEN")
        elif parsed.unread is False:
            criteria.append("SEEN")
        if parsed.has_attachment:
            criteria.extend(["TEXT", _imap_quote("Content-Disposition: attachment")])
        for term in parsed.text:
            criteria.extend(["TEXT", _imap_quote(term)])
        return criteria or ["ALL"]

    def search(self, query: str, folder_id: str | None, limit: int) -> list[Message]:
        client = self._connect()
        try:
            folder = self._select(client, folder_id)
            typ, data = client.uid("SEARCH", None, *self._criteria(query))
            if typ != "OK":
                raise BackendError("IMAP search failed")
            uids = (data[0] or b"").split() if data else []
            result: list[Message] = []
            for uid in reversed(uids[-limit:]):
                message = self._fetch_message(client, uid, folder)
                if message:
                    result.append(message)
            return result
        finally:
            self._logout(client)

    def _fetch_raw(self, client: imaplib.IMAP4_SSL, uid: bytes | str) -> bytes:
        uid_text = uid.decode("ascii") if isinstance(uid, bytes) else str(uid)
        if not uid_text.isdigit():
            raise BackendError("invalid IMAP message identifier")
        typ, data = client.uid("FETCH", uid, "(RFC822)")
        if typ != "OK" or not data:
            raise BackendError("IMAP message fetch failed")
        for item in data:
            if isinstance(item, tuple) and isinstance(item[1], bytes):
                if len(item[1]) > self.settings.max_message_bytes:
                    raise BackendError("message exceeds configured safety limit")
                return item[1]
        raise BackendError("IMAP message body was empty")

    def _fetch_message(self, client: imaplib.IMAP4_SSL, uid: bytes | str, folder: str) -> Message | None:
        raw = self._fetch_raw(client, uid)
        parsed = BytesParser(policy=email_policy.default).parsebytes(raw)
        body = self._body(parsed)
        attachments = self._attachments(parsed)
        date_value = parsed.get("Date")
        try:
            received = parsedate_to_datetime(date_value).isoformat() if date_value else None
        except (TypeError, ValueError):
            received = date_value
        uid_text = uid.decode() if isinstance(uid, bytes) else str(uid)
        return Message(
            id=f"imap:message:{self._folder_id(folder)}:{uid_text}", subject=_decode(parsed.get("Subject")),
            sender=_decode(parsed.get("From")), to=tuple(addr for _, addr in getaddresses(parsed.get_all("To", []))),
            cc=tuple(addr for _, addr in getaddresses(parsed.get_all("Cc", []))), received_at=received,
            body=body, unread=False, has_attachments=bool(attachments), folder_id=self._folder_id(folder), preview=body[:300],
        )

    @staticmethod
    def _body(message: email.message.Message) -> str:
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain" and not part.get_filename():
                    return part.get_content()
            return ""
        return message.get_content() if message.get_content_type() == "text/plain" else ""

    @staticmethod
    def _attachments(message: email.message.Message) -> list[Attachment]:
        result = []
        for index, part in enumerate(message.walk()):
            filename = part.get_filename()
            if filename:
                payload = part.get_payload(decode=True) or b""
                result.append(Attachment(str(index), _decode(filename), part.get_content_type(), len(payload)))
        return result

    def _resolve_message(self, client: imaplib.IMAP4_SSL, message_id: str, folder_id: str | None) -> tuple[bytes, str, email.message.Message]:
        prefix = "imap:message:"
        if not message_id.startswith(prefix):
            raise BackendError("invalid IMAP message_id")
        rest = message_id[len(prefix):]
        encoded_folder, _, uid = rest.rpartition(":")
        if not uid.isdigit():
            raise BackendError("invalid IMAP message identifier")
        folder = self._folder_name(encoded_folder, self.settings.default_mailbox)
        if folder_id and self._folder_name(folder_id, folder) != folder:
            raise BackendError("message does not belong to folder")
        self._select(client, self._folder_id(folder))
        raw = self._fetch_raw(client, uid.encode())
        return uid.encode(), folder, BytesParser(policy=email_policy.default).parsebytes(raw)

    def get_message(self, message_id: str, folder_id: str | None = None) -> Message:
        client = self._connect()
        try:
            uid, folder, parsed = self._resolve_message(client, message_id, folder_id)
            body = self._body(parsed)
            return Message(message_id, _decode(parsed.get("Subject")), _decode(parsed.get("From")), tuple(a for _, a in getaddresses(parsed.get_all("To", []))), tuple(a for _, a in getaddresses(parsed.get_all("Cc", []))), parsed.get("Date"), body, False, bool(self._attachments(parsed)), self._folder_id(folder), body[:300])
        finally:
            self._logout(client)

    def list_attachments(self, message_id: str, folder_id: str | None = None) -> list[Attachment]:
        client = self._connect()
        try:
            _, _, parsed = self._resolve_message(client, message_id, folder_id)
            return self._attachments(parsed)
        finally:
            self._logout(client)

    def save_attachment(self, message_id: str, attachment_id: str, directory: str, folder_id: str | None = None) -> dict:
        client = self._connect()
        try:
            _, _, parsed = self._resolve_message(client, message_id, folder_id)
            parts = [(str(i), p) for i, p in enumerate(parsed.walk()) if p.get_filename()]
            part = dict(parts).get(str(attachment_id))
            if part is None:
                raise BackendError("attachment not found")
            payload = part.get_payload(decode=True) or b""
            if len(payload) > self.settings.max_attachment_bytes:
                raise BackendError("attachment exceeds configured safety limit")
            filename = _decode(part.get_filename())
            target = self.policy.target(directory, filename)
            self.policy.write_new_file(target, payload)
            return {"path": str(target), "filename": filename, "size": len(payload)}
        finally:
            self._logout(client)

    def _message_for_draft(self, draft: Draft) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from or self.settings.smtp_username or ""
        message["To"] = ", ".join(draft.to)
        if draft.cc:
            message["Cc"] = ", ".join(draft.cc)
        message["Subject"] = draft.subject
        message["Date"] = formatdate(localtime=True)
        message.set_content(draft.body)
        for path_text in draft.attachments:
            path = self.policy.attachment(path_text, self.settings.max_attachment_bytes)
            data = path.read_bytes()
            maintype, subtype = (mimetypes.guess_type(path.name)[0] or "application/octet-stream").split("/", 1)
            message.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        return message

    def create_draft(self, draft: Draft) -> dict:
        client = self._connect()
        try:
            message = self._message_for_draft(draft)
            typ, _ = client.append("Drafts", "\\Draft", imaplib.Time2Internaldate(time.time()), message.as_bytes())
            if typ != "OK":
                raise BackendError("IMAP draft creation failed")
            return {"created": True, "folder": "Drafts", "recipients": list(draft.to)}
        finally:
            self._logout(client)

    def send_email(self, draft: Draft) -> dict:
        message = self._message_for_draft(draft)
        try:
            if self.settings.smtp_ssl:
                client: smtplib.SMTP = smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, context=ssl.create_default_context())
            else:
                client = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port)
                client.starttls(context=ssl.create_default_context())
            with client:
                client.login(self.settings.smtp_username or "", self._smtp_password or "")
                client.send_message(message, to=[*draft.to, *draft.cc, *draft.bcc])
            return {"sent": True, "recipients": list(draft.to)}
        except Exception as exc:
            raise BackendError("SMTP connection, authentication, or send failed") from exc
