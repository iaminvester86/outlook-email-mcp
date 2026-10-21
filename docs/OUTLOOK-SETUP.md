# Classic Outlook and mounted PST setup

Use an interactive Windows desktop under the intended non-administrator user.
Install Classic Outlook, sign in to the intended profile, and install this
project's `windows` extra into the interpreter used by the MCP client. New Outlook
does not implement this COM interface.

Open any intended PST in Outlook first. This project does not mount arbitrary PST
paths, repair PSTs, or bypass Outlook security prompts. Back up a PST through the
organization's approved process; do not copy or modify a live PST file underneath
Outlook.

Discover StoreIDs locally:

```powershell
.\.venv\Scripts\python.exe -m outlook_email_mcp --list-outlook-stores
```

Set `OUTLOOK_EMAIL_BACKEND=outlook` and add only selected returned IDs to
`OUTLOOK_EMAIL_OUTLOOK_STORES`, separated by semicolons. Full `outlook:store:`
IDs or their raw StoreID suffixes are accepted. Empty lists deny all mailbox
access. This setup command is not exposed through MCP.

Start with `status`, `list_stores`, and `list_folders`. Use exact returned folder
IDs for PSTs, archives, or non-default mailboxes. Every folder and actual message
parent store is checked; knowing a message ID cannot bypass the allowlist.

For draft creation or sending, also set `OUTLOOK_EMAIL_OUTLOOK_SEND_ACCOUNT` to the
exact SMTP address of one Outlook account. Its delivery store must be allowlisted.
Drafts are created in that account's Drafts folder, and SendUsingAccount is set
explicitly. A PST without an Outlook sending account is not a sender identity.

`OUTLOOK_EMAIL_ENABLE_DRAFTS` and `OUTLOOK_EMAIL_ENABLE_SEND` are separate opt-ins.
Sending always requires a fresh approval on this desktop. Keep Office, antivirus,
Python, and dependencies updated. Do not disable Outlook Object Model Guard or
run this COM workflow as an unattended Windows service.
