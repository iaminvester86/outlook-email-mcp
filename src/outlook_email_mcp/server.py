"""MCP stdio server exposing bounded, non-destructive mail operations."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from typing import Any

from .backend.factory import BackendManager
from .config import Settings
from .errors import ConfigurationError, EmailMcpError, UnsupportedBackendError
from .models import Draft, draft_from_dict
from .policy import SafePathPolicy
from .approval import approval_details, require_local_approval, snapshot_draft
from .http_auth import BearerAuthMiddleware

logger = logging.getLogger("outlook_email_mcp")


def require_send_confirmation(confirm: bool) -> None:
    """Keep accidental sends impossible unless the caller explicitly opts in."""
    if confirm is not True:
        raise ValueError("send_email requires confirm=true")


class EmailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.settings.validate()
        self._send_lock = threading.Lock()
        self.policy = SafePathPolicy(self.settings.allowed_save_roots, self.settings.allowed_attachment_roots)
        self.manager: BackendManager | None = None
        self.startup_error: str | None = None
        try:
            self.manager = BackendManager(self.settings, self.policy)
        except (EmailMcpError, OSError) as exc:
            self.startup_error = str(exc) if isinstance(exc, EmailMcpError) else "backend initialization failed"

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
            result["drafts_enabled"] = self.settings.enable_drafts
            result["sending_enabled"] = self.settings.enable_send
            result["local_send_approval_required"] = True
            if self.manager.selection_error:
                result["fallback_reason"] = self.manager.selection_error
            return result
        return {"backend": None, "available": False, "error": self.startup_error}

    def create_draft(self, draft: Draft) -> dict[str, Any]:
        if not self.settings.enable_drafts:
            raise ValueError("draft creation is disabled")
        frozen = snapshot_draft(draft, self.policy, self.settings.max_attachment_bytes, self.settings.max_message_bytes)
        return self.backend.create_draft(frozen)

    def send_email(self, draft: Draft, confirm: bool) -> dict[str, Any]:
        if not self.settings.enable_send:
            raise ValueError("sending is disabled")
        require_send_confirmation(confirm)
        if not self._send_lock.acquire(blocking=False):
            raise ValueError("another send is awaiting local approval")
        try:
            frozen = snapshot_draft(
                draft, self.policy, self.settings.max_attachment_bytes, self.settings.max_message_bytes
            )
            identity = self.backend.send_identity()
            require_local_approval(approval_details(frozen, identity), self.settings.approval_timeout)
            if self.backend.send_identity() != identity:
                raise ValueError("sender identity changed; approve a new request")
            return self.backend.send_email(frozen)
        finally:
            self._send_lock.release()


def create_server(service: EmailService | None = None):
    """Create a FastMCP instance; import MCP lazily so pure logic stays stdlib-testable."""
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings

    service = service or EmailService()
    settings = service.settings
    settings.validate()

    def setting(name: str, default: Any) -> Any:
        value = getattr(settings, name, default)
        return value if isinstance(value, type(default)) else default

    class AuthenticatedFastMCP(FastMCP):
        def streamable_http_app(self):
            app = super().streamable_http_app()
            app.add_middleware(BearerAuthMiddleware, token=settings.http_token)
            return app

        def sse_app(self, mount_path=None):
            app = super().sse_app(mount_path)
            app.add_middleware(BearerAuthMiddleware, token=settings.http_token)
            return app

    server_type = AuthenticatedFastMCP if settings.transport != "stdio" else FastMCP
    mcp = server_type(
        "outlook-email",
        host=setting("http_host", "127.0.0.1"),
        port=setting("http_port", 8000),
        streamable_http_path=setting("http_path", "/mcp"),
        sse_path=setting("http_path", "/mcp"),
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                f"127.0.0.1:{settings.http_port}",
                f"localhost:{settings.http_port}",
                f"[::1]:{settings.http_port}",
            ],
            allowed_origins=[
                f"http://127.0.0.1:{settings.http_port}",
                f"http://localhost:{settings.http_port}",
                f"http://[::1]:{settings.http_port}",
            ],
        ),
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
        return [
            item.to_dict() if hasattr(item, "to_dict") else dict(item)
            for item in service.backend.list_folders(store_id)
        ]

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
    def save_attachment(
        message_id: str, attachment_id: str, directory: str, folder_id: str | None = None
    ) -> dict[str, Any]:
        return service.backend.save_attachment(message_id, attachment_id, directory, folder_id)

    @mcp.tool()
    def prepare_draft(
        to: list[str] | str,
        subject: str,
        body: str,
        cc: list[str] | str | None = None,
        bcc: list[str] | str | None = None,
        attachments: list[str] | str | None = None,
    ) -> dict[str, Any]:
        data = {
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc or (),
            "bcc": bcc or (),
            "attachments": attachments or (),
        }
        return draft_from_dict(data).to_dict()

    @mcp.tool()
    def create_draft(draft: dict[str, Any]) -> dict[str, Any]:
        return service.create_draft(draft_from_dict(draft))

    @mcp.tool()
    def send_email(draft: dict[str, Any], confirm: bool = False) -> dict[str, Any]:
        return service.send_email(draft_from_dict(draft), confirm)

    if not settings.enable_drafts:
        mcp.remove_tool("create_draft")
    if not settings.enable_send:
        mcp.remove_tool("send_email")

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("stdio", "streamable-http", "sse"), default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--list-outlook-stores", action="store_true", help="locally list store IDs for the allowlist, then exit"
    )
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parser.parse_args()
    if args.list_outlook_stores:
        import json
        from .backend.outlook import OutlookBackend

        backend = OutlookBackend(SafePathPolicy())
        try:
            print(json.dumps([store.to_dict() for store in backend.discover_stores()], indent=2))
        finally:
            backend.close()
        return
    try:
        settings = Settings.from_env()
        if args.transport or args.host or args.port:
            from dataclasses import replace

            settings = replace(
                settings,
                transport=args.transport or settings.transport,
                http_host=args.host or settings.http_host,
                http_port=args.port or settings.http_port,
            )
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
