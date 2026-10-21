# Security validation — 0.2.0

Date: 2026-10-21. Review baseline: public commit `be75cab`. The 0.2.0 update
preserves public Git history and replaces the maintained source and documentation.

## Results

| Check | Result |
| --- | --- |
| Windows / Python 3.14 offline regression suite | 96 passed |
| Gitleaks 8.30.1, current files | No secrets found |
| Gitleaks 8.30.1, reachable Git history | No secrets found |
| Bandit 1.9.4, application source | No findings |
| pip-audit 2.10.1, 36 pinned runtime packages | No known vulnerabilities found |
| pip-audit 2.10.1, 75 pinned development packages | No known vulnerabilities found |
| Ruff lint and formatting | Passed |
| pip dependency consistency | Passed |
| Built wheel over real MCP stdio | Initialization, discovery, status, and draft preview passed with synthetic settings |
| Wheel, source archive, and portable plugin | Built from maintained source; checksums generated |

The test suite uses mocked mail/COM backends and in-process HTTP clients. It
covers certificate verification, rejected unauthenticated HTTP/SSE requests,
duplicate headers, DNS rebinding and untrusted Origins, read-only defaults,
local-approval rejection/unavailability, changed sender/attachment data, Outlook
store/folder/message restrictions, safe exports, SMTP recipients/TLS, IMAP
UIDVALIDITY/body limits, POP3 IDs and size preflights, and plugin configuration.

Windows asyncio requires loopback sockets; the tests were run with those enabled.
Dependency auditing used the computer's trusted public CA roots with certificate
verification enabled. No TLS-verification bypass was used. One non-failing
Starlette warning concerns its test-client HTTP adapter; it does not affect the
production transport or test results.

## Changes addressing the review

1. POP3 now supplies `ssl.create_default_context()` explicitly.
2. Sending is disabled by default, omitted from tool discovery until enabled, and
   requires a fresh independent desktop decision for the complete immutable plan.
3. HTTP/SSE requires bearer authentication on every route, while preserving
   loopback-only binding and SDK Host/Origin protections.
4. Outlook enumeration, folders, message parents, and sending accounts are checked
   against explicit store IDs; empty lists deny mailbox access.
5. Outlook exports use private random scratch directories and exclusive final
   creation; a pre-existing predictable temporary filename is no longer touched.
6. Outbound bytes are captured before approval, addresses/headers are validated,
   sizes are bounded, and password/token diagnostic fields are hidden.
7. SMTP recipient arguments/timeouts, POP3 identifier parsing, IMAP body bounds,
   stale mailbox IDs, read-only network configuration, and saved draft Bcc were fixed.
8. Generated code copies, old tracked packages, bytecode, and egg metadata were
   removed from Git. Ignore rules, repeatable packaging, dependency snapshots,
   pinned CI actions, scheduled auditing, and Dependabot configuration were added.

## Scope and remaining limitations

- No real mailbox was accessed, message sent, or live Outlook profile modified
  during validation. Provider compatibility, real COM behavior, and the approval
  window's appearance/interaction still require a controlled local acceptance test.
- The Windows test result is local. Linux compatibility is configured in CI and
  must be confirmed by that runner; do not infer a Linux pass from this report.
- No finding from a scanner is not a certification that all vulnerabilities are
  absent. Results describe the reviewed code and dependency versions on this date.
- Email returned through MCP reaches the client and potentially its AI provider.
  This server is not an isolation boundary against arbitrary code/UI access under
  its own OS account or an actively malicious mail provider.
- Old commits retain the original author's Gmail address. The review found no
  apparent associated password, real API token, or private key. New commits use
  a GitHub privacy address. Removing old metadata needs a coordinated history
  rewrite and cannot remove copies already downloaded by other people.
- GitHub branch protections, private vulnerability reporting, and account-level
  secret-scanning settings require repository-owner configuration. Adding CI files
  does not imply those account settings were enabled or verified.

See [the security model](SECURITY.md) and [migration instructions](MIGRATION-0.2.md)
before enabling writes or HTTP access.
