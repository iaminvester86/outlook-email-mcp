# Outlook Email MCP

Windows-first MCP server for Classic Outlook, mounted PST stores, and TLS-protected
IMAP/POP3 accounts. **Read-only mailbox access is the default.** Sending and saved
drafts require separate opt-ins. Version 0.2.0 includes security-breaking changes;
read [the migration guide](docs/MIGRATION-0.2.md) before upgrading.

## Install

Use Python 3.11 or newer; Python 3.14 is the tested Windows baseline. Classic
Outlook is required for COM/PST access. New Outlook does not expose this COM API.

```powershell
git clone https://github.com/iaminvester86/outlook-email-mcp.git
cd outlook-email-mcp
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[windows]"
```

For the audited Windows/Python 3.14 dependency snapshot, install
`requirements/runtime-windows-py314.txt` first, then install the project with
`pip install --no-deps -e .`. The snapshot is platform-specific; other platforms
should resolve supported dependencies from `pyproject.toml` and run an audit.

## Connect to Outlook/PST safely

First discover available store IDs in your own local terminal:

```powershell
.\.venv\Scripts\python.exe -m outlook_email_mcp --list-outlook-stores
```

Then allow only the stores you intend to expose. Copy exact IDs from that local
output; separate multiple IDs with semicolons. Store names are not accepted as IDs.

```powershell
$env:OUTLOOK_EMAIL_BACKEND = "outlook"
$env:OUTLOOK_EMAIL_OUTLOOK_STORES = "outlook:store:PASTE_SELECTED_STORE_ID"
.\.venv\Scripts\python.exe -m outlook_email_mcp
```

An empty allowlist exposes **no Outlook stores or messages**, even if the caller
already knows an entry ID. The discovery command is local setup functionality;
it is not an MCP tool. Open a PST in Outlook first, then explicitly allow its store.
Use `list_folders` and pass the returned folder ID when reading a non-default store.

The server speaks MCP over stdio and waits silently for protocol input. Configure
your MCP client with the absolute path to this project's `.venv\Scripts\python.exe`,
arguments `-m outlook_email_mcp`, and your approved non-secret settings. See
[the client template](examples/mcp-client.config.json). Diagnostics go to stderr.

## IMAP or POP3

Set `OUTLOOK_EMAIL_BACKEND=imap` or `pop3`, the corresponding host and username,
and a secure credential source. SMTP is optional for read-only use. All mail
connections validate certificates and hostnames; plaintext modes are rejected.

```powershell
$env:OUTLOOK_EMAIL_BACKEND = "imap"
$env:IMAP_HOST = "imap.example.test"
$env:IMAP_USERNAME = "mailbox@example.test"
$env:OUTLOOK_EMAIL_CREDENTIAL_BACKEND = "keyring"
$env:OUTLOOK_EMAIL_CREDENTIAL_SERVICE = "outlook-email-mcp"
.\.venv\Scripts\python.exe -c "import getpass,keyring; u=input('Mailbox username: '); keyring.set_password('outlook-email-mcp',u,getpass.getpass('Password: '))"
```

Replace example addresses/hosts locally. For POP3 use `POP3_HOST`, `POP3_USERNAME`,
and port 995. POP3 is inbox-only, has no reliable read/unread state, and cannot save
drafts. IMAP defaults to port 993. SMTP uses STARTTLS on 587, or implicit TLS with
`SMTP_SSL=true` and the provider's port (commonly 465). See
[credentials](docs/CREDENTIALS.md) and [network setup](docs/NETWORK-SOLUTIONS.md).

`auto` selects Outlook first, then IMAP, then POP3. These can represent different
accounts. Prefer an explicit backend and inspect `status` before reading or writing.

## Drafts and sending

`prepare_draft` only returns a validated preview. It does not save or send anything.
To save drafts, explicitly set `OUTLOOK_EMAIL_ENABLE_DRAFTS=true` before starting
the server. To enable sending, set `OUTLOOK_EMAIL_ENABLE_SEND=true`. Disabled
write tools are not advertised. Outlook writes additionally require
`OUTLOOK_EMAIL_OUTLOOK_SEND_ACCOUNT` to match one configured account whose delivery
store is allowlisted. Network sending requires SMTP host, username, and credentials.

Every send requires **both** `confirm=true` and a fresh approval in a separate
window on the server computer. The window shows the selected sender, every To/Cc/Bcc
recipient, the complete subject/body, and attachment names, sizes, and SHA-256
hashes. Cancel, timeout, or an unavailable desktop/Tkinter blocks the send. No
environment flag, MCP parameter, or approval token disables this local approval.

