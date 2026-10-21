from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from outlook_email_mcp.backend.outlook import OutlookBackend
from outlook_email_mcp.errors import PolicyError
from outlook_email_mcp.models import AttachmentPayload, Draft
from outlook_email_mcp.policy import SafePathPolicy


def outlook_backend(allowed=("allowed",), policy=None):
    backend = object.__new__(OutlookBackend)
    backend.allowed_stores = frozenset(allowed)
    backend.send_account = "sender@example.test"
    backend.policy = policy or SafePathPolicy()
    backend.max_attachment_bytes = 1000
    backend.max_message_bytes = 5000
    backend.max_body_chars = 100
    backend._worker = SimpleNamespace(call=lambda fn: fn(), _namespace=Mock())
    return backend


def test_store_discovery_is_local_and_mcp_listing_is_filtered():
    backend = outlook_backend()
    backend._worker._namespace.Folders = [
        SimpleNamespace(StoreID="allowed", Name="Selected"),
        SimpleNamespace(StoreID="private", Name="Private"),
    ]
    assert [s.name for s in backend.list_stores()] == ["Selected"]
    assert len(backend.discover_stores()) == 2


@pytest.mark.parametrize("explicit", [True, False])
def test_default_and_explicit_folder_access_enforce_store_allowlist(explicit):
    backend = outlook_backend()
    namespace = backend._worker._namespace
    namespace.GetDefaultFolder.return_value = SimpleNamespace(StoreID="private")
    namespace.GetFolderFromID.return_value = SimpleNamespace(StoreID="private")
    with pytest.raises(PolicyError, match="not allowed"):
        backend._folder("outlook:folder:known-private-id" if explicit else None)


def test_empty_allowlist_denies_all_outlook_data():
    backend = outlook_backend(allowed=())
    backend._worker._namespace.Folders = [SimpleNamespace(StoreID="allowed", Name="Selected")]
    backend._worker._namespace.GetDefaultFolder.return_value = SimpleNamespace(StoreID="allowed")
    assert backend.list_stores() == []
    with pytest.raises(PolicyError):
        backend._folder(None)


@pytest.mark.parametrize("actual_store,actual_folder", [("private", "folder"), ("allowed", "other")])
def test_message_identifier_cannot_bypass_store_or_folder(actual_store, actual_folder):
    backend = outlook_backend()
    namespace = backend._worker._namespace
    namespace.GetFolderFromID.return_value = SimpleNamespace(StoreID="allowed", EntryID="folder")
    namespace.GetItemFromID.return_value = SimpleNamespace(
        Parent=SimpleNamespace(StoreID=actual_store, EntryID=actual_folder)
    )
    with pytest.raises(PolicyError):
        backend._item("outlook:message:known-id", "outlook:folder:folder")


def test_export_does_not_touch_predictable_existing_temporary_file(tmp_path):
    old = tmp_path / "report.txt.outlook-download"
    old.write_bytes(b"preserve this file")
    backend = outlook_backend(policy=SafePathPolicy((tmp_path,)))
    attachment = Mock(FileName="report.txt", Size=7)
    paths = []

    def save(path):
        paths.append(Path(path))
        Path(path).write_bytes(b"payload")

    attachment.SaveAsFile.side_effect = save
    item = Mock()
    item.Attachments.Item.return_value = attachment
    backend._item = lambda *args: (item, None)
    backend.save_attachment("outlook:message:1", "1", str(tmp_path))
    assert old.read_bytes() == b"preserve this file"
    assert (tmp_path / "report.txt").read_bytes() == b"payload"
    assert paths[0].parent != tmp_path
    assert not paths[0].parent.exists()


def test_export_checks_actual_attachment_size_after_com_download(tmp_path):
    backend = outlook_backend(policy=SafePathPolicy((tmp_path,)))
    backend.max_attachment_bytes = 5
    attachment = Mock(FileName="report.txt", Size=1)
    attachment.SaveAsFile.side_effect = lambda path: Path(path).write_bytes(b"too many actual bytes")
    item = Mock()
    item.Attachments.Item.return_value = attachment
    backend._item = lambda *args: (item, None)
    with pytest.raises(Exception, match="safety limit"):
        backend.save_attachment("outlook:message:1", "1", str(tmp_path))
    assert not (tmp_path / "report.txt").exists()


def test_sender_is_explicit_and_draft_uses_its_delivery_store(tmp_path):
    backend = outlook_backend()
    account = Mock(SmtpAddress="sender@example.test")
    account.DeliveryStore.StoreID = "allowed"
    backend._worker._namespace.Accounts = [account]
    item = Mock()
    account.DeliveryStore.GetDefaultFolder.return_value.Items.Add.return_value = item
    captured = []
    item.Attachments.Add.side_effect = lambda path: captured.append(Path(path).read_bytes())
    draft = Draft(("to@example.test",), "subject", "body", payloads=(AttachmentPayload("report.txt", b"frozen"),))
    backend.create_draft(draft)
    assert item.SendUsingAccount is account
    account.DeliveryStore.GetDefaultFolder.assert_called_once_with(16)
    assert captured == [b"frozen"]
    item.Save.assert_called_once()
    item.Send.assert_not_called()


@pytest.mark.parametrize("sender,store", [(None, "allowed"), ("sender@example.test", "private")])
def test_missing_or_disallowed_outlook_sender_is_rejected(sender, store):
    backend = outlook_backend()
    backend.send_account = sender
    account = Mock(SmtpAddress="sender@example.test")
    account.DeliveryStore.StoreID = store
    backend._worker._namespace.Accounts = [account]
    with pytest.raises(PolicyError):
        backend.send_identity()
