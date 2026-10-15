from __future__ import annotations

from ..config import Settings
from ..errors import ConfigurationError, UnsupportedBackendError
from ..policy import SafePathPolicy
from .imap import ImapBackend
from .outlook import OutlookBackend


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
                self.backend = OutlookBackend(self.policy, self.settings.max_attachment_bytes, self.settings.max_body_chars)
                return
            except UnsupportedBackendError as exc:
                self.selection_error = str(exc)
                if self.settings.backend == "outlook":
                    raise
        if self.settings.backend in {"auto", "imap"}:
            self.backend = ImapBackend(self.settings, self.policy)
            return
        raise ConfigurationError("no usable email backend is configured")

    def close(self) -> None:
        if self.backend:
            self.backend.close()
