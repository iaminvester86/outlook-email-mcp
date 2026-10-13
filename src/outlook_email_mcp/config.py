"""Environment-backed configuration with conservative defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
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
    raise ConfigurationError(f"invalid boolean setting: {value!r}")


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
    imap_host: str | None = None
    imap_port: int = 993
    imap_username: str | None = None
    imap_password: str | None = None
    imap_tls: bool = True
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
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

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        backend = env.get("OUTLOOK_EMAIL_BACKEND", env.get("EMAIL_BACKEND", "auto")).strip().lower()
        if backend == "imap-smtp":
            backend = "imap"
        if backend not in {"auto", "outlook", "imap"}:
            raise ConfigurationError("OUTLOOK_EMAIL_BACKEND must be auto, outlook, or imap")
        roots = tuple(
            Path(p).expanduser()
            for p in env.get("OUTLOOK_EMAIL_SAVE_ROOTS", "").split(os.pathsep)
            if p.strip()
        )
        attachment_roots = tuple(
            Path(p).expanduser()
            for p in env.get("OUTLOOK_EMAIL_ATTACHMENT_ROOTS", "").split(os.pathsep)
            if p.strip()
        )
        settings = cls(
            backend=backend,
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
            max_body_chars=_int("OUTLOOK_EMAIL_MAX_BODY_CHARS", env.get("OUTLOOK_EMAIL_MAX_BODY_CHARS"), 20000, 100, 1_000_000),
            max_attachment_bytes=_int(
                "OUTLOOK_EMAIL_MAX_ATTACHMENT_BYTES",
                env.get("OUTLOOK_EMAIL_MAX_ATTACHMENT_BYTES", env.get("MCP_MAX_ATTACHMENT_BYTES")),
                25 * 1024 * 1024,
                1,
                500 * 1024 * 1024,
            ),
            max_message_bytes=_int("OUTLOOK_EMAIL_MAX_MESSAGE_BYTES", env.get("OUTLOOK_EMAIL_MAX_MESSAGE_BYTES"), 50 * 1024 * 1024, 1_000, 500 * 1024 * 1024),
            allowed_save_roots=roots,
            allowed_attachment_roots=attachment_roots,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.imap_tls:
            raise ConfigurationError("IMAP_TLS must remain enabled")
        if not self.smtp_tls and not self.smtp_ssl:
            raise ConfigurationError("SMTP_TLS or SMTP_SSL must be enabled")
        if self.backend == "imap" and not self.imap_host:
            raise ConfigurationError("IMAP_HOST is required when backend=imap")

    @property
    def imap_configured(self) -> bool:
        return bool(self.imap_host and self.imap_username and self.imap_password)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_username and self.smtp_password)
