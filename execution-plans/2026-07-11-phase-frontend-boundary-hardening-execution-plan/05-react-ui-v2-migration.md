# React UI-V2 Migration

## Security Gate Before Public Trial

No React implementation or legacy freeze starts before BH-RP1 has exited through the exact chain BH-HANDOFF -> BH-SF0A -> BH-SF0B -> BH-SF0C -> BH-SF1 -> BH-SF2 -> BH-SF3 -> BH-SF4 -> BH-PILOT -> BH-RP1. After that entry Gate, `/ui-v2` may run on localhost or approved internal test scope while security migration is incomplete. Public trial is blocked until:

- HTTPS public smoke passes without HTTP fallback.
- React session no longer persists raw bearer token in JavaScript-readable Cookie, localStorage, sessionStorage, URL, or build configuration.
- CSRF, XSS, Cookie flags, logout and rotation tests pass.
- CSP and static asset/index cache behavior pass.

## Session And Token Migration

React uses a server-side session exchange:

1. User supplies token over HTTPS to a pre-session exchange endpoint using JSON body or Authorization header; token in query string is forbidden.
2. Server validates token and creates opaque, short-lived, account-bound session.
3. Browser receives session Cookie with `HttpOnly=true`, `Secure=true`, `SameSite=Strict`, `Path=/`, and no broad Domain attribute.
4. Raw token is not persisted in React memory beyond exchange and never stored client-side.
5. State-changing requests require anti-CSRF token/header and Origin/Referer validation.
6. Logout revokes session and clears Cookie.
7. Token rotation invalidates affected sessions according to documented policy.

Session persistence requirements:

- Store only a hash of the opaque session ID server-side.
- Session IDs use at least 256 bits from the OS CSPRNG with fixed canonical encoding. Lookup uses a keyed hash with protected server pepper (or an ADR-approved equivalent) and constant-time secret comparison; raw IDs never enter logs or persistence.
- Bind account, token version, created/expiry/revoked timestamps and CSRF secret/version.
- Rotate session ID after successful exchange to prevent fixation.
- Default idle timeout and absolute timeout are configuration with tested upper bounds; no 30-day raw bearer session.
- Session exchange body, token and Cookie are excluded from request logs, diagnostics and analytics.
- Exchange endpoint has account/IP-safe rate limiting and stable unauthorized behavior.
- CSRF token is delivered through an authenticated same-origin mechanism and must match the server-side session; it is never a substitute for auth.
- Default idle timeout is 8 hours and absolute timeout is 24 hours; configuration may reduce but not exceed the accepted security maximum without ADR.
- Default maximum active sessions is 5 per account. Session creation, oldest-session eviction and audit row commit use one serializable transaction or equivalent account-scoped lock; concurrent exchanges cannot exceed the limit.
- Use a `__Host-` prefixed Cookie name in public deployment; compatibility Cookie names are cleared and cannot authenticate.
- Every authenticated request atomically validates session hash, account, token/session version, expiry and revocation before authorization. Logout, token rotation and session-ID rotation increment or revoke the authoritative version in the same transaction.
- Concurrent requests holding an older version fail with the stable unauthorized contract; they cannot recreate or extend a revoked session.
- Cleanup runs hourly in batches of at most 1,000 rows, is idempotent, records audit counts, and cannot delete active/non-expired rows. Expired/revoked rows become unusable immediately and are physically removed within 24 hours; backlog older than 6 hours or three consecutive cleanup failures alerts operations.

Bootstrap exchange rules:

- Initial exchange has no existing session Cookie requirement and therefore does not use session CSRF token.
- It requires HTTPS, allowed Origin, JSON/Authorization content type, rate limit and uniform authentication failure.
- After exchange, all Cookie-authenticated state changes require synchronizer CSRF token in a custom header plus trusted Origin validation.
- CSRF token endpoint is same-origin, authenticated, no-store and never returns the raw session ID.

Legacy `HttpOnly=false` raw-token Cookie is allowed only for localhost/internal compatibility behind an explicit expiring flag. Before any public `/ui-v2` trial, `/ui` and `/ui-v2` must both use the server-side session path and the raw-token Cookie must be disabled for the public deployment.

Legacy Cookie cleanup uses the exact old name/path/domain and writes an expired Cookie during session exchange, logout and public cutover. Tests prove a browser carrying the old Cookie cannot authenticate `/ui-v2` and that public smoke removes it.

## Trusted Proxy And Origin

