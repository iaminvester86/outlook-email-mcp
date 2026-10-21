# Changelog

## 0.2.0 — 2026-10-21

Security changes:

- Verify POP3 server certificates and hostnames with an explicit default TLS context.
- Disable saved drafts/sending by default and omit disabled tools from discovery.
- Require a fresh local desktop approval for each send; show the complete message,
  selected identity, recipients, and frozen attachment hashes. Fail closed on UI
  failure, rejection, timeout, overlapping sends, or sender changes.
- Enforce Outlook store allowlists on enumeration, folders, and actual message
  parents. Require explicit sending accounts and account-specific draft folders.
- Authenticate every HTTP/SSE route with a bearer token while retaining loopback,
  Host, and Origin restrictions.
- Use private random Outlook export scratch directories and exclusive final writes.
- Capture outbound attachment bytes before review; enforce aggregate limits.
- Validate outbound addresses/headers and hide credential fields from diagnostics.
- Add ignore rules, pinned CI actions, secret/static/dependency checks, regression
  tests, reproducible plugin packaging, and audited Windows dependency snapshots.

Bug fixes:

- Correct the SMTP recipient keyword to `to_addrs`, retain Bcc only in the envelope,
  and apply timeouts to both SMTP backends.
- Accept generated POP3 message IDs and reject stale content/incorrect folders.
- Permit read-only IMAP/POP3 operation without SMTP credentials.
- Apply IMAP body limits, check message sizes before retrieval, and include
  UIDVALIDITY in IMAP IDs to detect mailbox recreation.
- Remove committed build copies, stale release archives, egg metadata, and bytecode;
  build 0.2.0 artifacts from the maintained source instead.

Public Git history is preserved. Its historical author email is not a password
leak and cannot be removed from already downloaded copies by this source update.
