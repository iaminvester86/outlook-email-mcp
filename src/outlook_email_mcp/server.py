"""MCP stdio server exposing bounded, non-destructive mail operations."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from .backend.factory import BackendManager
from .config import Settings
from .errors import ConfigurationError, EmailMcpError, UnsupportedBackendError
from .models import Draft, draft_from_dict
from .policy import SafePathPolicy

logger = logging.getLogger("outlook_email_mcp")


def require_send_confirmation(confirm: bool) -> None:
    """Keep accidental sends impossible unless the caller explicitly opts in."""
    if confirm is not True:
        raise ValueError("send_email requires confirm=true")


class EmailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.policy = SafePathPolicy(self.settings.allowed_save_roots, self.settings.allowed_attachment_roots)
        self.manager: BackendManager | None = None
        self.startup_error: str | None = None
        try:
            self.manager = BackendManager(self.settings, self.policy)
        except (EmailMcpError, OSError) as exc:
            self.startup_error = str(exc)

    @property
    def backend(self):
        if not self.manager or not self.manager.backend:
            raise UnsupportedBackendError(self.startup_error or "no email backend is available")
        return self.manager.backend

    def close(self) -> None:
        if self.manager:
            self.manager.close()

    def status(self) -> dict[str, Any]:
        if self.manager and self.manager.backend:
            result = self.manager.backend.status()
            if self.manager.selection_error:
                result["fallback_reason"] = self.manager.selection_error
            return result
        return {"backend": None, "available": False, "error": self.startup_error}


def create_server(service: EmailService | None = None):
    """Create a FastMCP instance; import MCP lazily so pure logic stays stdlib-testable."""
    from mcp.server.fastmcp import FastMCP

    service = service or EmailService()
    settings = service.settings
    def setting(name: str, default: Any) -> Any:
        value = getattr(settings, name, default)
        return value if isinstance(value, type(default)) else default

    mcp = FastMCP(
        "outlook-email",
        host=setting("http_host", "127.0.0.1"),
        port=setting("http_port", 8000),
        streamable_http_path=setting("http_path", "/mcp"),
        sse_path=setting("http_path", "/mcp"),
    )

    @mcp.tool()
    def status() -> dict[str, Any]:
        """Report backend and transport availability."""
        return service.status()

    @mcp.tool()
    def list_stores() -> list[dict[str, Any]]:
        return [item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in service.backend.list_stores()]

    @mcp.tool()
    def list_folders(store_id: str | None = None) -> list[dict[str, Any]]:
        return [item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in service.backend.list_folders(store_id)]

    @mcp.tool()
    def search(query: str = "", folder_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        bounded_limit = min(max(1, limit or service.settings.max_results), service.settings.max_results)
        return [item.to_dict() for item in service.backend.search(query, folder_id, bounded_limit)]

    @mcp.tool()
    def get_message(message_id: str, folder_id: str | None = None) -> dict[str, Any]:
        return service.backend.get_message(message_id, folder_id).to_dict()

    @mcp.tool()
    def list_attachments(message_id: str, folder_id: str | None = None) -> list[dict[str, Any]]:
        return [item.to_dict() for item in service.backend.list_attachments(message_id, folder_id)]

    @mcp.tool()
    def save_attachment(message_id: str, attachment_id: str, directory: str, folder_id: str | None = None) -> dict[str, Any]:
        return service.backend.save_attachment(message_id, attachment_id, directory, folder_id)

    @mcp.tool()
    def prepare_draft(to: list[str] | str, subject: str, body: str, cc: list[str] | str | None = None, bcc: list[str] | str | None = None, attachments: list[str] | str | None = None) -> dict[str, Any]:
        data = {"to": to, "subject": subject, "body": body, "cc": cc or (), "bcc": bcc or (), "attachments": attachments or ()}
        return draft_from_dict(data).to_dict()

    @mcp.tool()
    def create_draft(draft: dict[str, Any]) -> dict[str, Any]:
        return service.backend.create_draft(draft_from_dict(draft))

    @mcp.tool()
    def send_email(draft: dict[str, Any], confirm: bool = False) -> dict[str, Any]:
        require_send_confirmation(confirm)
        return service.backend.send_email(draft_from_dict(draft))

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("stdio", "streamable-http", "sse"), default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if args.transport or args.host or args.port:
            from dataclasses import replace
            settings = replace(settings, transport=args.transport or settings.transport, http_host=args.host or settings.http_host, http_port=args.port or settings.http_port)
            settings.validate()
    except ConfigurationError as exc:
        parser.error(str(exc))
    service = EmailService(settings)
    try:
        create_server(service).run(transport=service.settings.transport)
    finally:
        service.close()


if __name__ == "__main__":
    main()
