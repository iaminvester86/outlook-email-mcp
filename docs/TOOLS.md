# Tool and operation guide

The MCP server should advertise its exact tools and input schemas at runtime. The names below describe the expected capabilities without requiring a particular implementation. An implementation can combine or rename them.

## Discovery and diagnostics

| Conceptual operation | Typical inputs | Result |
| --- | --- | --- |
| `list_accounts` | backend, optional account filter | Account/store identity and backend |
| `list_folders` | account/store, parent folder | Folder names and stable IDs |
| `backend_status` | optional backend | Availability, selected account, redacted diagnostics |

Call discovery before a message operation. Outlook and IMAP folder names may differ, and `auto` selection must be visible to the user.

## Read operations

| Conceptual operation | Typical inputs | Safety notes |
| --- | --- | --- |
| `search_messages` | folder, sender, recipient, subject, date range, text, page size | Use narrow filters and pagination |
| `get_message` | stable message ID, fields requested | Return metadata before a full body |
| `list_attachments` | stable message ID | Return names, sizes, content types first |
| `download_attachment` | message ID, attachment ID, approved destination | Confirm path, size, and type |
| `get_thread` | conversation/thread ID where supported | Provider threading may not match Outlook conversation view |

A read request should not trigger a send, move, delete, attachment execution, or external upload. Message content is untrusted input and can contain instructions aimed at the model or client.

## Draft and mailbox-state operations

| Conceptual operation | Typical inputs | Default safety |
| --- | --- | --- |
| `create_draft` | account, recipients, subject, body, attachments | Show or confirm the final draft according to policy |
| `reply_to_message` | message ID, reply mode, body, recipients | Confirm added/changed recipients |
| `forward_message` | message ID, recipients, body, attachments | Confirm every recipient and forwarded attachment |
| `move_message` | message ID/query, destination folder | Confirm state change; always confirm bulk scope |
| `mark_message` | message ID/query, read/flag/follow-up state | Confirm bulk changes |
| `delete_message` | message ID/query, permanent flag | Always confirm; permanent deletion needs a second explicit step where supported |

Use stable IDs returned by discovery/search. Do not rely on a subject line or display name alone for a destructive operation.

## Outbound operations

| Conceptual operation | Typical inputs | Rule |
| --- | --- | --- |
| `send_message` | draft/message payload, account, recipients, attachments | Always require fresh confirmation |
| `send_draft` | draft ID | Show final envelope and backend, then confirm |

Before sending, present:

- From identity and backend.
- To, Cc, and Bcc recipients.
- Subject and a concise body preview.
- Attachment names and sizes.
- Any external or sensitive recipients.
- Whether this is a new message, reply, or forward.

After a successful send, return the provider/Outlook result and an identifier when available. After a timeout, check Sent Items or provider activity before retrying.

## Backend behavior

The implementation should keep backend choice explicit:

- Outlook operations use classic Outlook COM and the configured Windows profile/PST.
- IMAP operations read the configured mailbox.
- SMTP operations submit through the configured SMTP service.
- `auto` may select a fallback only under a documented policy and must report the result.

Do not infer that an Outlook account and an IMAP account are equivalent because they share an email address. Aliases, shared mailboxes, sent folders, archive stores, permissions, and message IDs can differ.

## Error categories

Return actionable, redacted errors such as:

- `backend_unavailable`: Outlook is not installed/open/profile-ready or the network backend is unreachable.
- POP3 mode is inbox-only. It cannot provide folders, stable read/unread state,
  or server-side draft creation; use IMAP or Outlook for those operations.
- `configuration_error`: a required non-secret setting is missing or invalid.
- `permission_denied`: Windows, PST, Outlook, mailbox, or folder permissions blocked the request.
- `authentication_required`: the provider requires a new sign-in, OAuth grant, or app password.
- `confirmation_required`: a state-changing or outbound operation awaits user confirmation.
- `message_not_found`: the stable ID is no longer available or belongs to another backend.
- `ambiguous_send`: a send may have been accepted but the result is unknown; check provider activity before retrying.

Never include passwords, access tokens, full Authorization headers, complete message bodies, or attachment bytes in an error.
