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
