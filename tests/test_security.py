from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import ssl

import pytest

from outlook_email_mcp.approval import require_local_approval, snapshot_draft
from outlook_email_mcp.backend.imap import ImapBackend
from outlook_email_mcp.backend.pop3 import Pop3Backend
from outlook_email_mcp.config import Settings
from outlook_email_mcp.errors import BackendError, ConfigurationError, PolicyError
from outlook_email_mcp.models import Draft, draft_from_dict
from outlook_email_mcp.policy import SafePathPolicy
from outlook_email_mcp.server import EmailService, create_server


def make_service(monkeypatch, settings):
    backend = Mock()
    backend.send_identity.return_value = {"backend": "test", "account": "sender@example.test"}
    manager = SimpleNamespace(backend=backend, selection_error=None)
    monkeypatch.setattr("outlook_email_mcp.server.BackendManager", lambda *args: manager)
    return EmailService(settings), backend


def mail_settings(**kwargs):
    return Settings(
        backend="pop3",
        pop3_host="pop.example.test",
        pop3_username="reader@example.test",
        pop3_password="synthetic-only",
        imap_host="imap.example.test",
        imap_username="reader@example.test",
        imap_password="synthetic-only",
        smtp_host="smtp.example.test",
        smtp_username="sender@example.test",
        smtp_password="synthetic-only",
        **kwargs,
    )


@pytest.mark.parametrize("field", ["pop3_password", "imap_password", "smtp_password", "http_token"])
def test_secrets_are_absent_from_settings_repr(field):
    assert "synthetic-secret" not in repr(replace(Settings(), **{field: "synthetic-secret"}))


@pytest.mark.parametrize("transport", ["streamable-http", "sse"])
@pytest.mark.parametrize("token", [None, "short", "x" * 32 + "\n", "x" * 32 + "é"])
def test_http_requires_valid_bearer_secret(transport, token):
    with pytest.raises(ConfigurationError, match="HTTP transport requires"):
        Settings(transport=transport, http_token=token).validate()


def test_sending_and_mailbox_writes_disabled_by_default(monkeypatch):
    service, backend = make_service(monkeypatch, Settings())
    draft = Draft(("recipient@example.test",), "subject", "body")
    with pytest.raises(ValueError, match="disabled"):
        service.send_email(draft, True)
    with pytest.raises(ValueError, match="disabled"):
        service.create_draft(draft)
    backend.send_email.assert_not_called()
    backend.create_draft.assert_not_called()


async def test_disabled_tools_are_not_advertised(monkeypatch):
    service, _ = make_service(monkeypatch, Settings())
    names = {tool.name for tool in await create_server(service).list_tools()}
    assert "send_email" not in names
    assert "create_draft" not in names
    assert {"status", "search", "get_message", "prepare_draft"} <= names


@pytest.mark.parametrize("confirm", [False, None, 1, "true"])
def test_send_confirmation_is_strict(monkeypatch, confirm):
    service, backend = make_service(monkeypatch, Settings(enable_send=True))
    with pytest.raises(ValueError, match="confirm=true"):
        service.send_email(Draft(("r@example.test",), "subject", "body"), confirm)
    backend.send_email.assert_not_called()


def test_caller_flag_cannot_replace_local_human_approval(monkeypatch):
    service, backend = make_service(monkeypatch, Settings(enable_send=True))

    def decline(*args):
        raise PolicyError("declined")

    monkeypatch.setattr("outlook_email_mcp.server.require_local_approval", decline)
    with pytest.raises(PolicyError, match="declined"):
        service.send_email(Draft(("r@example.test",), "subject", "body"), True)
    backend.send_email.assert_not_called()


def test_no_desktop_approval_fails_closed(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "tkinter", None)
    with pytest.raises(PolicyError, match="unavailable"):
        require_local_approval({"body": "untrusted mail"})


