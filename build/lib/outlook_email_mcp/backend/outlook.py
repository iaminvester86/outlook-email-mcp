"""Outlook COM backend. All COM calls execute on one initialized thread."""

from __future__ import annotations

import datetime as _dt
import os
import queue
import sys
import threading
from email.utils import format_datetime
from typing import Any, Callable, TypeVar

from ..errors import BackendError, UnsupportedBackendError
from ..models import Attachment, Draft, Folder, Message, Store
from ..policy import SafePathPolicy
from ..query import parse_query

T = TypeVar("T")


class _ComWorker:
    def __init__(self) -> None:
        self._jobs: queue.Queue[tuple[Callable[[], Any], queue.Queue[tuple[bool, Any]]]] = queue.Queue()
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._stopped = False
        self._thread = threading.Thread(target=self._run, name="outlook-com", daemon=True)
        self._thread.start()
        self._ready.wait(15)
        if self._startup_error:
            raise self._startup_error
        if not self._ready.is_set():
            raise UnsupportedBackendError("Outlook COM thread did not start")

    def _run(self) -> None:
        pythoncom = None
        initialized = False
        try:
            if sys.platform != "win32":
                raise UnsupportedBackendError("Outlook COM is supported only on Windows")
            import pythoncom  # type: ignore
            import win32com.client  # type: ignore
            pythoncom.CoInitialize()
            initialized = True
            self._outlook = win32com.client.Dispatch("Outlook.Application")
            self._namespace = self._outlook.GetNamespace("MAPI")
        except Exception as exc:  # startup errors become a safe capability result
            if initialized and pythoncom is not None:
                pythoncom.CoUninitialize()
            self._startup_error = UnsupportedBackendError("Outlook is unavailable; use the IMAP backend")
            self._ready.set()
            return
        self._ready.set()
        while True:
            job = self._jobs.get()
            if job is None:
                break
            fn, result = job
            try:
                result.put((True, fn()))
            except Exception as exc:
                result.put((False, exc))
        if pythoncom is not None:
            pythoncom.CoUninitialize()

    def call(self, fn: Callable[[], T]) -> T:
        if self._stopped:
            raise BackendError("Outlook backend is closed")
        result: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)
        self._jobs.put((fn, result))
        ok, value = result.get()
        if ok:
            return value
        raise BackendError("Outlook operation failed") from value

    def close(self) -> None:
        if not self._stopped:
            self._stopped = True
            self._jobs.put(None)  # type: ignore[arg-type]
            self._thread.join(timeout=5)


