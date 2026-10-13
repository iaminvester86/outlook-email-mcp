# Classic Outlook and PST setup

This backend uses classic Outlook for Windows as the COM provider. It does not use the new Outlook for Windows web-based client. The new client may display the same mailbox but does not provide the desktop COM object model required for PST automation.

## 1. Install and verify classic Outlook

1. Install classic Outlook from a supported Microsoft 365 or Office installation.
2. Open Outlook from the Windows Start menu and finish activation/sign-in.
3. Confirm that the classic ribbon and folder pane appear. If the product opens the new Outlook app, switch to the classic application or install the classic component according to your organization's Office policy.
4. Allow Outlook to finish initial synchronization before testing the MCP server.
5. Keep Office and Windows updates current.

The server may be unable to attach to Outlook when Outlook is running under a different Windows account, when a first-run dialog is waiting, or when an organization blocks programmatic access.

## 2. Create or select an Outlook profile

1. Open **Control Panel > Mail > Show Profiles**.
2. Select the profile that contains the mailbox or PST you want to use.
3. Record the profile name exactly if the implementation exposes an `OUTLOOK_PROFILE`-style setting.
4. Set the profile to prompt for a profile or use the intended default, according to the deployment model.
5. Launch classic Outlook with that profile and verify the account name before starting the MCP client.

Outlook COM commonly follows the interactive Windows user's profile. A profile name in configuration cannot grant access that the Windows account or Outlook itself does not have.

## 3. Add an existing PST

Use Outlook's UI to add a PST:

1. Select **File > Open & Export > Open Outlook Data File**.
2. Choose the PST from a local, trusted folder.
3. Wait for Outlook to index/display the PST in the folder pane.
4. Expand the PST and confirm the target folders and messages.
5. Close any repair or password prompt and resolve it in Outlook before testing the MCP server.

Keep PSTs on a local disk or approved storage. Avoid opening a live PST from a file share, removable drive, or synchronized folder unless Microsoft and your organization support that arrangement. Do not copy or repair a PST while Outlook is using it.

If the implementation accepts an `OUTLOOK_PST_PATH`-style setting, use the full path and keep it under an allowed root such as the Outlook Files directory. If the implementation discovers PSTs from the Outlook profile, leave the direct path empty and verify the discovered store by name before reading it.

## 4. Configure the server

Start with:

```text
EMAIL_BACKEND=outlook
OUTLOOK_PROFILE=<the local profile name, if supported>
OUTLOOK_PST_PATH=<full PST path, if supported>
OUTLOOK_ALLOWED_PST_ROOT=C:\Users\YourWindowsUser\Documents\Outlook Files
MCP_CONFIRM_SEND=true
MCP_CONFIRM_DELETE=true
MCP_CONFIRM_BULK_ACTIONS=true
```

The names above are configuration conventions used by this documentation. Check the implementation's advertised configuration before adding a key. Do not place a PST password, Microsoft password, or OAuth token in a checked-in file.

## 5. Test in read-only order

Run these checks in sequence:

1. List Outlook stores/accounts.
2. List folders in the selected PST.
3. Search for a known test message using a narrow date or subject filter.
4. Read metadata, then a small body, without requesting attachments.
5. Create a draft addressed to the test account.
6. Inspect the draft in Outlook.
7. Send only after the MCP client presents the final recipients and confirmation prompt.
8. Test move, attachment export, and deletion against disposable test data.

The server should identify the backend and account in diagnostic output. If the profile cannot attach, do not switch to SMTP automatically and send a message until the active backend is visible.

## Outlook COM troubleshooting

### Outlook cannot be started or attached

- Open classic Outlook manually and clear all first-run, sign-in, update, or password dialogs.
- Check that the MCP client and Outlook run under the same Windows user.
- Close stale Outlook processes only after confirming that Outlook has saved pending changes.
- Verify that the profile is valid in **Control Panel > Mail**.
- Check Office installation/COM registration and organization policy.
- Review Windows Event Viewer and the server's redacted diagnostic log.

### The PST is missing

- Confirm that Outlook shows the PST in the folder pane.
- Check the configured path spelling and drive availability.
- Check the allowlist and Windows read permissions.
- Do not move the PST while Outlook has it open.
- If the PST is password-protected or damaged, resolve that condition in Outlook first.

### Outlook security prompts appear

Treat a security prompt as an intentional trust boundary. Review the account, operation, and organization policy. Do not bypass the prompt by lowering Outlook or antivirus security settings. A deployment that needs unattended operation should use a documented provider/API backend or a managed policy approved by the administrator.

### Outlook is slow or returns stale data

Allow synchronization/indexing to finish. Use narrow searches and pagination. Avoid scanning an entire PST or returning complete message bodies in one request. If the mailbox is shared, verify that the folder and store belong to the intended account.

## Operating notes

- A PST is a local data file, not a multi-user database.
- Outlook may hold a file lock while the store is mounted.
- Outlook folder names, message identifiers, flags, and sent-item behavior can differ from IMAP.
- A Windows desktop session, sleep state, and Outlook process lifetime can affect COM reliability.
- Keep the first production deployment interactive until the organization has tested its endpoint, profile, and policy controls.
