# Migrating from 0.1.0 to 0.2.0

1. Stop the old MCP process and remove any references to old bundled wheel/build
   directories. Use Python 3.11+ (Windows/Python 3.14 is the tested baseline).
2. Install the new version in a dedicated virtual environment and point the MCP
   client at that interpreter. Generated artifacts/bytecode are no longer tracked.
3. Discover Outlook StoreIDs in the local terminal and configure an explicit
   `OUTLOOK_EMAIL_OUTLOOK_STORES` allowlist. Empty means deny all Outlook mail access.
4. Leave writes disabled for initial read tests. Enable drafts/sending separately
   only when needed. Outlook writes require an explicit sending account whose
   delivery store is allowed.
5. Every send now requires a local desktop review in addition to `confirm=true`.
   Headless/unattended sending is intentionally unsupported and fails closed.
6. Existing HTTP/SSE deployments must provide a random bearer token and send it
   on every request. A tunnel alone no longer satisfies authentication. Do not
   disable Host/Origin checks for an incompatible client.
7. Search again to refresh message IDs. POP3 retrieval now accepts its generated
   IDs, and IMAP IDs include UIDVALIDITY to reject recreated-mailbox IDs.
8. Narrow export/source directories, refresh the client tool inventory, and run
   security checks. `prepare_draft` remains a preview; disabled write tools are
   absent from discovery.

No real credentials were found in the reviewed reachable history. The original
author email remains in old commits; this upgrade does not rewrite published
history or remove downloaded copies. Use a GitHub privacy address for new commits.
