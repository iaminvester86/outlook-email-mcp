# ChatGPT Secure MCP Tunnel setup

ChatGPT web cannot launch a local Python stdio MCP process. It can connect to a
custom MCP server through a public HTTPS endpoint or an OpenAI Secure MCP
Tunnel. This repository supports the tunnel path by serving Streamable HTTP on
loopback.

## 1. Install and configure locally

From the repository root in PowerShell:

```powershell
py -3 -m pip install -e ".[windows]"
$env:OUTLOOK_EMAIL_BACKEND = "auto"
$env:OUTLOOK_EMAIL_TRANSPORT = "streamable-http"
$env:OUTLOOK_EMAIL_HTTP_HOST = "127.0.0.1"
$env:OUTLOOK_EMAIL_HTTP_PORT = "8000"
$env:OUTLOOK_EMAIL_HTTP_PATH = "/mcp"
```

For IMAP/SMTP, configure the host and usernames. Prefer Windows Credential
Manager for passwords:

```powershell
$env:OUTLOOK_EMAIL_CREDENTIAL_BACKEND = "keyring"
$env:OUTLOOK_EMAIL_CREDENTIAL_SERVICE = "outlook-email-mcp"
python -c "import keyring; keyring.set_password('outlook-email-mcp', 'you@example.com', 'ENTER_LOCALLY_ONLY')"
```

Do not paste a real password into ChatGPT, a repository, or a command that will
be saved in shell history. Use the actual mailbox username in `IMAP_USERNAME`
and `SMTP_USERNAME`.

For a POP3-only provider, set `OUTLOOK_EMAIL_BACKEND=pop3`, configure
`POP3_HOST`, `POP3_PORT=995`, and `POP3_USERNAME`, and keep the SMTP settings
for outbound mail. See `docs/NETWORK-SOLUTIONS.md` for POP3 limitations.

## 2. Start the local server

```powershell
py -3 -m outlook_email_mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

The process should log a loopback Uvicorn listener. The server rejects public
bind addresses such as `0.0.0.0` in HTTP mode. Do not port-forward port 8000
or place it directly on the Internet.

## 3. Configure the Secure MCP Tunnel

Use OpenAI's Secure MCP Tunnel tooling to target the local endpoint:

```text
http://127.0.0.1:8000/mcp
```

The tunnel setup and tunnel ID are managed by OpenAI. This repository does not
create, store, or transmit tunnel credentials.

## 4. Add the custom server in ChatGPT

In ChatGPT web, open **Plugins → + → Add custom MCP server**, choose **Tunnel**,
select the Secure MCP Tunnel or enter its tunnel ID, review the discovered
tools and permissions, and create the plugin.

This feature is subject to the ChatGPT plan, workspace role, and RBAC policy.
OpenAI's current Help Center states that full custom MCP support is available
for Business and Enterprise/Edu workspaces, with permissions controlled by
admins and owners.

## 5. Test read-only operations first

Start a new conversation and select the created plugin. Test `status`,
`list_stores`, `list_folders`, a narrow `search`, and `get_message` in that
order. Only after those work should you test `prepare_draft` and `create_draft`.
`send_email` requires `confirm=true`, and ChatGPT workspace action permissions
should be reviewed before enabling it.

ChatGPT stores a reviewed tool snapshot. After changing this repository or
adding tools, refresh the app's tool list in ChatGPT workspace settings and
review the changes before using it again.

This does not make local PST data available when the Windows PC is offline, does
not create a public relay, and does not bypass ChatGPT workspace permissions.
