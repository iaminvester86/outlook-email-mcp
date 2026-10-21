# Credential handling

Outlook COM reuses the signed-in Windows profile; the server does not need or store
its password. IMAP, POP3, and SMTP use either `env` or `keyring` credentials.

## Windows Credential Manager

Install the `windows` extra and set:

```powershell
$env:OUTLOOK_EMAIL_CREDENTIAL_BACKEND = "keyring"
$env:OUTLOOK_EMAIL_CREDENTIAL_SERVICE = "outlook-email-mcp"
.\.venv\Scripts\python.exe -c "import getpass,keyring; u=input('Mailbox username: '); keyring.set_password('outlook-email-mcp',u,getpass.getpass('Password: '))"
```

The username must exactly match `IMAP_USERNAME`, `POP3_USERNAME`, or `SMTP_USERNAME`.
Use the same entry only when those services intentionally share a credential.
Missing entries or keyring errors fail closed with generic diagnostics. Check that
the `keyring` installation selects the intended OS credential provider; do not
install plaintext fallback providers.

## Protected environment

`OUTLOOK_EMAIL_CREDENTIAL_BACKEND=env` is the compatibility default. It reads
`IMAP_PASSWORD`, `POP3_PASSWORD`, and `SMTP_PASSWORD`. Supply these from a protected
process environment or secret manager. They can be inspected by privileged local
processes; they are not encrypted merely because they are environment variables.

Never embed passwords/tokens in command arguments, client JSON, committed files,
screenshots, issue reports, or chat. `.env.example` documents variable names only;
the server does not load `.env` files automatically. Password/token fields are
excluded from the Settings diagnostic representation and MCP status output.

## HTTP bearer token

HTTP/SSE requires `OUTLOOK_EMAIL_HTTP_TOKEN` separately from mailbox passwords.
Generate a new random token for this server, pass it to the client through a
protected secret setting, and rotate it if exposed. Do not reuse a mailbox password.
HTTP clients send `Authorization: Bearer <token>` on every request.

## Rotation

Change mailbox passwords at the provider first, update the keyring/secret manager,
and restart the server. Remove unused entries with an interactive local command:

```powershell
.\.venv\Scripts\python.exe -c "import keyring; u=input('Mailbox username: '); keyring.delete_password('outlook-email-mcp',u)"
```

Prefer provider-supported app passwords for accounts with MFA. OAuth token flows
are not implemented by these mail backends; do not assume OAuth support from an
email provider means this password-based client will work.
