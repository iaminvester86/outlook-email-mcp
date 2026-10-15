import pytest

from outlook_email_mcp.errors import QueryError
from outlook_email_mcp.models import Draft, Message, draft_from_dict
from outlook_email_mcp.query import parse_query
from outlook_email_mcp.backend.imap import _imap_quote


def test_message_and_draft_are_bounded():
    message = Message("id", "subject", "sender", body="x" * 300_000)
    assert len(message.body) == 200_000
    draft = Draft(("a@example.test",), "s", "body", attachments=tuple(str(i) for i in range(200)))
    assert len(draft.attachments) == 100


def test_query_matches_structured_fields_and_text():
    message = Message("1", "Build report", "alice@example.test", ("bob@example.test",), body="weekly status", unread=True, has_attachments=True)
    query = parse_query('from:alice@example.test is:unread has:attachment weekly')
    assert query.matches(message)
    assert not parse_query("is:read").matches(message)


def test_query_reports_bad_quotes_and_draft_requires_recipient():
    with pytest.raises(QueryError):
        parse_query('subject:"unfinished')
    with pytest.raises(ValueError):
        draft_from_dict({"subject": "missing recipient", "body": "x"})


def test_query_rejects_control_characters():
    with pytest.raises(QueryError):
        parse_query("subject:invoice\r\nX-Injected: yes")


def test_imap_search_values_are_quoted():
    assert _imap_quote('a"\\b') == '"a\\"\\\\b"'
