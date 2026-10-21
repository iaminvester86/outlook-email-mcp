# IMAP, POP3, and SMTP

Choose an explicit `OUTLOOK_EMAIL_BACKEND=imap` or `pop3` and use the provider's
published hostname/port. IMAP reads folders/messages and can append drafts; POP3
reads only the inbox. SMTP submits mail. Neither network backend reads local PSTs.

| Protocol | Default port | Security |
| --- | --- | --- |
| IMAP | 993 | Verified TLS from connection start |
| POP3 | 995 | Verified TLS from connection start |
| SMTP | 587 | STARTTLS required before authentication |
| SMTP with `SMTP_SSL=true` | Set `SMTP_PORT=465` where supported | Verified implicit TLS |

Set `IMAP_HOST`/`IMAP_USERNAME` or `POP3_HOST`/`POP3_USERNAME`, then provide
credentials as described in [CREDENTIALS.md](CREDENTIALS.md). Read-only access
does not require any SMTP settings. For sending, set `SMTP_HOST`, `SMTP_USERNAME`,
the SMTP credential, and optionally a provider-authorized `SMTP_FROM` address.
Enabling sending does not remove the mandatory local interactive approval.

The server never falls back to plaintext after TLS failure. Certificate/hostname
validation cannot be disabled through configuration. Fix DNS, certificates,
trusted roots, system time, or provider settings rather than bypassing validation.
OAuth is not implemented. Providers that disable password/app-password login
cannot be used through these network backends.

POP3 cannot save drafts or preserve read/unread flags. Its generated identifiers
include a content digest and are checked again before returning message/attachment
content. IMAP IDs include UIDVALIDITY; mailbox recreation invalidates old IDs.
Search again after a stale-ID error or after upgrading from 0.1.0.

`OUTLOOK_EMAIL_MAX_BODY_CHARS` applies to every backend. Message-size preflights
reject ordinary oversized messages before retrieval; IMAP body requests are also
partial and use BODY.PEEK to avoid marking mail read. POP3 may retain provider
side effects associated with retrieval; it does not implement deletion.

For connectivity, use `Test-NetConnection` with the actual approved hostname and
port. A successful TCP check does not prove authentication or TLS success. These
standard-library mail connections are direct and do not inherit browser proxies.

Timeouts use `OUTLOOK_EMAIL_NETWORK_TIMEOUT` (default 30 seconds). If a send has an
ambiguous failure, inspect provider activity before retrying. The server does not
automatically retry sending. SMTP success means submission was accepted, not that
delivery completed or that the provider saved a copy in Sent Items.
