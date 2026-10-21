from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from starlette.testclient import TestClient

from outlook_email_mcp.config import Settings
from outlook_email_mcp.server import create_server

TOKEN = "synthetic-http-token-for-offline-tests-only"


def application(transport="streamable-http"):
    service = SimpleNamespace(
        settings=Settings(transport=transport, http_token=TOKEN), backend=Mock(), status=lambda: {}
    )
    server = create_server(service)
    return server.streamable_http_app() if transport == "streamable-http" else server.sse_app()


@pytest.mark.parametrize(
    "transport,path,method",
    [
        ("streamable-http", "/mcp", "post"),
        ("streamable-http", "/mcp", "get"),
        ("sse", "/mcp", "get"),
        ("sse", "/messages/", "post"),
    ],
)
@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Basic invalid"])
def test_every_http_transport_route_requires_bearer_auth(transport, path, method, authorization):
    with TestClient(application(transport), base_url="http://localhost:8000") as client:
        response = getattr(client, method)(path, headers={"Authorization": authorization} if authorization else {})
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
        assert TOKEN not in response.text


def initialize(client, **headers):
    return client.post(
        "/mcp",
        headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/json, text/event-stream", **headers},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "security-test", "version": "1"},
            },
        },
    )


def test_valid_bearer_token_can_initialize_mcp():
    with TestClient(application(), base_url="http://localhost:8000") as client:
        assert initialize(client).status_code == 200


def test_bearer_scheme_is_case_insensitive():
    with TestClient(application(), base_url="http://localhost:8000") as client:
        assert initialize(client, Authorization="bearer " + TOKEN).status_code == 200


def test_untrusted_browser_origin_is_rejected_even_with_token():
    with TestClient(application(), base_url="http://localhost:8000") as client:
        assert initialize(client, Origin="https://attacker.example.test").status_code == 403


def test_dns_rebinding_host_is_rejected_even_with_token():
    with TestClient(application(), base_url="http://localhost:8000") as client:
        assert initialize(client, Host="attacker.example.test:8000").status_code == 421


def test_duplicate_authorization_headers_are_rejected():
    with TestClient(application(), base_url="http://localhost:8000") as client:
        response = client.post(
            "/mcp", headers=[("Authorization", "Bearer " + TOKEN), ("Authorization", "Bearer " + TOKEN)]
        )
        assert response.status_code == 401