- Forwarded scheme/host/client IP are accepted only from configured Caddy/proxy addresses.
- Arbitrary client `X-Forwarded-For`, `X-Forwarded-Proto` or `Forwarded` headers are ignored/replaced.
- Canonical public origin comes from validated `PUBLIC_BASE_URL`; localhost/internal origins use explicit allowlist.
- Rate limiting uses trusted proxy-derived client identity plus account/session dimensions, not raw user-supplied headers.
- HTTP request for public session exchange is rejected; no redirect carries token body/header.
- Tests cover forged forwarded headers, wrong origin, IP literal, proxy bypass and HTTP downgrade.

## Route Ownership

```text
/                 -> legacy during trial
/ui               -> legacy during trial
/ui-v2             -> React index
/ui-v2/            -> React index
/ui-v2/assets/**   -> immutable hashed assets
/ui-v2/{**path}    -> SPA fallback after API/static exclusions
```

- `/api/**`, downloads, artifacts, previews and non-SPA routes are excluded from fallback.
- Current legacy `/ui-v2` handler is removed/replaced in one route-owner change with contract tests.
- `/ui` retirement/default cutover is a separate decision.

## Authentication And Cache Boundary

- React index is a public shell only if it contains no user/account/project/secret/internal version data.
- Index response: `Cache-Control: no-store` during trial; CSP/security headers always applied.
- Hashed assets: `Cache-Control: public,max-age=31536000,immutable`.
- Static middleware ordering must not bypass CSP, content-type, path, or security headers.
- All data/admin APIs remain server-authorized; hiding a React route is never authorization.
- Admin page bundles may expose UI structure but no privileged data or credentials.

### Minimum Browser Security Policy

Public `/ui-v2` responses use a tested minimum policy:

```text
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
```

- Inline script/style, `unsafe-eval`, arbitrary CDN and wildcard sources are prohibited unless a security ADR provides nonce/hash controls, owner and expiry.
- API and session endpoints are same-origin by default. CORS is disabled unless a named route has an explicit exact-origin allowlist; wildcard origin, reflected origin and credentialed wildcard are prohibited.
- Preflight, wrong-origin, null-origin, forged-host, WebSocket and download responses have negative tests. Security headers also apply to SPA fallback and error responses.

## Toolchain And Supply Chain

- React + TypeScript + Vite.
- npm only; commit `package-lock.json`; CI uses `npm ci`.
- React ADR pins exact Node 24 LTS patch and npm version in `.node-version`, `engines`, `packageManager`, and CI.
- No floating versions in CI.
- Initial rollout has no service worker.
- Production source maps are not publicly served; optional internal artifact is access-controlled.
- Dependency audit, license allowlist, lockfile integrity and registry allowlist run in CI.
- Generate CycloneDX or SPDX SBOM.
- Build provenance records Node/npm/Vite/React versions, lockfile hash, source commit and build identity.
- React asset manifest and bundle receive checksums/signature in deployment manifest.
- `npm ci` runs in an isolated least-privilege build identity without production/deployment/signing secrets. Network is restricted to the approved registry during dependency restore and disabled during application build.
- npm lifecycle scripts are disabled by default (`ignore-scripts`) or admitted through an exact package/version/script-hash allowlist with security review. Native addon/build exceptions are isolated and audited.
- The deployment manifest is signed by the protected release identity outside repository-controlled build steps. Deployment and rollback verify signer key ID, signature, bundle checksums, source commit and compatibility fields before selecting a bundle.
- Every lockfile package add/change requires protected dependency admission recording package/version, registry integrity, lifecycle-script decision, license and advisory result. A locked dependency is not trusted merely because `npm ci` is reproducible.
- Release verification public keys and deployment-selector binary/workflow hashes are pinned in protected runtime configuration outside the bundle and reviewed repository. Release-key rotation, revocation and break-glass require the independently administered two-approver ceremony; a bundle cannot supply its own trusted key or verifier.

### Upgrade Policy

- Security-critical dependency advisory: triage within one business day; patch or accepted mitigation with owner/expiry.
- npm/React/Vite patch/minor review at least monthly.
- Node active-LTS review quarterly and before EOL minus 90 days.
- Major upgrades require compatibility task and, when architectural, ADR.
- Automated dependency PRs cannot bypass E2E, CSP, license, SBOM or bundle budget gates.

## Typed Contract Source

- HTTP DTO/client generated to `src/generated/api` from the handoff-bound `DownstreamApiObservationSnapshot`. The snapshot may express observed handlers/DTOs as OpenAPI, but remains a downstream technical projection and cannot add or reinterpret business routes.
- Action/status/evidence vocabulary generated from the exact handoff-bound upstream machine fixtures to `src/generated/workflow`; React cannot add business values locally.
- Generated files contain source version/hash and are not hand-edited.
- CI regenerate-and-zero-diff check is mandatory.
- Incompatible change requires API version and compatibility plan before React consumption.

## Migration Ledger

Machine ledger fields:

