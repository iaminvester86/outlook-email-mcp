# Authenticated HTTP and tunnel setup

Local stdio is recommended. A remote MCP client cannot launch this local Python
process; an HTTP-capable client needs a separately secured connection to the
server computer. This guide describes this server's requirements, without assuming
any hosted product's current UI, subscription, or tunnel support.

Configure the mailbox, Outlook store allowlist, and credential source first. Then:

```powershell
$env:OUTLOOK_EMAIL_TRANSPORT = "streamable-http"
$env:OUTLOOK_EMAIL_HTTP_HOST = "127.0.0.1"
$env:OUTLOOK_EMAIL_HTTP_PORT = "8000"
$env:OUTLOOK_EMAIL_HTTP_TOKEN = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
.\.venv\Scripts\python.exe -m outlook_email_mcp
```

This captures the generated token into the server process environment without
printing it in the terminal. Supply the same token to the client's protected
secret setting. Do not put it in a URL, committed JSON, command arguments, or chat.
It is lost when that environment/session ends; use a protected secret manager for
persistent deployments and restart the server after rotation.

The default endpoint is `http://127.0.0.1:8000/mcp`. Every request needs
`Authorization: Bearer <token>`. The local listener rejects absent/wrong tokens,
duplicate Authorization headers, non-loopback binds, unapproved Host headers,
and browser Origins outside the configured loopback addresses.

SSE uses the same authentication policy, including its separate message POST
endpoint. The client must send the bearer header on every transport request.

If using a tunnel/reverse proxy, it must provide HTTPS, restrict access to the
intended user, retain bearer authentication, and forward the correct loopback
Host. Do not weaken host/origin checks to make an arbitrary proxy work. Never
port-forward the listener directly onto a LAN or the Internet.

Compatibility must be tested with the selected client. A client/tunnel that cannot
preserve the required authentication headers is unsupported by this setup; use
local stdio instead. This project does not create tunnel credentials or implement
an OAuth authorization server.

Remote sending still requires a person to approve the complete message on the
server's desktop. HTTP access does not enable unattended sends or bypass mailbox
store restrictions, disabled write tools, or attachment policies.