def test_approved_attachment_bytes_cannot_change_before_send(monkeypatch, tmp_path):
    source = tmp_path / "report.txt"
    source.write_bytes(b"approved bytes")
    service, backend = make_service(monkeypatch, Settings(enable_send=True, allowed_attachment_roots=(tmp_path,)))
    observed = []

    def approve(details, timeout):
        observed.append(details)
        source.write_bytes(b"changed after approval")

    monkeypatch.setattr("outlook_email_mcp.server.require_local_approval", approve)
    service.send_email(Draft(("r@example.test",), "subject", "full body", attachments=(str(source),)), True)
    sent = backend.send_email.call_args.args[0]
    assert sent.payloads[0].data == b"approved bytes"
    assert observed[0]["body"] == "full body"
    assert observed[0]["attachments"][0]["bytes"] == len(b"approved bytes")
    assert "payloads" not in sent.to_dict()


def test_sender_change_invalidates_approval(monkeypatch):
    service, backend = make_service(monkeypatch, Settings(enable_send=True))
    backend.send_identity.side_effect = [{"account": "a@example.test"}, {"account": "b@example.test"}]
    monkeypatch.setattr("outlook_email_mcp.server.require_local_approval", lambda *args: None)
    with pytest.raises(ValueError, match="identity changed"):
        service.send_email(Draft(("r@example.test",), "subject", "body"), True)
    backend.send_email.assert_not_called()


def test_overlapping_sends_are_blocked(monkeypatch):
    service, backend = make_service(monkeypatch, Settings(enable_send=True))
    service._send_lock.acquire()
    try:
        with pytest.raises(ValueError, match="another send"):
            service.send_email(Draft(("r@example.test",), "subject", "body"), True)
    finally:
        service._send_lock.release()
    backend.send_email.assert_not_called()


@pytest.mark.parametrize(
    "data",
    [
        {"to": ["a@example.test\r\nBcc: victim@example.test"]},
        {"to": ["a@example.test,b@example.test"]},
        {"to": ["unresolved-contact"]},
        {"to": [1]},
        {"to": 42},
        {"to": ["a@example.test"], "cc": 42},
        {"to": ["a@example.test"] * 101},
        {"to": ["a@example.test"], "subject": "subject\r\nBcc: victim@example.test"},
        {"to": ["a@example.test"], "body": "x" * 200_001},
    ],
)
def test_invalid_or_ambiguous_outbound_inputs_are_rejected(data):
    with pytest.raises(ValueError):
        draft_from_dict(data)


def test_display_names_are_normalized_to_unambiguous_envelope_addresses():
    assert draft_from_dict({"to": ['"A; B" <a@example.test>']}).to == ("a@example.test",)


def test_aggregate_attachment_limit_and_roots_are_enforced(tmp_path):
    path = tmp_path / "report.txt"
    path.write_bytes(b"1234567890")
    draft = Draft(("a@example.test",), "s", "body", attachments=(str(path), str(path)))
    with pytest.raises(PolicyError, match="outbound message"):
        snapshot_draft(draft, SafePathPolicy(attachment_roots=(tmp_path,)), 100, 15)
    with pytest.raises(PolicyError, match="disabled"):
        snapshot_draft(draft, SafePathPolicy(), 100, 100)


