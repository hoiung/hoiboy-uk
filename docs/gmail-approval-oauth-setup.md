---
title: AGIT email-approval Gmail OAuth - least-privilege access model + setup
purpose: The access model and setup for the AGIT feature email-approval automation (issue #48 Phase 4). Least-privilege Gmail OAuth (send + read-own-thread), not a broad app-password. Credentials are granted at implementation time and never committed.
last_verified: 2026-07-12
related:
  - content/legal/agit-story-guidelines.md (the member-facing promise this enforces)
  - scripts/agit_approval.py (the automation)
  - scripts/check-agit-publish-gate.py (the hard gate that requires approval on file)
---

## What this is

AGIT edits every member feature before publishing, so HOIBOY AI LTD is the
publisher, not a neutral host. The member's protection (and ours) is that
**nothing goes live until the member has approved the exact final wording**. This
automation sends the member the exact wording and records their approval reply,
so `check-agit-publish-gate.py` can hard-fail publish until that approval is on
file. No approval, no publish.

The mailbox is `hoiboyuk@gmail.com`. Access to it is granted at this point (Phase
4 implementation), not before, and is scoped as tightly as the Gmail API allows.

## The access model (least-privilege)

The goal is the narrowest access that still lets the automation send one email and
read the one reply, and nothing more.

- **Dedicated OAuth client, not a password.** A broad IMAP/SMTP app-password
  hands over the whole mailbox to anything holding it. Instead we use a dedicated
  Google Cloud OAuth client (Desktop app type) for `hoiboyuk@gmail.com`, so access
  is a revocable, scoped grant, not a standing password.
- **Two scopes only:**
  - `https://www.googleapis.com/auth/gmail.send` (send only, cannot read),
  - `https://www.googleapis.com/auth/gmail.readonly` (read only, cannot delete or
    modify).
  These are the two scopes in `scripts/agit_approval.py` (`GMAIL_SCOPES`). We do
  NOT request `gmail.modify`, `gmail.labels`, or full-account scopes.
- **Application-level thread restriction.** Be honest about the scope boundary:
  `gmail.readonly` is a mailbox-wide read scope at the OAuth level (Gmail has no
  per-thread scope). The automation restricts itself in code: `poll_for_approval`
  reads exactly one thread, the approval thread it created (tracked by
  `threadId`), and only treats a message as the member's reply when the `From`
  header matches the submitter. It never lists or browses the mailbox.
- **Token lives outside the repo.** The OAuth client secret and the cached token
  are stored outside the public repo (default `~/.agit-secrets/`). Nothing about
  the credentials is ever committed. `.agit-secrets/` is gitignored as a
  belt-and-braces guard in case a repo-relative path is ever used.
- **Revocable.** The grant can be revoked at any time from the Google Account
  permissions page, or by deleting the OAuth client in the Cloud Console. Deleting
  the cached token forces a fresh consent on the next run.

## Setup steps (operator, one time)

These are the operator-runtime steps. The credential grant happens here.

1. **Create the OAuth client.** In the Google Cloud Console for the project tied
   to `hoiboyuk@gmail.com`: enable the Gmail API, then create an OAuth client ID
   of type **Desktop app**. Download the client secret JSON.
2. **Place the secret outside the repo:**

   ```bash
   mkdir -p ~/.agit-secrets
   mv ~/Downloads/client_secret_*.json ~/.agit-secrets/gmail_client_secret.json
   chmod 600 ~/.agit-secrets/gmail_client_secret.json
   ```

3. **Install the runtime libraries** (deliberately NOT in `requirements-dev.txt`,
   because CI and the unit tests use a fake service and never touch the network):

   ```bash
   pip install google-api-python-client google-auth-oauthlib
   ```

4. **First run does the consent.** The first `send` opens a browser for the
   one-time OAuth consent and caches the token to
   `~/.agit-secrets/gmail_token.json`. After that it is non-interactive.

## Running it

Send the exact final wording to the submitter (this creates the approval thread):

```bash
python3 scripts/agit_approval.py send \
  --record <record-dir>/<slug> \
  --to <member-email> \
  --title "<Feature title>" \
  --wording-file <edited.txt> \
  --slug <slug>
```

Later, check for the member's reply and record the decision:

```bash
python3 scripts/agit_approval.py poll \
  --record <record-dir>/<slug> \
  --thread-id <thread-id-from-approval_request.json> \
  --member-email <member-email>
```

`poll` writes `approval.json` into the record (`approved: true|false`). The
publish gate then reads it: `python3 scripts/check-agit-publish-gate.py --record
<record-dir>/<slug>` exits 0 only once approval is on file (and every named person
is cleared). Approval detection is strict and fail-safe: a reply approves only if
it carries an affirmative phrase and no negation phrase (phrases live in
`scripts/agit-feature-edit-check.config.yaml` under `approval:`), so anything
ambiguous is treated as NOT approved.

## Secrets handling

- The client secret and token are stored under `~/.agit-secrets/` (outside the
  public repo). They are never committed.
- `.agit-secrets/` and `.agit-records/` are both gitignored.
- `scripts/check-public-repo-secrets.py` runs pre-commit and in CI; keep it green.
- If a credential is ever exposed, revoke the OAuth client in the Cloud Console
  and delete the cached token; a new consent mints fresh credentials.
