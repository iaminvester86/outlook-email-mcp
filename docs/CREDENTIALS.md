# Credential handling

The server supports two credential modes for IMAP, POP3, and SMTP.

## Windows Credential Manager (recommended)

Set:

```text
OUTLOOK_EMAIL_CREDENTIAL_BACKEND=keyring
OUTLOOK_EMAIL_CREDENTIAL_SERVICE=outlook-email-mcp
```

Store passwords interactively so they do not appear in shell history:

```powershell
py -c "import getpass, keyring; u=input('Username: '); keyring.set_password('outlook-email-mcp', u, getpass.getpass('Password: '))"
```

Use the exact same username in `IMAP_USERNAME`, `POP3_USERNAME`, or
`SMTP_USERNAME`. The server requests the password from the local keyring when
it starts. It never returns passwords through MCP tools and never includes
them in status output or error messages.

## Environment mode

`OUTLOOK_EMAIL_CREDENTIAL_BACKEND=env` reads `IMAP_PASSWORD`,
`POP3_PASSWORD`, and `SMTP_PASSWORD`. This is supported for isolated local
testing and container deployments with a protected secret manager, but process
environment variables may be visible to privileged local processes. Never put
these values in `.env.example`, client JSON, Git, ChatGPT, logs, screenshots,
or support tickets.

## What is protected

- Outlook/PST mode uses the signed-in Windows Outlook profile; this server does
  not store Outlook passwords.
- Keyring mode stores mailbox passwords through the operating system's secure
  credential provider.
- Status output includes hostnames and selected backend only, never passwords.
- Logs go to stderr and redact application errors; protocol debug logging is not
  enabled by default.
- Tunnel credentials are owned by the tunnel provider and are not stored in
  this repository.

## Rotation and removal

Rotate a mailbox password at the provider, then replace the keyring entry.
Remove an entry after testing with:

```powershell
py -c "import keyring; u=input('Username: '); keyring.delete_password('outlook-email-mcp', u)"
```

Do not use the delete command until you have confirmed the username.
