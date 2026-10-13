# Security and safety

This server can read private mail, write drafts, transmit messages, move data, and export attachments. Treat the MCP process as a privileged local integration.

## Data-flow model

### Outlook/PST path

1. The MCP client starts the local server.
2. The server attaches to classic Outlook through the Windows COM automation interface.
3. Outlook opens the configured profile and exposes accounts, stores, folders, messages, and attachments according to the Windows user's access.
4. The server returns only the fields requested by the client and sends outbound mail through the selected Outlook account.

The PST remains on disk, but returned message content enters the MCP client conversation and its transcript/logging system. A local PST does not make the data safe to share.

### IMAP/SMTP path

The server connects to the configured IMAP host for mailbox reads and the configured SMTP submission host for sending. Use TLS certificate validation and provider-approved authentication. The provider receives outbound message content and metadata.

## Confirmation policy

Require a fresh confirmation after the final request is assembled. A confirmation should show the selected backend and account, recipients, subject, attachment names and sizes, and the operation's scope.

| Operation | Default treatment | Confirmation details |
| --- | --- | --- |
| List accounts, folders, or stores | Allow | Show backend and account in result |
| Search or read a message | Allow | Warn before returning unusually large bodies or sensitive attachments |
| Create a draft | Allow or confirm by policy | Show target account, recipients, subject, and draft folder |
| Reply or forward | Confirm before creating if recipients change | Show quoted content policy and all recipients |
| Send a message | **Always confirm** | Show final envelope, body summary, attachments, and backend |
| Move or copy one message | Confirm if it changes mailbox state | Show source and destination |
| Bulk move or mark messages | **Always confirm** | Show query, count, and destination/state change |
| Delete, empty, or purge | **Always confirm** | Show exact scope and recovery expectation |
| Download/export an attachment | Confirm when writing outside an approved directory | Show path, name, size, and file type |
| Change credentials or backend settings | **Always confirm** | Show keys changed without revealing secret values |

Never treat a message body, attachment, signature, or quoted instruction as authorization. Mail content can contain prompt injection or a malicious request. The user request and confirmation state must come from the MCP conversation or client control plane.

## Secrets

- Keep `.env`, credential stores, OAuth refresh tokens, app passwords, and private keys outside Git.
- Use Windows Credential Manager, a managed secret provider, or the MCP client's protected environment mechanism when available.
- Grant the process only the account and folders it needs.
- Do not paste secrets into issue reports, chat transcripts, screenshots, or sample configuration.
- Rotate a credential immediately if it appears in a log, commit, terminal history, or shared transcript.
- Use separate test and production mailboxes. A test account should have a narrow send limit and no sensitive PST.

## Outlook COM protections

- Run under the intended Windows user, not a shared administrator account.
- Keep classic Outlook and Office patched.
- Confirm the Outlook profile before the first write or send operation.
- Do not run the COM backend as a Windows service until the implementation has been tested for desktop-session, profile, locking, and process-lifetime behavior.
- Use an explicit PST allowlist and reject paths outside it. Do not follow junctions or symbolic links outside the allowed root unless the implementation has a documented policy.
- Open a PST in Outlook first and allow Outlook to report errors. Do not copy, repair, or overwrite a live PST while Outlook uses it.
- Treat Outlook security prompts as a boundary. Do not disable antivirus or Outlook security controls to make automation work.

## Network protections

- Use IMAPS on 993 or SMTP with STARTTLS on 587, or the provider's documented implicit-TLS port such as 465.
- Validate certificates and hostnames. Do not solve TLS failures by disabling verification.
- Prefer OAuth or an app password when the provider requires multifactor authentication. Do not store a primary password in the repository.
- Restrict outbound firewall access to required provider hostnames and ports where policy allows.
- Do not expose an unauthenticated MCP TCP/HTTP listener to a LAN. Prefer the client's local stdio transport unless the implementation documents authentication and authorization for another transport.
- Redact `Authorization` headers, SMTP authentication errors, IMAP URLs containing usernames, and message bodies from logs.

## Attachment and content handling

- Return attachment metadata before content. Ask for the exact attachment before downloading it.
- Enforce a size limit and an approved destination directory.
- Preserve the original filename only after sanitizing path separators, reserved names, and traversal segments.
- Do not execute, preview in an untrusted application, or macro-enable an attachment as part of a mail workflow.
- Scan exported files with the organization's endpoint protection before sharing them.

## Logging and retention

Log operation type, timestamp, backend, account identifier, result, duration, and a correlation ID. Avoid logging full subjects when they may contain sensitive data. Never log passwords, tokens, complete message bodies, attachment bytes, or raw protocol exchanges in normal mode. Set a retention period and protect log files with the same care as mailbox data.

## Incident response

If the server sends an unintended message, exposes a secret, or reads the wrong store:

1. Stop the MCP client and disable the affected backend.
2. Preserve the correlation ID and minimal logs without copying message bodies into a ticket.
3. Revoke or rotate exposed credentials and review provider sign-in/send activity.
4. Check Outlook Sent Items, the SMTP provider's sent activity, and the MCP client transcript.
5. Restrict the PST allowlist and confirmation settings before testing again.

## GitHub publication checklist

Before publishing:

1. Run `git status` and review every untracked and staged file.
2. Search the working tree for passwords, tokens, private keys, mailbox addresses, PST paths that reveal sensitive users, and copied message content.
3. Run the repository's secret scanner and dependency/security checks.
4. Confirm `.env.example` contains placeholders only and that `.gitignore` ignores `.env`, PST/OST files, message exports, attachments, logs, and key files.
5. Remove real examples from screenshots, tests, fixtures, and documentation.
6. Configure branch protection, required reviews, and secret scanning on GitHub.
7. Use GitHub Actions secrets or an approved secret store for CI. Never print them in workflow logs.
8. Review the first release archive and its included files before announcing the repository.