- upstreamHandoffId/hash/epoch, StateEvent hash, ActiveRegistry rowVersion, derived surfaceId, upstream source refs/owner/authority document, legacy route/renderer, React route/component
- downstream API observation/frontend inventory version/hash, upstream fixture/E2E refs and compatibility classification
- state: not_started/shell_ready/parity_ready/trial/default/legacy_retired
- trial cohort, cutover evidence, rollback bundle

The required surface set is generated from `DownstreamFrontendSurfaceInventory`, which deterministically inventories the frozen upstream browser routes/renderers/E2E/compatibility evidence referenced by the manifest. Every row retains its upstream source path/hash and a stable derived surface ID; the inventory cannot invent a new purpose or omit an observed surface without an upstream compatibility classification. This book owns only React renderer/client/session/cache/build/migration state; upstream remains owner of surface purpose, business action/status, eligibility, readback, diagnostic and acceptance semantics. An unmapped or extra local surface blocks generation. Trial is per derived surface/cohort; `/ui-v2` is not complete until every mandatory observed surface reaches its required migration state.

### Trial Promotion And Rollback Gate

Each surface records a minimum 7-day observation window and at least 100 representative sessions before promotion. The representative matrix is derived from DownstreamFrontendSurfaceInventory rows and their upstream E2E/source refs and must cover normal/admin roles as applicable, success/failure/unauthorized/stale/readback paths, long-running operation recovery, current supported browsers and desktop/mobile classifications declared by product support. Low traffic may extend the trial but cannot waive the session floor or substitute an unquantified decision log. Promotion requires:

- server error rate <= 0.5% and no regression greater than 0.2 percentage points versus legacy
- unexpected authentication/session failure <= 0.2%
- zero confirmed cross-account, CSRF, XSS, token leakage, cache leakage or authorization finding
- API/fixture parity pass rate 100% for mandatory cases
- P95 API latency <= 2 seconds, P95 initial page LCP <= 2.5 seconds on the accepted desktop fixture, and neither metric worse than legacy by more than 20%
- no unresolved P0/P1 and no P2 without owner/expiry

Any confirmed shared auth/session/authorization/CSRF/XSS/cross-account or backend security boundary failure immediately stops cohort expansion and enters fail-closed maintenance; it must not fall back to legacy because legacy shares the affected boundary. Only a proven React-client/bundle-specific incompatibility may select the verified previous React bundle or legacy surface. Sustained error budget breach for 15 minutes also stops expansion. A rollback-smoke failure enters maintenance rather than selecting an unverified fallback. Promotion/rollback/maintenance decisions are machine-recorded in the migration ledger with owner and evidence refs.

## Legacy Deletion

- BrowserUiRenderer feature freeze begins only after BH-HANDOFF and the affected upstream surface enters BH-REACT migration; it never blocks the ongoing upstream plan.
- Per-surface parity may stop legacy feature work but cannot delete shared shell code while `/` or `/ui` references it.
- Shared `RenderShellV2` removal requires `/ui` cutover/retirement, reference scan, route tests and rollback approval.
- Removal also requires the handoff compatibility entry to be `eligible_for_removal`; `must_preserve` and unexpired `time_bounded_compatibility` behavior cannot be deleted or silently reimplemented.

## Version Compatibility And Rollback

- Backend supports current and immediately previous React deployment bundle for at least 14 days, except emergency security revocation.
- Versioned deployment bundle contains platform binary, React assets, SBOM, provenance and manifest.
- External runtime build root retains current and previous verified bundles.
- Rollback selects previous bundle without rebuilding.
- Rollback selection first verifies platform binary and DB schema compatibility from release manifest; incompatible previous bundle is blocked rather than starting against a newer schema.
- Rollback smoke covers session, project list, long-running readback, error/requestId and CSRF mutation.

## Acceptance

- Public `/ui-v2` blocked until HTTPS/session/CSRF Gate passes.
- Cookie is HttpOnly/Secure/SameSite; raw token absent from browser storage.
- Session fixation, expiry, revocation, exchange rate limit, token-redaction, XSS, CSRF, logout, rotation and cross-account tests pass.
- Concurrent logout/rotation/request races, session-version checks, cleanup and active-session-limit tests pass.
- Bootstrap exchange, trusted proxy, legacy Cookie deletion and HTTP downgrade tests pass.
- Index/assets/fallback/API exclusion and cache policies pass.
- Exact CSP/CORS/HSTS/nosniff policy and error/fallback response header tests pass.
- Generated contracts have zero drift.
- SBOM/provenance/checksum correspond to deployed bundle.
- Lifecycle-script allowlist/build isolation and release-manifest signer/runtime verification pass.
- Migration ledger, per-surface E2E and previous-bundle rollback pass.
- Trial promotion/rollback thresholds and observation evidence pass before cohort expansion.
