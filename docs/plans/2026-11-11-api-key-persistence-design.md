# Remembering the Studio API key

The operator reports that the key prompt returns after closing a tab at
`https://tasbir.pokharelsabin.com.np`. The existing code uses localStorage,
which should survive tab closure, but hides write failures and treats an
in-memory key as successfully saved. The header dialog also captures its draft
at mount, so saving the first-run prompt can leave the header dialog empty.
The user's browser storage settings remain unknown; the tunnel has no access
to localStorage, and public responses do not clear site data.

Keep the existing versioned localStorage key for compatibility. Add an HTTPS
host-only recovery cookie with a one-year lifetime, Secure, Path=/ and
SameSite=Strict. Backend authentication continues to require x-api-key; it
does not accept cookie authentication. Existing localStorage credentials migrate
automatically on the next visit. Clear removes both copies. If neither store
accepts a key, keep the dialog open and show a useful error. Refresh the header
draft whenever its dialog opens.

Keeping only localStorage with a visible error would expose failed writes but
would not recover a key after localStorage loss. Server-side sessions would
require a separate authentication lifecycle and do not prevent browsers clearing
site data. The recovery cookie retains the existing client-owned credential
model and matches the requested scope. Private browsing and explicit deletion
of all site data still require re-entry; the app must not promise otherwise.

Validate existing-key migration, module/tab reload, failed writes, complete
storage denial, clear behavior, HTTPS cookie attributes, stale dialog state,
and a real tab close/reopen on the deployed HTTPS origin. Release all current
main changes plus this fix as 1.3.0, with a configuration/data snapshot and a
version/digest-pinned VM deployment. The user explicitly authorized this release
and deployment in this session.
