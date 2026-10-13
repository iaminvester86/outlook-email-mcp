# Outlook Email MCP

Windows-first MCP server for bounded, non-destructive email access. It uses a
single-threaded Outlook COM worker when Outlook is available, and can fall back
to an IMAP/SMTP account over TLS.

## Run

```powershell
py -m pip install -e ".[windows]"
$env:OUTLOOK_EMAIL_BACKEND = "auto"
outlook-email-mcp
```

For the IMAP fallback, configure `IMAP_HOST`, `IMAP_USERNAME`,
`IMAP_PASSWORD`, `SMTP_HOST`, `SMTP_USERNAME`, and `SMTP_PASSWORD`. Ports are
configurable with `IMAP_PORT` (default `993`) and `SMTP_PORT` (default `587`).
IMAP TLS cannot be disabled. SMTP uses STARTTLS by default; set `SMTP_SSL=true`
for implicit TLS instead.

Attachment saves are disabled unless `OUTLOOK_EMAIL_SAVE_ROOTS` contains one or
more allowed directories separated by the platform path separator. Results,
bodies, and attachment sizes are bounded by `OUTLOOK_EMAIL_MAX_RESULTS`,
`OUTLOOK_EMAIL_MAX_BODY_CHARS`, and `OUTLOOK_EMAIL_MAX_ATTACHMENT_BYTES`.

## Tools

The server exposes `status`, `list_stores`, `list_folders`, `search`,
`get_message`, `list_attachments`, `save_attachment`, `prepare_draft`,
`create_draft`, and `send_email`. `send_email` requires `confirm=true` in the
same call. There are no delete or move operations.

All logging is configured for stderr so stdout remains a clean MCP stdio
transport.
