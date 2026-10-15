# Outlook Email Agent Plugin

This directory is an Agent Plugins 1.0.0 package containing:

- `plugin.json` — package metadata;
- `mcp.json` — local stdio MCP configuration;
- `skills/outlook-email/SKILL.md` — safe-use instructions.

## Important limitation

The package configuration launches the Python module `outlook_email_mcp`. The
module must already be installed in the plugin data environment. Agent Plugins
does not define a portable dependency-install step, and OmniRush.ai's current
organization importer reports local `stdio` servers without installing them.

For this repository, install the server once on Windows:

```powershell
py -3 -m pip install -e ".[windows]"
```

Then configure the client using `mcp.json`, changing `cwd` to the checkout or
installed project directory if the client does not expand `PLUGIN_DATA`.

Classic Outlook must be installed for Outlook/PST access. Set
`OUTLOOK_EMAIL_BACKEND=auto` to prefer Outlook and fall back to IMAP when
Outlook is unavailable. IMAP/SMTP settings are documented in the repository's
`docs/NETWORK-SOLUTIONS.md`.

For security, configure `OUTLOOK_EMAIL_ATTACHMENT_ROOTS` before using drafts or
sends with attachments. The server rejects attachment files outside those
roots and refuses to overwrite existing export files.

The package never contains passwords, app passwords, OAuth tokens, PST files,
or authorization headers.

## ChatGPT connection

ChatGPT does not install or launch this local stdio package directly. Start the
server in loopback Streamable HTTP mode and connect it through an OpenAI Secure
MCP Tunnel, then add it in ChatGPT web under **Plugins → + → Add custom MCP
server → Tunnel**. The server rejects non-loopback HTTP binds by design.
