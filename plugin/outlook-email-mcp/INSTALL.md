# Outlook Email MCP plugin 0.2.0

This portable package contains `plugin.json`, `mcp.json`, and the safe-use skill in
`skills/outlook-email/SKILL.md`. It launches a local Python MCP process; it does not
bundle Python, install dependencies, or grant remote access to your desktop.

Install the server from the repository in a dedicated virtual environment, then
replace the `command` in your imported MCP configuration with that environment's
absolute Python executable. The included `python` command is a template for
clients with an explicitly configured runtime environment.

Follow the repository README to configure allowed Outlook StoreIDs or a network
account and protected credentials. Writes are disabled by default. Outlook writes
require an explicit sending account and an allowed delivery store. Every send
requires a person to approve the full message in a local desktop window; no host
confirmation alone bypasses this check.

Use local stdio when possible. Hosted clients cannot directly launch this local
process. Optional HTTP/tunnel use requires the separate bearer/loopback/HTTPS
controls in `docs/CHATGPT-TUNNEL.md` from the repository. Client compatibility must
be tested; this package does not assume a hosted product's importer behavior.

Do not add real credentials to manifests, skills, client templates, or archives.
Refresh the client's tool inventory after upgrading; disabled write tools are
absent, and IMAP message IDs changed. The package identity remains
`outlook-email-mcp`; version 0.2.0 has breaking security defaults.