Attachment bytes are captured before review and those exact bytes are sent, even
if the original file changes during approval. Approvals are never reused. Automated
clients must not click the approval window on the user's behalf. This boundary
assumes the server's OS account and desktop are trusted; it cannot protect against
software that already has arbitrary shell or UI control under that same account.

## Attachments and limits

Attachment exports are disabled until `OUTLOOK_EMAIL_SAVE_ROOTS` is configured.
Outbound source files are separately disabled until `OUTLOOK_EMAIL_ATTACHMENT_ROOTS`
is configured. Use dedicated directories, not your entire home folder or drive.
Root lists use `;` on Windows and the platform path separator elsewhere. Exports
reject traversal, unsafe filenames, and existing targets. Outlook downloads use a
private random scratch directory; exported attachments are never executed.

| Setting | Default | Purpose |
| --- | --- | --- |
| `OUTLOOK_EMAIL_MAX_RESULTS` | 50 | Maximum search results |
| `OUTLOOK_EMAIL_MAX_BODY_CHARS` | 20000 | Returned message body limit |
| `OUTLOOK_EMAIL_MAX_ATTACHMENT_BYTES` | 26214400 | Each attachment limit |
| `OUTLOOK_EMAIL_MAX_MESSAGE_BYTES` | 52428800 | Inbound message / outbound decoded payload limit |
| `OUTLOOK_EMAIL_NETWORK_TIMEOUT` | 30 | Network timeout in seconds |
| `OUTLOOK_EMAIL_APPROVAL_TIMEOUT` | 120 | Local send decision timeout in seconds |

Large inbound messages are size-checked before retrieval. A hostile mail provider
is still outside the trust boundary. Search results include bounded body text, so
mail returned through MCP is visible to the client and any AI service it uses.

## HTTP and tunnels

Prefer local stdio. Optional HTTP/SSE listeners are loopback-only and require a
random bearer token in `OUTLOOK_EMAIL_HTTP_TOKEN` (at least 32 printable ASCII
characters). Missing, incorrect, or duplicate Authorization headers are rejected
before MCP processing. Host and browser Origin checks also remain enabled.

An external tunnel must preserve those controls and provide HTTPS and its own
access policy. Never publish the listener directly. Clients that cannot supply
the bearer header cannot use this HTTP configuration; use stdio instead. See
[HTTP setup](docs/CHATGPT-TUNNEL.md). No hosted-client UI, plan eligibility, or
tunnel compatibility is assumed by this repository.

## Tools

Always available: `status`, `list_stores`, `list_folders`, `search`, `get_message`,
`list_attachments`, `save_attachment`, `prepare_draft`. Conditional:
`create_draft` and `send_email`. There are no delete/move tools, arbitrary COM
commands, or arbitrary PST-opening tools. See [the tool reference](docs/TOOLS.md).

## Repository layout

```text
src/outlook_email_mcp/    Server, policies, local approval UI, and backends
tests/                  Offline unit, protocol, authentication, and regression tests
docs/                   Setup, threat model, migration, and validation report
examples/               Credential-free client template
plugin/outlook-email-mcp/ Portable plugin manifests and safe-use skill
requirements/           Audited Windows/Python 3.14 dependency snapshots
scripts/                Build and security-check helpers
.github/workflows/      Tests, dependency audit, static checks, and secret scanning
```

Generated `build/`, `dist/`, bytecode, environment files, credentials, and mail
exports are ignored. Release packages are built from source rather than committed
as duplicate executable copies. The bundled plugin must use the interpreter where
the server was installed; see [plugin installation](plugin/outlook-email-mcp/INSTALL.md).

## Development and security checks

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[windows,test,dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m bandit -r src
.\.venv\Scripts\python.exe -m pip_audit --disable-pip --no-deps -r requirements/runtime-windows-py314.txt
.\.venv\Scripts\python.exe scripts/run_gitleaks.py
.\.venv\Scripts\python.exe -m build
.\.venv\Scripts\python.exe scripts/build_plugin.py
```

Security CI runs with read-only repository permissions and commit-pinned actions.
Use [SECURITY.md](SECURITY.md) for reporting, [the threat model](docs/SECURITY.md)
for trust boundaries, and [the validation report](docs/SECURITY-REVIEW.md) for tested
behavior and remaining limitations. Automated checks do not certify a live mailbox
configuration or replace deployment-specific review.
