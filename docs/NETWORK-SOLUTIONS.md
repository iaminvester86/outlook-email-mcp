# IMAP/POP3/SMTP network setup and troubleshooting

Use the network backend when classic Outlook is unavailable, when a provider supports a stable IMAP/SMTP or POP3/SMTP interface, or when the deployment needs a provider connection independent of a local PST. IMAP and POP3 read mail; SMTP submits outbound mail. Neither protocol reads a local PST.

## Recommended connection settings

| Service | Typical port | Transport | Purpose |
| --- | ---: | --- | --- |
| IMAP | 993 | TLS from connection start | Read folders/messages |
| POP3 | 995 | TLS from connection start | Read inbox messages |
| SMTP submission | 587 | STARTTLS | Submit messages |
| SMTP submission | 465 | Implicit TLS | Submit messages where provider documents it |

Use the hostnames, ports, authentication method, and certificate requirements documented by the mail provider. A provider may disable password authentication, require OAuth, or require an app password when multifactor authentication is enabled.

Example configuration shape:

```text
OUTLOOK_EMAIL_BACKEND=imap
IMAP_HOST=imap.example.test
IMAP_PORT=993
IMAP_TLS=true
IMAP_USERNAME=
IMAP_PASSWORD=
SMTP_HOST=smtp.example.test
SMTP_PORT=587
SMTP_TLS=true
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
```

For POP3-only mailboxes, use the same shape with:

```text
OUTLOOK_EMAIL_BACKEND=pop3
POP3_HOST=pop.example.test
POP3_PORT=995
POP3_TLS=true
POP3_USERNAME=
SMTP_HOST=smtp.example.test
SMTP_PORT=587
SMTP_TLS=true
SMTP_USERNAME=
SMTP_FROM=
```

POP3 has no folders or server-side draft storage. Message identifiers are
validated against a short content digest so mailbox reordering cannot silently
turn an old identifier into a different message. POP3 does not reliably expose
read/unread state, so the server reports messages as unread-state unknown.

For a safer Windows setup, set `OUTLOOK_EMAIL_CREDENTIAL_BACKEND=keyring` and
store the IMAP and SMTP passwords in Windows Credential Manager using the
`keyring` package. Keep `IMAP_USERNAME` and `SMTP_USERNAME` as non-secret
identifiers. Environment variables remain supported for isolated testing but
are more exposed to local process inspection.

The `.test` hostname above is a documentation placeholder. Replace it with the provider's published endpoint. Keep credentials blank in templates and provide them through a protected local mechanism.

## Windows connectivity checks

Run these checks from the same Windows account and machine that runs the MCP server:

```powershell
Test-NetConnection imap.example.test -Port 993
Test-NetConnection smtp.example.test -Port 587
```

`TcpTestSucceeded: True` confirms that a TCP connection reached the endpoint. It does not prove that TLS, authentication, mailbox permissions, or SMTP submission policy will succeed.

If the organization uses a proxy, inspect the implementation's proxy support. Many mail libraries connect directly and do not use the browser's proxy automatically. Ask the network administrator for approved egress rules rather than disabling TLS or opening broad firewall access.

## TLS and authentication

- Validate the server certificate and hostname.
- Use the provider's documented TLS mode. Do not use STARTTLS on a port that expects implicit TLS, or the reverse.
- Keep system time correct; certificate and OAuth failures often follow clock drift.
- Prefer OAuth or an app password when the provider requires multifactor authentication.
- Use a dedicated test mailbox and least-privilege account.
- Set the SMTP `From` address only to a permitted identity. Providers may reject mismatched sender addresses or rewrite them.
- Avoid logging raw protocol sessions. Authentication exchanges and message bodies can appear in debug output.

## Common failures

### DNS or connection timeout

Check DNS resolution, VPN state, firewall egress, proxy requirements, and provider service status. Test the exact hostname configured by the server. A successful browser connection does not prove that the Python/Node process can reach the same host.

### Connection refused

Check the port and transport mode. Providers often block port 25 for client submission; use 587 or 465 as documented. Confirm that a local security product is not blocking the process.

### TLS certificate or handshake error

Check the hostname, system clock, trusted root certificates, TLS version policy, and whether the selected port expects implicit TLS or STARTTLS. Do not set a “skip verification” option in production.

### Authentication rejected

Verify that IMAP is enabled, SMTP submission is enabled, the username format is correct, and the provider allows the selected authentication method. Check for an app-password or OAuth requirement, account lockout, conditional access, or an IP allowlist. Rotate a credential that has appeared in a log.

### IMAP folder or message mismatch

Providers expose localized or special-use folder names differently. List folders first and use the returned stable identifier when available. Do not assume that `Sent`, `Trash`, or `INBOX` has the same name across providers.

### SMTP accepted but message did not arrive

Inspect the provider's sent activity, delivery status, spam/quarantine folders, recipient rejection notice, and the final envelope shown at confirmation. An SMTP acceptance response means the submission service accepted the message; it does not guarantee final delivery.

### Outlook worked but IMAP/SMTP uses another identity

Backend selection is explicit for a reason. Display the active backend and account before every send. Do not treat `auto` as proof that both backends represent the same mailbox, aliases, folders, or sent-item store.

## Network and privacy controls

- Restrict outbound access to required provider hostnames and ports when policy allows.
- Keep the MCP server on local stdio unless a separately authenticated remote transport is required.
- Use message-size, attachment-size, timeout, retry, and pagination limits.
- Avoid retrying a send after an ambiguous timeout until the provider's sent activity is checked. A retry can create a duplicate message.
- Record a correlation ID and provider response category, not raw message content.

## GitHub publication steps

Use a clean working tree and substitute your own repository URL:

```powershell
py -m pip install -e ".[test]"
python -m pytest
```

Before `git add`, run a secret scanner and inspect `git status`. Do not place a real `origin` URL containing a token in a script or documentation. Configure branch protection, Dependabot or equivalent dependency alerts, secret scanning, and required reviews in GitHub after the first push.
