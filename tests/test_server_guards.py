from unittest.mock import Mock

import pytest

from outlook_email_mcp.config import Settings
from outlook_email_mcp.errors import UnsupportedBackendError
from outlook_email_mcp.server import EmailService, create_server, require_send_confirmation


def test_service_reports_unavailable_without_outlook_or_imap(monkeypatch):
    monkeypatch.setattr("outlook_email_mcp.backend.factory.OutlookBackend", lambda *args: (_ for _ in ()).throw(UnsupportedBackendError("not available")))
    service = EmailService(Settings())
    assert service.status()["available"] is False


def test_mcp_factory_isolated_from_backend(monkeypatch):
    # The MCP package is optional in the test environment; this test is skipped if absent.
    pytest.importorskip("mcp")
    backend = Mock()
    backend.list_stores.return_value = []
    service = Mock()
    service.backend = backend
    service.settings.max_results = 5
    server = create_server(service)
    assert server is not None


def test_send_requires_explicit_confirmation():
    with pytest.raises(ValueError):
        require_send_confirmation(False)
    require_send_confirmation(True)
