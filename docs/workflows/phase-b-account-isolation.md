# Phase B Account Isolation Slice

## Scope

Phase B B1 starts by turning the Phase A console from a single-admin prototype into an account-scoped prototype console.

Implemented scope:

- Admin token still comes from the host secret environment.
- Admin can create user accounts manually from the console.
- Admin can disable or enable user accounts without deleting their projects.
- Admin can rotate a user access token; the new plaintext token is returned once.
- Admin account actions are recorded in `admin_account_audit_events` without plaintext token material.
- User tokens are generated once, stored only as hashes, and returned only at creation time.
- Project listing, project creation, deletion, chat history, package access, asset access, run readback, and artifact readback are scoped to the authenticated account.
- Admin-only panels and admin APIs require the resolved admin role.
- Each signed-in account can read and save its own LLM gateway binding through `/api/account/llm-binding`.
- Each signed-in account can view its own LLM usage summary through `/api/account/llm-usage`.
- Admin can view cross-account LLM usage summary through `/api/admin/llm-usage` without exposing plaintext tokens.
- Admin can export the cross-account LLM usage summary as CSV through `/api/admin/llm-usage.csv`.
- Admin can inspect recent cross-account LLM run audit summaries through `/api/admin/llm-runs`.

## Runtime Behavior

Authentication accepts a bearer token. The server resolves the token in this order:

1. Host-configured admin token hash.
2. Database-backed account token hash.
3. Legacy configured user token hash fallback for compatibility.

The browser stores the token under `phaseAAccessToken`. The old `phaseAAdminToken` key is read only as a compatibility fallback and removed on new login/logout.

## Admin User Flow

1. Sign in with the admin access token.
2. Open `Account Admin`.
3. Enter `Username` and `Project limit`.
4. Click `Create user token`.
5. Copy the returned token immediately. It is not recoverable later.
6. Use `Refresh users` to confirm account, quota, disabled state, and project count.
7. Use `Disable user`, `Enable user`, or `Rotate token` for account recovery.

## Security Boundary

Current hard boundary:

- Users cannot list or mutate other accounts' projects through project-scoped API routes.
- Users cannot read another account's run or artifact by guessing run/artifact ids.
- Public package and asset preview ticket URLs remain ticket-gated and resolve the owning account before reading files.
- User tokens are not stored in plaintext.

Still deferred:

- User deletion.
- Full LLM audit export with filters and pagination.
- Account audit CSV export and filters.
- Full integration tests around HTTP auth middleware.

## Account LLM Binding

Current B2 minimum slice:

- `GET /api/account/llm-binding` reads the current account binding.
- `POST /api/account/llm-binding` saves the current account binding.
- `GET /api/account/llm-usage` returns the current UTC day call count, estimated CNY cost, and recent LLM runs scoped to the current account.
- The browser UI only asks for gateway base URL, external account reference, and token reference.
- Plain provider API keys are rejected by the server-side binding service.
- The legacy `/api/admin/llm-binding` path is retained for admin compatibility, but user-facing binding should use the account route.

## Admin LLM Usage Summary

Current admin audit slice:

- `GET /api/admin/llm-usage` requires admin role.
- `GET /api/admin/llm-usage.csv` requires admin role and exports only account-level summary fields.
- The response is grouped by account and includes username, admin/disabled flags, project count, current UTC day call count, and estimated CNY cost.
- The response intentionally does not include plaintext tokens, token hashes, provider keys, or token secret values.
- `GET /api/admin/llm-runs` returns recent run-level audit summaries without stdout, stderr, evidence blobs, artifacts, file paths, or token material.

## Smoke Check

Use the Phase B account smoke script after restarting the platform:

```powershell
py -3 scripts/python/phase_b_account_smoke.py --base-url http://127.0.0.1:18080
```

Optional authorized checks can be enabled by passing `--admin-token <access-token>` or setting `PHASEA_ADMIN_TOKEN` in the process environment. Authorized checks create a temporary user account and verify user/admin route boundaries.

## Account Action Audit

Current account audit slice:

- Admin user creation records `user_created`.
- Admin disable/enable records `user_disabled` or `user_enabled`.
- Admin token rotation records `user_token_rotated`.
- `GET /api/admin/account-audit` requires admin role and returns recent audit events.
- Audit metadata must not include plaintext tokens, token hashes, provider keys, or secret values.
