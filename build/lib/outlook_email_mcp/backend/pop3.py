"""POP3 over TLS read backend with SMTP outbound support.

POP3 is intentionally treated as an inbox-only protocol: it has no folders,
server-side search, or draft storage. Message IDs include a digest so a stale
index cannot silently address a different message after mailbox changes.
"""

from __future__ import annotations

import email
import hashlib
import logging
import mimetypes
import poplib
import smtplib
import ssl
import time
from email import policy as email_policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, getaddresses, parsedate_to_datetime
from pathlib import Path

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


class Pop3Backend:
    name = "pop3"

    def __init__(self, settings: Settings, policy: SafePathPolicy) -> None:
        if not settings.pop3_configured:
            raise ConfigurationError("POP3_HOST, POP3_USERNAME, and POP3 credentials are required")
        if not settings.smtp_configured:
            raise ConfigurationError("SMTP_HOST, SMTP_USERNAME, and SMTP credentials are required")
        self.settings = settings
        self.policy = policy
        self._pop3_password = self._secret("POP3_PASSWORD", settings.pop3_username)
        self._smtp_password = self._secret("SMTP_PASSWORD", settings.smtp_username)

    def _secret(self, name: str, username: str | None) -> str | None:
        if self.settings.credential_backend == "env":
            return getattr(self.settings, name.lower(), None)
        try:
            import keyring  # type: ignore
        except ImportError as exc:
            raise ConfigurationError("install the windows extra to use keyring credentials") from exc
        return keyring.get_password(self.settings.credential_service or "outlook-email-mcp", username or "")

    def close(self) -> None:
        return None

    def status(self) -> dict:
        return {"backend": self.name, "available": True, "transport": "POP3 over TLS and SMTP over TLS", "pop3_host": self.settings.pop3_host, "smtp_host": self.settings.smtp_host}

    def _connect(self) -> poplib.POP3_SSL:
        try:
            client = poplib.POP3_SSL(self.settings.pop3_host, self.settings.pop3_port, timeout=self.settings.network_timeout)
            client.user(self.settings.pop3_username or "")
            client.pass_(self._pop3_password or "")
            return client
        except Exception as exc:
            raise BackendError("POP3 connection or authentication failed") from exc

    @staticmethod
    def _message_id(number: int, raw: bytes) -> str:
        return f"pop3:message:{number}:{hashlib.sha256(raw).hexdigest()[:24]}"

    @staticmethod
    def _parse(raw: bytes) -> email.message.Message:
        return BytesParser(policy=email_policy.default).parsebytes(raw)

    def _raw_messages(self, client: poplib.POP3_SSL, limit: int | None = None) -> list[tuple[int, bytes]]:
        count, _ = client.stat()
        numbers = list(range(max(1, count - (limit or self.settings.max_results) + 1), count + 1))
        result: list[tuple[int, bytes]] = []
        for number in reversed(numbers):
            _, lines, _ = client.retr(number)
            raw = b"\r\n".join(lines)
            if len(raw) > self.settings.max_message_bytes:
                continue
            result.append((number, raw))
        return result

    def list_stores(self) -> list[Store]:
        return [Store("pop3:store:account", self.settings.pop3_username or "POP3 account", self.name)]

    def list_folders(self, store_id: str | None = None) -> list[Folder]:
        if store_id and store_id != "pop3:store:account":
            return []
        return [Folder("pop3:folder:inbox", "INBOX", "pop3:store:account", path="INBOX")]

    def _message(self, number: int, raw: bytes) -> Message:
        parsed = self._parse(raw)
        body = self._body(parsed)
        attachments = self._attachments(parsed)
        date_value = parsed.get("Date")
        try:
            received = parsedate_to_datetime(date_value).isoformat() if date_value else None
        except (TypeError, ValueError):
            received = date_value
        return Message(self._message_id(number, raw), _decode(parsed.get("Subject")), _decode(parsed.get("From")), tuple(a for _, a in getaddresses(parsed.get_all("To", []))), tuple(a for _, a in getaddresses(parsed.get_all("Cc", []))), received, body[: self.settings.max_body_chars], False, bool(attachments), "pop3:folder:inbox", body[:300])

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
        return [Attachment(str(index), _decode(part.get_filename()), part.get_content_type(), len(part.get_payload(decode=True) or b"")) for index, part in enumerate(message.walk()) if part.get_filename()]

    def search(self, query: str, folder_id: str | None, limit: int) -> list[Message]:
        if folder_id and folder_id != "pop3:folder:inbox":
            return []
        parsed = parse_query(query)
        client = self._connect()
        try:
            result = []
            for number, raw in self._raw_messages(client, limit):
                message = self._message(number, raw)
                if parsed.matches(message):
                    result.append(message)
            return result[:limit]
        finally:
            try:
                client.quit()
            except Exception:
                logger.debug("POP3 logout failed", exc_info=True)

    def _resolve(self, client: poplib.POP3_SSL, message_id: str) -> tuple[int, bytes, email.message.Message]:
        parts = message_id.split(":")
        if len(parts) != 5 or parts[0] != "pop3" or parts[1] != "message" or not parts[2].isdigit():
            raise BackendError("invalid POP3 message_id")
        number = int(parts[2])
        _, lines, _ = client.retr(number)
        raw = b"\r\n".join(lines)
        if self._message_id(number, raw) != message_id:
            raise BackendError("POP3 message changed; search again")
        if len(raw) > self.settings.max_message_bytes:
            raise BackendError("message exceeds configured safety limit")
        return number, raw, self._parse(raw)

    def get_message(self, message_id: str, folder_id: str | None = None) -> Message:
        client = self._connect()
        try:
            if folder_id and folder_id != "pop3:folder:inbox":
                raise BackendError("POP3 only exposes INBOX")
            number, raw, _ = self._resolve(client, message_id)
            return self._message(number, raw)
        finally:
            try:
                client.quit()
            except Exception:
                logger.debug("POP3 logout failed", exc_info=True)

    def list_attachments(self, message_id: str, folder_id: str | None = None) -> list[Attachment]:
        client = self._connect()
        try:
            return self._attachments(self._resolve(client, message_id)[2])
        finally:
            try:
                client.quit()
            except Exception:
                logger.debug("POP3 logout failed", exc_info=True)

    def save_attachment(self, message_id: str, attachment_id: str, directory: str, folder_id: str | None = None) -> dict:
        client = self._connect()
        try:
            parsed = self._resolve(client, message_id)[2]
            parts = [(str(i), p) for i, p in enumerate(parsed.walk()) if p.get_filename()]
            part = dict(parts).get(str(attachment_id))
            if part is None:
                raise BackendError("attachment not found")
            payload = part.get_payload(decode=True) or b""
            if len(payload) > self.settings.max_attachment_bytes:
                raise BackendError("attachment exceeds configured safety limit")
            target = self.policy.target(directory, _decode(part.get_filename()))
            self.policy.write_new_file(target, payload)
            return {"path": str(target), "filename": target.name, "size": len(payload)}
        finally:
            try:
                client.quit()
            except Exception:
                logger.debug("POP3 logout failed", exc_info=True)

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
            maintype, subtype = (mimetypes.guess_type(path.name)[0] or "application/octet-stream").split("/", 1)
            message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
        return message

    def create_draft(self, draft: Draft) -> dict:
        raise BackendError("POP3 cannot store drafts; use Outlook or IMAP for create_draft")

    def send_email(self, draft: Draft) -> dict:
        message = self._message_for_draft(draft)
        try:
            if self.settings.smtp_ssl:
                client: smtplib.SMTP = smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=self.settings.network_timeout, context=ssl.create_default_context())
            else:
                client = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=self.settings.network_timeout)
                client.starttls(context=ssl.create_default_context())
            with client:
                client.login(self.settings.smtp_username or "", self._smtp_password or "")
                client.send_message(message, to=[*draft.to, *draft.cc, *draft.bcc])
            return {"sent": True, "recipients": list(draft.to)}
        except Exception as exc:
            raise BackendError("SMTP connection, authentication, or send failed") from exc