def test_pop3_connection_validates_certificates_and_hostname(monkeypatch):
    clients = []

    def connect(*args, **kwargs):
        clients.append(kwargs)
        return Mock()

    monkeypatch.setattr("outlook_email_mcp.backend.pop3.poplib.POP3_SSL", connect)
    Pop3Backend(mail_settings(), SafePathPolicy())._connect()
    context = clients[0]["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_read_only_pop3_does_not_require_smtp_credentials():
    backend = Pop3Backend(
        Settings(
            backend="pop3", pop3_host="pop.example.test", pop3_username="r@example.test", pop3_password="synthetic-only"
        ),
        SafePathPolicy(),
    )
    assert backend.status()["available"] is True


def test_imap_draft_preserves_bcc_without_requiring_smtp(monkeypatch):
    from email import policy
    from email.parser import BytesParser

    settings = Settings(
        backend="imap",
        imap_host="imap.example.test",
        imap_username="reader@example.test",
        imap_password="synthetic-only",
        enable_drafts=True,
    )
    backend = ImapBackend(settings, SafePathPolicy())
    client = Mock()
    client.append.return_value = ("OK", [])
    monkeypatch.setattr(backend, "_connect", lambda: client)
    backend.create_draft(Draft(("to@example.test",), "subject", "body", bcc=("hidden@example.test",)))
    message = BytesParser(policy=policy.default).parsebytes(client.append.call_args.args[-1])
    assert str(message["Bcc"]) == "hidden@example.test"
    assert str(message["From"]) == "reader@example.test"


def test_pop3_generated_identifier_can_be_retrieved_and_stale_id_is_rejected():
    backend = Pop3Backend(mail_settings(), SafePathPolicy())
    raw = b"From: a@example.test\r\nSubject: test\r\n\r\nbody"
    client = Mock()
    client.list.return_value = b"+OK 1 100"
    client.retr.return_value = (b"+OK", raw.split(b"\r\n"), len(raw))
    identifier = backend._message_id(1, raw)
    assert backend._resolve(client, identifier)[1] == raw
    with pytest.raises(BackendError, match="changed"):
        backend._resolve(client, identifier[:-1] + ("0" if identifier[-1] != "0" else "1"))


def test_pop3_oversized_message_is_rejected_before_download():
    backend = Pop3Backend(mail_settings(max_message_bytes=1000), SafePathPolicy())
    client = Mock()
    client.list.return_value = b"+OK 1 9999999"
    with pytest.raises(BackendError, match="safety limit"):
        backend._retrieve(client, 1)
    client.retr.assert_not_called()


def test_imap_body_limit_is_respected():
    backend = ImapBackend(replace(mail_settings(max_body_chars=100), backend="imap"), SafePathPolicy())
    client = Mock()
    client.response.return_value = ("UIDVALIDITY", [b"123"])
    raw = b"From: a@example.test\r\nSubject: test\r\n\r\n" + b"x" * 1000
    client.uid.side_effect = [("OK", [b"1 (RFC822.SIZE 1100)"]), ("OK", [(b"1", raw)])]
    message = backend._fetch_message(client, b"1", "INBOX")
    assert len(message.body) == 100
    assert ":123:1" in message.id


def test_imap_uidvalidity_change_blocks_wrong_message():
    backend = ImapBackend(replace(mail_settings(), backend="imap"), SafePathPolicy())
    client = Mock()
    client.select.return_value = ("OK", [b"1"])
    client.response.return_value = ("UIDVALIDITY", [b"124"])
    identifier = "imap:message:" + backend._folder_id("INBOX") + ":123:1"
    with pytest.raises(BackendError, match="identity changed"):
        backend._resolve_message(client, identifier, None)
    client.uid.assert_not_called()


@pytest.mark.parametrize("kind", ["imap", "pop3"])
@pytest.mark.parametrize("implicit", [True, False])
def test_smtp_envelope_and_tls_use_correct_arguments(monkeypatch, kind, implicit):
    settings = replace(mail_settings(smtp_ssl=implicit), backend=kind)
    backend = (ImapBackend if kind == "imap" else Pop3Backend)(settings, SafePathPolicy())
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    constructor = Mock(return_value=client)
    monkeypatch.setattr(
        f"outlook_email_mcp.backend.{kind}.smtplib.SMTP_SSL"
        if implicit
        else f"outlook_email_mcp.backend.{kind}.smtplib.SMTP",
        constructor,
    )
    draft = Draft(("to@example.test",), "subject", "body", cc=("cc@example.test",), bcc=("bcc@example.test",))
    assert backend.send_email(draft)["sent"] is True
    assert client.send_message.call_args.kwargs["to_addrs"] == [
        "to@example.test",
        "cc@example.test",
        "bcc@example.test",
    ]
    message = client.send_message.call_args.args[0]
    assert "Bcc" not in message
    assert constructor.call_args.kwargs["timeout"] == settings.network_timeout
    context = constructor.call_args.kwargs["context"] if implicit else client.starttls.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
