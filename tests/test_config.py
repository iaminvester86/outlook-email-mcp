import pytest

from outlook_email_mcp.config import Settings
from outlook_email_mcp.errors import ConfigurationError


def test_config_parses_limits_and_roots(tmp_path):
    settings = Settings.from_env({
        "OUTLOOK_EMAIL_BACKEND": "imap",
        "IMAP_HOST": "imap.example.test",
        "IMAP_USERNAME": "u",
        "IMAP_PASSWORD": "p",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_USERNAME": "u",
        "SMTP_PASSWORD": "p",
        "OUTLOOK_EMAIL_MAX_RESULTS": "7",
        "OUTLOOK_EMAIL_SAVE_ROOTS": str(tmp_path),
    })
    assert settings.max_results == 7
    assert settings.imap_configured and settings.smtp_configured
    assert settings.allowed_save_roots == (tmp_path,)


def test_config_rejects_plaintext_transport():
    with pytest.raises(ConfigurationError):
        Settings.from_env({"IMAP_TLS": "false"})


def test_http_transport_cannot_bind_public_interface():
    with pytest.raises(ConfigurationError):
        Settings.from_env({"OUTLOOK_EMAIL_TRANSPORT": "streamable-http", "OUTLOOK_EMAIL_HTTP_HOST": "0.0.0.0"})


def test_pop3_configuration_is_supported_without_plaintext_password():
    settings = Settings.from_env({
        "OUTLOOK_EMAIL_BACKEND": "pop3",
        "POP3_HOST": "pop.example.test",
        "POP3_USERNAME": "u",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_USERNAME": "u",
        "OUTLOOK_EMAIL_CREDENTIAL_BACKEND": "keyring",
        "OUTLOOK_EMAIL_CREDENTIAL_SERVICE": "test-service",
    })
    assert settings.pop3_configured and settings.smtp_configured


def test_cli_overrides_cannot_bypass_loopback_policy():
    settings = Settings.from_env({"OUTLOOK_EMAIL_TRANSPORT": "stdio"})
    from dataclasses import replace
    with pytest.raises(ConfigurationError):
        replace(settings, transport="streamable-http", http_host="0.0.0.0").validate()
