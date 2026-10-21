"""Environment-backed configuration with conservative defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigurationError


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError("invalid boolean setting; use true or false")


def _int(name: str, value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        result = default if value is None else int(value)
    except ValueError as exc:
        raise ConfigurationError(f"invalid integer setting {name}") from exc
    if not minimum <= result <= maximum:
        raise ConfigurationError(f"setting {name} must be between {minimum} and {maximum}")
    return result


@dataclass(frozen=True)
class Settings:
    backend: str = "auto"
    pop3_host: str | None = None
    pop3_port: int = 995
    pop3_username: str | None = None
    pop3_password: str | None = field(default=None, repr=False)
    pop3_tls: bool = True
    imap_host: str | None = None
    imap_port: int = 993
    imap_username: str | None = None
    imap_password: str | None = field(default=None, repr=False)
    imap_tls: bool = True
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = field(default=None, repr=False)
    smtp_from: str | None = None
    smtp_tls: bool = True
    smtp_ssl: bool = False
    default_mailbox: str = "INBOX"
    max_results: int = 50
    max_body_chars: int = 20000
    max_attachment_bytes: int = 25 * 1024 * 1024
    max_message_bytes: int = 50 * 1024 * 1024
    allowed_save_roots: tuple[Path, ...] = ()
    allowed_attachment_roots: tuple[Path, ...] = ()
    transport: str = "stdio"
    http_host: str = "127.0.0.1"
    http_port: int = 8000
    http_path: str = "/mcp"
    http_token: str | None = field(default=None, repr=False)
    enable_drafts: bool = False
    enable_send: bool = False
    allowed_outlook_stores: tuple[str, ...] = ()
    outlook_send_account: str | None = None
    approval_timeout: int = 120
    credential_backend: str = "env"
    credential_service: str | None = None
    network_timeout: int = 30

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        backend = env.get("OUTLOOK_EMAIL_BACKEND", env.get("EMAIL_BACKEND", "auto")).strip().lower()
        if backend == "imap-smtp":
            backend = "imap"
        if backend == "pop3-smtp":
            backend = "pop3"
        if backend not in {"auto", "outlook", "imap", "pop3"}:
            raise ConfigurationError("OUTLOOK_EMAIL_BACKEND must be auto, outlook, imap, or pop3")
        roots = tuple(
            Path(p).expanduser() for p in env.get("OUTLOOK_EMAIL_SAVE_ROOTS", "").split(os.pathsep) if p.strip()
        )
        attachment_roots = tuple(
            Path(p).expanduser() for p in env.get("OUTLOOK_EMAIL_ATTACHMENT_ROOTS", "").split(os.pathsep) if p.strip()
        )
        settings = cls(
            backend=backend,
            pop3_host=env.get("POP3_HOST") or None,
            pop3_port=_int("POP3_PORT", env.get("POP3_PORT"), 995, 1, 65535),
            pop3_username=env.get("POP3_USERNAME") or None,
            pop3_password=env.get("POP3_PASSWORD"),
            pop3_tls=_bool(env.get("POP3_TLS"), True),
            imap_host=env.get("IMAP_HOST") or None,
            imap_port=_int("IMAP_PORT", env.get("IMAP_PORT"), 993, 1, 65535),
            imap_username=env.get("IMAP_USERNAME") or None,
            imap_password=env.get("IMAP_PASSWORD"),
            imap_tls=_bool(env.get("IMAP_TLS"), True),
            smtp_host=env.get("SMTP_HOST") or None,
            smtp_port=_int("SMTP_PORT", env.get("SMTP_PORT"), 587, 1, 65535),
            smtp_username=env.get("SMTP_USERNAME") or None,
            smtp_password=env.get("SMTP_PASSWORD"),
            smtp_from=env.get("SMTP_FROM") or None,
            smtp_tls=_bool(env.get("SMTP_TLS"), True),
            smtp_ssl=_bool(env.get("SMTP_SSL"), False),
            default_mailbox=env.get("IMAP_MAILBOX", "INBOX"),
            max_results=_int("OUTLOOK_EMAIL_MAX_RESULTS", env.get("OUTLOOK_EMAIL_MAX_RESULTS"), 50, 1, 500),
            max_body_chars=_int(
                "OUTLOOK_EMAIL_MAX_BODY_CHARS", env.get("OUTLOOK_EMAIL_MAX_BODY_CHARS"), 20000, 100, 1_000_000
            ),
            max_attachment_bytes=_int(
                "OUTLOOK_EMAIL_MAX_ATTACHMENT_BYTES",
                env.get("OUTLOOK_EMAIL_MAX_ATTACHMENT_BYTES", env.get("MCP_MAX_ATTACHMENT_BYTES")),
                25 * 1024 * 1024,
                1,
                500 * 1024 * 1024,
            ),
            max_message_bytes=_int(
                "OUTLOOK_EMAIL_MAX_MESSAGE_BYTES",
                env.get("OUTLOOK_EMAIL_MAX_MESSAGE_BYTES"),
                50 * 1024 * 1024,
                1_000,
                500 * 1024 * 1024,
            ),
            allowed_save_roots=roots,
            allowed_attachment_roots=attachment_roots,
            transport=env.get("OUTLOOK_EMAIL_TRANSPORT", "stdio").strip().lower(),
            http_host=env.get("OUTLOOK_EMAIL_HTTP_HOST", "127.0.0.1").strip(),
            http_port=_int("OUTLOOK_EMAIL_HTTP_PORT", env.get("OUTLOOK_EMAIL_HTTP_PORT"), 8000, 1, 65535),
            http_path=env.get("OUTLOOK_EMAIL_HTTP_PATH", "/mcp").strip() or "/mcp",
            http_token=env.get("OUTLOOK_EMAIL_HTTP_TOKEN") or None,
            enable_drafts=_bool(env.get("OUTLOOK_EMAIL_ENABLE_DRAFTS"), False),
            enable_send=_bool(env.get("OUTLOOK_EMAIL_ENABLE_SEND"), False),
            allowed_outlook_stores=tuple(
                s.strip() for s in env.get("OUTLOOK_EMAIL_OUTLOOK_STORES", "").split(";") if s.strip()
            ),
            outlook_send_account=env.get("OUTLOOK_EMAIL_OUTLOOK_SEND_ACCOUNT") or None,
            approval_timeout=_int(
                "OUTLOOK_EMAIL_APPROVAL_TIMEOUT", env.get("OUTLOOK_EMAIL_APPROVAL_TIMEOUT"), 120, 10, 600
            ),
            credential_backend=env.get("OUTLOOK_EMAIL_CREDENTIAL_BACKEND", "env").strip().lower(),
            credential_service=env.get("OUTLOOK_EMAIL_CREDENTIAL_SERVICE") or None,
            network_timeout=_int("OUTLOOK_EMAIL_NETWORK_TIMEOUT", env.get("OUTLOOK_EMAIL_NETWORK_TIMEOUT"), 30, 1, 300),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.backend not in {"auto", "outlook", "imap", "pop3"}:
            raise ConfigurationError("invalid email backend")
        if not 1 <= self.http_port <= 65535:
            raise ConfigurationError("HTTP port must be between 1 and 65535")
        if self.transport not in {"stdio", "streamable-http", "sse"}:
            raise ConfigurationError("OUTLOOK_EMAIL_TRANSPORT must be stdio, streamable-http, or sse")
        if self.transport != "stdio" and self.http_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ConfigurationError("HTTP transport must bind to localhost")
        if self.transport != "stdio" and (
            not self.http_token
            or len(self.http_token) < 32
            or not self.http_token.isascii()
            or any(ord(c) < 33 or ord(c) > 126 for c in self.http_token)
        ):
            raise ConfigurationError(
                "HTTP transport requires OUTLOOK_EMAIL_HTTP_TOKEN with at least 32 printable ASCII characters"
            )
        if (
            not self.http_path.startswith("/")
            or any(c in self.http_path for c in "?#\\")
            or any(ord(c) < 33 for c in self.http_path)
        ):
            raise ConfigurationError("OUTLOOK_EMAIL_HTTP_PATH must be an absolute URL path")
        if self.credential_backend not in {"env", "keyring"}:
            raise ConfigurationError("OUTLOOK_EMAIL_CREDENTIAL_BACKEND must be env or keyring")
        if self.credential_backend == "keyring" and not self.credential_service:
            raise ConfigurationError("OUTLOOK_EMAIL_CREDENTIAL_SERVICE is required with keyring credentials")
        if not self.imap_tls:
            raise ConfigurationError("IMAP_TLS must remain enabled")
        if not self.pop3_tls:
            raise ConfigurationError("POP3_TLS must remain enabled")
        if not self.smtp_tls and not self.smtp_ssl:
            raise ConfigurationError("SMTP_TLS or SMTP_SSL must be enabled")
        if self.backend == "imap" and not self.imap_host:
            raise ConfigurationError("IMAP_HOST is required when backend=imap")
        if self.backend == "pop3" and not self.pop3_host:
            raise ConfigurationError("POP3_HOST is required when backend=pop3")

    @property
    def imap_configured(self) -> bool:
        return bool(
            self.imap_host and self.imap_username and (self.imap_password or self.credential_backend == "keyring")
        )

    @property
    def smtp_configured(self) -> bool:
        return bool(
            self.smtp_host and self.smtp_username and (self.smtp_password or self.credential_backend == "keyring")
        )

    @property
    def pop3_configured(self) -> bool:
        return bool(
            self.pop3_host and self.pop3_username and (self.pop3_password or self.credential_backend == "keyring")
        )
