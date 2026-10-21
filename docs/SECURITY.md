# Security model

## Trust boundaries

The Windows user, configured desktop, Python environment, approved attachment
directories, and mail provider are trusted. Email content, attachment names, MCP
arguments, HTTP clients, and AI-generated instructions are untrusted. Do not run
as administrator. A process with arbitrary shell/UI control under the same OS
account can change files, access credentials, or interact with the desktop;
this server is not a sandbox against that level of compromise.

Mailbox content returned through MCP goes to the client and potentially its AI
service. Local Outlook/PST storage does not guarantee that read mail stays local.

## Enforced controls

- Read-only operation by default; draft/send tools require independent opt-ins.
- Sending requires a caller confirmation plus a fresh local approval showing the
  complete payload. Cancel, timeout, unavailable GUI, or changed sender fails closed.
  There is no MCP approval tool or noninteractive bypass. Only one send approval
  can be outstanding per server process.
- Every Outlook folder and retrieved message is checked against explicit StoreIDs.
  An empty allowlist permits no mailbox access. Outbound Outlook accounts must be
  explicitly selected, and their delivery stores must also be allowlisted.
- IMAP, POP3, and SMTP validate certificates and hostnames. Plaintext modes are
  rejected. Read-only network use does not require SMTP credentials.
- HTTP/SSE is loopback-only with mandatory bearer authentication on every route.
  Duplicate authorization headers are rejected. DNS-rebinding Host and browser
  Origin validation remain enabled. External HTTPS/tunnel authorization is additional.
- Attachment source and destination roots are independent and disabled by default.
  Existing exports are never overwritten; Outlook scratch paths are random/private.
  Outbound bytes are captured once before approval, with aggregate size limits.
- Queries reject controls and quote IMAP values. IMAP IDs bind UIDVALIDITY, folder,
  and UID; POP3 IDs bind mailbox position and a content digest. Stale IDs are rejected.
- Password/token fields are hidden from diagnostic representations. Network errors
  use generic text; raw protocol logging is not enabled by this application.

## Operational precautions

Use dedicated mailboxes/profiles, narrowly allowlisted stores, and dedicated file
directories. Protect those directories from other users, keep Outlook/Office and
Python dependencies patched, and audit updates. Do not automatically click local
send approvals. Do not run this COM integration as a background Windows service.

The application does not expose deletion/move tools, execute downloaded attachments,
or disable Outlook security prompts. Attachment exports are not malware-scanned by
this server; normal endpoint protection remains responsible for scanning them.

Size preflights and partial IMAP retrieval bound ordinary oversized messages.
An actively malicious mail provider can violate protocol responses; provider-level
resource exhaustion is outside this client's isolation guarantees. SMTP acceptance
is not delivery confirmation. Ambiguous send errors require checking provider
activity or Outlook Sent Items before retrying.

## Git and release hygiene

`.gitignore` excludes secrets, local environments, generated packages, bytecode,
mail stores, and exported mail. Gitleaks checks current files and Git history;
Bandit checks application source; pip-audit checks the pinned runtime snapshot.
CI has read-only permissions and pinned action commits. Dependency snapshots need
periodic regeneration and fresh auditing; a past clean scan is not permanent proof.

The 0.2.0 review found no apparent real credential/private-key leak. Historical
commits still contain the original author's email address. New work uses GitHub's
privacy address. Changing an old author address requires a coordinated history
rewrite and cannot remove copies already downloaded by others.

Report vulnerabilities using the private process in [the repository security
policy](../SECURITY.md). Do not put credentials or actual mailbox content in reports.
