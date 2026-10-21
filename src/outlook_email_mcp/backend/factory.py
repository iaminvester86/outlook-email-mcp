from __future__ import annotations

from ..config import Settings
from ..errors import ConfigurationError, UnsupportedBackendError
from ..policy import SafePathPolicy
from .imap import ImapBackend
from .outlook import OutlookBackend
from .pop3 import Pop3Backend


class BackendManager:
    """Select Outlook first on Windows, then configured IMAP in auto mode."""

    def __init__(self, settings: Settings, policy: SafePathPolicy) -> None:
        self.settings = settings
        self.policy = policy
        self.backend = None
        self.selection_error: str | None = None
        self._select()

    def _select(self) -> None:
        if self.settings.backend in {"auto", "outlook"}:
            try:
                self.backend = OutlookBackend(
                    self.policy,
                    self.settings.max_attachment_bytes,
                    self.settings.max_body_chars,
                    self.settings.allowed_outlook_stores,
                    self.settings.outlook_send_account,
                    self.settings.max_message_bytes,
                )
                return
            except UnsupportedBackendError as exc:
                self.selection_error = str(exc)
                if self.settings.backend == "outlook":
                    raise
        candidates = []
        if self.settings.backend in {"auto", "imap"}:
            candidates.append(("imap", ImapBackend))
        if self.settings.backend in {"auto", "pop3"}:
            candidates.append(("pop3", Pop3Backend))
        errors = []
        for name, backend_type in candidates:
            try:
                self.backend = backend_type(self.settings, self.policy)
                return
            except (ConfigurationError, UnsupportedBackendError) as exc:
                errors.append(f"{name}: {exc}")
                if self.settings.backend != "auto":
                    raise
        raise ConfigurationError(
            "no usable email backend is configured" + (" (" + "; ".join(errors) + ")" if errors else "")
        )

    def close(self) -> None:
        if self.backend:
            self.backend.close()