class OutlookBackend:
    name = "outlook"

    def __init__(self, policy: SafePathPolicy, max_attachment_bytes: int = 25 * 1024 * 1024, max_body_chars: int = 20000) -> None:
        self.policy = policy
        self.max_attachment_bytes = max_attachment_bytes
        self.max_body_chars = max_body_chars
        self._worker = _ComWorker()

    def close(self) -> None:
        self._worker.close()

    def status(self) -> dict:
        return {"backend": self.name, "available": True, "transport": "local Outlook COM"}

    @staticmethod
    def _store_id(store: Any) -> str:
        return f"outlook:store:{store.StoreID}"

    @staticmethod
    def _folder_id(folder: Any) -> str:
        return f"outlook:folder:{folder.EntryID}"

    def list_stores(self) -> list[Store]:
        def run() -> list[Store]:
            return [Store(self._store_id(s), str(s.Name), self.name) for s in self._worker._namespace.Folders]
        return self._worker.call(run)

    def list_folders(self, store_id: str | None = None) -> list[Folder]:
        def run() -> list[Folder]:
            output: list[Folder] = []
            for store in self._worker._namespace.Folders:
                sid = self._store_id(store)
                if store_id and store_id != sid:
                    continue
                def walk(folder: Any, parent: str | None = None, prefix: str = "") -> None:
                    fid = self._folder_id(folder)
                    path = f"{prefix}/{folder.Name}" if prefix else str(folder.Name)
                    output.append(Folder(fid, str(folder.Name), sid, parent, path))
                    for child in folder.Folders:
                        walk(child, fid, path)
                for root in store.Folders:
                    walk(root)
            return output
        return self._worker.call(run)

    def _folder(self, folder_id: str | None) -> Any:
        if not folder_id:
            # Outlook's built-in Inbox constant is 6 (OlDefaultFolders.olFolderInbox).
            return self._worker._namespace.GetDefaultFolder(6)
        if not folder_id.startswith("outlook:folder:"):
            raise BackendError("invalid Outlook folder_id")
        return self._worker._namespace.GetFolderFromID(folder_id.removeprefix("outlook:folder:"))

    def search(self, query: str, folder_id: str | None, limit: int) -> list[Message]:
        parsed = parse_query(query)
        def run() -> list[Message]:
            folder = self._folder(folder_id)
            items = folder.Items
            items.Sort("[ReceivedTime]", True)
            found: list[Message] = []
            for item in items:
                if len(found) >= limit:
                    break
                message = self._message(item, self._folder_id(folder))
                if parsed.matches(message):
                    found.append(message)
            return found
        return self._worker.call(run)

    def _message(self, item: Any, folder_id: str | None) -> Message:
        attachments = getattr(item, "Attachments", None)
        count = int(getattr(attachments, "Count", 0) or 0)
        received = getattr(item, "ReceivedTime", None)
        if isinstance(received, _dt.datetime):
            received_at = format_datetime(received)
        else:
            received_at = str(received) if received else None
        recipients = getattr(item, "Recipients", None)
        to_addresses: list[str] = []
        cc_addresses: list[str] = []
        if recipients is not None:
            for index in range(1, int(getattr(recipients, "Count", 0) or 0) + 1):
                recipient = recipients.Item(index)
                recipient_type = int(getattr(recipient, "Type", 1))
                if recipient_type == 1:
                    to_addresses.append(str(getattr(recipient, "Address", "")))
                elif recipient_type == 2:
                    cc_addresses.append(str(getattr(recipient, "Address", "")))
        return Message(
            id=f"outlook:message:{item.EntryID}", subject=str(getattr(item, "Subject", "")),
            sender=str(getattr(item, "SenderEmailAddress", "") or getattr(item, "SenderName", "")),
            to=tuple(to_addresses),
            cc=tuple(cc_addresses),
            received_at=received_at, body=str(getattr(item, "Body", ""))[: self.max_body_chars],
            unread=bool(getattr(item, "UnRead", False)), has_attachments=count > 0,
            folder_id=folder_id, preview=str(getattr(item, "Body", ""))[:300],
        )

    def _item(self, message_id: str, folder_id: str | None) -> tuple[Any, Any]:
        if not message_id.startswith("outlook:message:"):
            raise BackendError("invalid Outlook message_id")
        folder = self._folder(folder_id)
        store_id = getattr(folder, "StoreID", None)
        item = self._worker._namespace.GetItemFromID(message_id.removeprefix("outlook:message:"), store_id) if store_id else self._worker._namespace.GetItemFromID(message_id.removeprefix("outlook:message:"))
        return item, folder

    def get_message(self, message_id: str, folder_id: str | None = None) -> Message:
        return self._worker.call(lambda: self._message(self._item(message_id, folder_id)[0], folder_id))

    def list_attachments(self, message_id: str, folder_id: str | None = None) -> list[Attachment]:
        def run() -> list[Attachment]:
            item, _ = self._item(message_id, folder_id)
            return [Attachment(str(i), str(item.Attachments.Item(i).FileName), str(getattr(item.Attachments.Item(i), "Type", "application/octet-stream")), int(getattr(item.Attachments.Item(i), "Size", 0) or 0)) for i in range(1, int(item.Attachments.Count) + 1)]
        return self._worker.call(run)

    def save_attachment(self, message_id: str, attachment_id: str, directory: str, folder_id: str | None = None) -> dict:
        def run() -> dict:
            item, _ = self._item(message_id, folder_id)
            attachment = item.Attachments.Item(int(attachment_id))
            size = int(getattr(attachment, "Size", 0) or 0)
            if size > self.max_attachment_bytes:
                raise BackendError("attachment exceeds configured safety limit")
            target = self.policy.target(directory, str(attachment.FileName))
            temporary = target.with_name(target.name + ".outlook-download")
            attachment.SaveAsFile(str(temporary))
            try:
                payload = temporary.read_bytes()
                self.policy.write_new_file(target, payload)
            finally:
                temporary.unlink(missing_ok=True)
            return {"path": str(target), "filename": str(attachment.FileName), "size": size}
        return self._worker.call(run)

    def create_draft(self, draft: Draft) -> dict:
        def run() -> dict:
            item = self._worker._outlook.CreateItem(0)
            item.To = ";".join(draft.to); item.CC = ";".join(draft.cc); item.BCC = ";".join(draft.bcc)
            item.Subject = draft.subject; item.Body = draft.body
            for path in draft.attachments:
                item.Attachments.Add(os.fspath(self.policy.attachment(path, self.max_attachment_bytes)))
            item.Save()
            return {"created": True, "id": f"outlook:message:{getattr(item, 'EntryID', '')}", "folder": "Drafts"}
        return self._worker.call(run)

    def send_email(self, draft: Draft) -> dict:
        def run() -> dict:
            item = self._worker._outlook.CreateItem(0)
            item.To = ";".join(draft.to); item.CC = ";".join(draft.cc); item.BCC = ";".join(draft.bcc)
            item.Subject = draft.subject; item.Body = draft.body
            for path in draft.attachments:
                item.Attachments.Add(os.fspath(self.policy.attachment(path, self.max_attachment_bytes)))
            item.Send()
            return {"sent": True, "recipients": list(draft.to)}
        return self._worker.call(run)
