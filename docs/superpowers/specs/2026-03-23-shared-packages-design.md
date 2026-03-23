# Shared Packages Design — @codyjo/*

**Date:** 2026-03-23
**Status:** Approved
**Approach:** B simplified — npm workspace monorepo, published to public npm

## Problem

5 Next.js apps (selah, thenewbeautifulme, fuel, certstudy, cordivent) share ~95% identical code in auth, crypto, toast, theme, and WhatsNew. Lambda boilerplate and Terraform modules are also duplicated across all apps plus analogify. Bug fixes must be manually copied to every repo.

## Decision

One new public GitHub repo `CodyJo/shared` containing an npm workspace monorepo. Packages published to public npm under `@codyjo/` scope. Apps install as normal npm dependencies. Terraform modules stay in `codyjo.com/terraform/modules/` (existing proven pattern).

## Packages

### @codyjo/crypto
- **Source:** `journal-crypto.ts` (verbatim, zero config)
- **Contents:** AES-256-GCM encryption, PBKDF2 key derivation, recovery codes
- **Dependencies:** None (Web Crypto API only)
- **Build:** tsup → ESM + CJS + .d.ts

### @codyjo/ui
- **Source:** Toast.tsx, theme-context.tsx, WhatsNewModal.tsx, OnboardingManager.tsx, EmailVerificationBanner.tsx
- **Config pattern:** Factory functions for components needing app-specific strings
  - `createThemeContext({ storageKey })` → `{ ThemeProvider, useTheme }`
  - `createWhatsNewModal({ lastSeenKey, tutorialKey, brandName })` → `{ WhatsNewModal }`
  - `ToastProvider` / `useToast` — no config needed (ships as-is)
- **Peer deps:** react >= 19
- **Build:** tsup → ESM + .d.ts (preserves `'use client'` directive)

### @codyjo/auth
- **Source:** auth-context.tsx (two variants: base + encrypted)
- **Config pattern:** Factory function
  - `createAuthContext({ tokenKey, userKey, encCacheKey?, hasEncryption?, onLogin?, onUserUpdate? })`
  - Base variant (Fuel): no encryption methods
  - Encrypted variant (Selah, TNBM, CertStudy, Cordivent): full E2E encryption lifecycle
- **Deps:** @codyjo/crypto
- **Peer deps:** react >= 19
- **Types:** Exports `BaseUser`, `EncryptionKeys` — apps extend with domain-specific fields

### @codyjo/lambda-utils
- **Source:** Extracted from selah/lambda/api/index.mjs (lines 21-200)
- **Contents (all functions take deps as args, no module globals):**
  - `getSecret(arn)` — Secrets Manager with cold-start caching
  - `checkRateLimit(ddb, table, key, max, window)` — atomic DynamoDB UpdateCommand
  - `corsHeaders(origin)` / `getAllowedOrigin(event, allowed)`
  - `res(status, body, origin)` / `rateLimitResponse(origin, retryAfter)`
  - `createToken(payload, secret)` / `verifyToken(token, secret)` / `getUser(event, ddb, table, secret)`
  - `HttpError` class / `parseJsonBody(event)`
- **Build:** Pure ESM (.mjs), no compilation needed

## Terraform Modules (in codyjo.com repo)

New modules alongside existing `codebuild/`:
- `app-site/` — S3 + CloudFront + OAC + ACM + rewrite function + security headers
- `app-dynamodb/` — Single-table with GSI1 + TTL + PITR
- `app-api-gateway/` — HTTP API v2 + CORS + stage + integrations
- `app-lambda/` — IAM + Lambda + Secrets Manager + log groups (for_each over lambda list)

Consumed via existing pattern: `git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/app-site?ref=infra-modules-v1`

Analogify benefits from `app-site`, `app-dynamodb`, `app-api-gateway`. Python Lambdas stay in analogify repo.

## Config Injection Pattern

Each app keeps a thin adapter file at the existing import path. Example for Selah:

```typescript
// selah/src/lib/auth-context.tsx (10 lines replaces 400+)
import { createAuthContext } from '@codyjo/auth';
export const { AuthProvider, useAuth } = createAuthContext<SelahUser>({
  tokenKey: 'selah_token',
  userKey: 'selah_user',
  encCacheKey: 'selah_enc_cache',
  hasEncryption: true,
  onLogin: (user) => syncStoredVersion(user.preferredVersion),
});
```

All existing app imports (`@/lib/auth-context`, `@/components/Toast`) remain unchanged.

## Per-App Config Reference

| App | tokenKey | userKey | encCacheKey | themeKey | brandName |
|---|---|---|---|---|---|
| selah | selah_token | selah_user | selah_enc_cache | selah_theme | Selah |
| thenewbeautifulme | tarot_token | tarot_user | tnbm_enc_cache | tnbm_theme | The New Beautiful Me |
| fuel | fuel_token | fuel_user | — | fuel_theme | Fuel |
| certstudy | cert_token | cert_user | cert_enc_cache | cert_theme | CertStudy |
| cordivent | cordivent_token | cordivent_user | cordivent_enc_cache | cordivent_theme | Cordivent |

## Publishing Workflow

1. Edit shared code, push to main
2. `npm version patch && git push --tags`
3. GitHub Action publishes all packages to npm
4. In consuming app: `npm install @codyjo/auth@1.0.1`

GitHub Action (~20 lines): on tag push → `npm publish --workspaces`

No changesets. No complex versioning. Just `npm version` + push.

## CodeBuild

No changes needed — public npm packages require zero auth. `npm ci` just works.

## Migration Order

1. **@codyjo/crypto** — zero config, cleanest extraction, proof of concept
2. **@codyjo/ui** — Toast (no config) + ThemeProvider + WhatsNewModal (factory pattern)
3. **@codyjo/auth** — most complex, depends on crypto
4. **@codyjo/lambda-utils** — Lambda boilerplate extraction
5. **Terraform modules** — new modules in codyjo.com, migrate one app at a time
6. **Auth-service decommission** — tear down unused infra after all apps migrated

Selah is the canary app for each phase. Verify tests + deploy before migrating others.

## Bugs Fixed (pre-migration)

- [x] Cordivent theme key: `bible_theme` → `cordivent_theme`
- [x] Cordivent auth keys: `portis_*` → `cordivent_*`
- [x] Selah auth key inconsistency: `bible_token` → `selah_token`, `bible_user` → `selah_user`
- [x] TNBM rate limiter: read-then-write → atomic UpdateCommand

## Next.js Integration Notes

- Packages ship compiled JS + .d.ts via tsup — no `transpilePackages` needed
- `'use client'` directive preserved in compiled output (tsup banner config)
- Tailwind v4: add `@source "../node_modules/@codyjo/*/dist";` to globals.css
- Selah Bible version preference: injected via `onLogin` callback in auth config
