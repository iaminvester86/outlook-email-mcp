"""Authenticate every HTTP route before MCP parsing or backend execution."""

from __future__ import annotations

import hmac


class BearerAuthMiddleware:
    def __init__(self, app, token: str) -> None:
        self.app = app
        self.expected = token.encode("ascii")

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            headers = [value for name, value in scope.get("headers", ()) if name.lower() == b"authorization"]
            scheme, separator, candidate = headers[0].partition(b" ") if len(headers) == 1 else (b"", b"", b"")
            if scheme.lower() != b"bearer" or separator != b" " or not hmac.compare_digest(candidate, self.expected):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"www-authenticate", b"Bearer"),
                            (b"content-type", b"text/plain"),
                            (b"cache-control", b"no-store"),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": b"Authentication required"})
                return
        await self.app(scope, receive, send)
