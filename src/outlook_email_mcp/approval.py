"""A local, interactive approval boundary, never exposed as an MCP tool."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import replace

from .errors import PolicyError
from .models import AttachmentPayload, Draft
from .policy import SafePathPolicy


def snapshot_draft(draft: Draft, policy: SafePathPolicy, max_attachment_bytes: int, max_message_bytes: int) -> Draft:
    """Freeze attachments before review; sending never reopens their source paths."""
    payloads = []
    total = len(draft.body.encode("utf-8"))
    for path in draft.attachments:
        filename, data = policy.read_attachment(path, max_attachment_bytes)
        total += len(data)
        if total > max_message_bytes:
            raise PolicyError("outbound message exceeds configured safety limit")
        payloads.append(AttachmentPayload(filename, data))
    if total > max_message_bytes:
        raise PolicyError("outbound message exceeds configured safety limit")
    return replace(draft, payloads=tuple(payloads))


def approval_details(draft: Draft, identity: dict) -> dict:
    if draft.payloads is None:
        raise PolicyError("message attachments must be frozen before approval")
    return {
        "sender": identity,
        "to": list(draft.to),
        "cc": list(draft.cc),
        "bcc": list(draft.bcc),
        "subject": draft.subject,
        "body": draft.body,
        "attachments": [
            {"filename": p.filename, "bytes": len(p.data), "sha256": hashlib.sha256(p.data).hexdigest()}
            for p in draft.payloads
        ],
    }


def require_local_approval(details: dict, timeout: int = 120) -> None:
    """Show the full immutable plan on the server desktop. No token/flag bypass."""
    accepted = False
    root = None
    try:
        import tkinter as tk
        from tkinter.scrolledtext import ScrolledText

        root = tk.Tk()
        root.title("Outlook Email MCP - approve one email")
        root.geometry("820x680")
        tk.Label(
            root,
            text="Review every recipient, the complete body, and attachments.\n"
            "This approval sends this message once. Cancel is the default.",
            pady=12,
        ).pack()
        text = ScrolledText(root, wrap="word", font=("Consolas", 10))
        # JSON escaping makes terminal controls, bidi controls, and invisible
        # Unicode visible rather than allowing mail content to alter this UI.
        text.insert("1.0", json.dumps(details, ensure_ascii=True, indent=2))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=12)
        buttons = tk.Frame(root)
        buttons.pack(pady=12)

        def approve() -> None:
            nonlocal accepted
            accepted = True
            root.destroy()

        cancel = tk.Button(buttons, text="Cancel", width=20, command=root.destroy)
        cancel.pack(side="left", padx=12)
        tk.Button(buttons, text="Send this exact email", width=24, command=approve).pack(side="left")
        cancel.focus_set()
        root.bind("<Escape>", lambda event: root.destroy())
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        root.after(timeout * 1000, root.destroy)
        root.mainloop()
    except Exception:
        raise PolicyError("local send approval is unavailable; no message was sent") from None
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                logging.getLogger(__name__).debug("approval window was already closed")
    if not accepted:
        raise PolicyError("local send approval was declined or expired; no message was sent")
