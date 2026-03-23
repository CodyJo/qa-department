# Shared Packages Foundation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `CodyJo/shared` npm workspace monorepo with `@codyjo/crypto` and `@codyjo/ui` packages, publish to npm, and migrate Selah as the canary app.

**Architecture:** npm workspaces monorepo in a new GitHub repo. Packages built with tsup, published to public npm. Apps install as normal npm dependencies. Factory pattern for config injection — apps keep thin adapter files at existing import paths.

**Tech Stack:** TypeScript, tsup, vitest, React 19 (peer dep for ui), npm workspaces

**Spec:** `docs/superpowers/specs/2026-03-23-shared-packages-design.md`

---

## Chunk 1: Repository Scaffold + @codyjo/crypto

### Task 1: Create shared repo and workspace root

**Files:**
- Create: `/home/merm/projects/shared/package.json`
- Create: `/home/merm/projects/shared/.gitignore`
- Create: `/home/merm/projects/shared/.npmrc`

- [ ] **Step 1: Create directory and initialize**

```bash
mkdir -p /home/merm/projects/shared
cd /home/merm/projects/shared
git init
```

- [ ] **Step 2: Create workspace root package.json**

```json
{
  "name": "@codyjo/shared",
  "private": true,
  "workspaces": ["packages/*"],
  "scripts": {
    "build": "npm run build --workspaces --if-present",
    "test": "npm run test --workspaces --if-present",
    "typecheck": "npm run typecheck --workspaces --if-present"
  }
}
```

- [ ] **Step 3: Create .gitignore**

```
node_modules/
dist/
*.tgz
.DS_Store
```

- [ ] **Step 4: Create .npmrc**

```
workspaces-update=false
```

- [ ] **Step 5: Commit**

```bash
git add package.json .gitignore .npmrc
git commit -m "chore: initialize shared workspace monorepo"
```

---

### Task 2: Create @codyjo/crypto package

**Files:**
- Create: `/home/merm/projects/shared/packages/crypto/package.json`
- Create: `/home/merm/projects/shared/packages/crypto/tsconfig.json`
- Create: `/home/merm/projects/shared/packages/crypto/tsup.config.ts`
- Create: `/home/merm/projects/shared/packages/crypto/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@codyjo/crypto",
  "version": "1.0.0",
  "description": "Zero-knowledge E2E encryption — AES-256-GCM, PBKDF2, recovery codes",
  "type": "module",
  "main": "./dist/index.cjs",
  "module": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.js",
      "require": "./dist/index.cjs",
      "types": "./dist/index.d.ts"
    }
  },
  "files": ["dist"],
  "scripts": {
    "build": "tsup",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "tsup": "^8",
    "typescript": "^5",
    "vitest": "^4"
  },
  "license": "MIT"
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022", "DOM"],
    "strict": true,
    "declaration": true,
    "outDir": "dist",
    "rootDir": "src",
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create tsup.config.ts**

```typescript
import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['esm', 'cjs'],
  dts: true,
  clean: true,
  splitting: false,
});
```

- [ ] **Step 4: Copy journal-crypto.ts verbatim as src/index.ts**

Copy the exact contents of `/home/merm/projects/selah/src/lib/journal-crypto.ts` to `/home/merm/projects/shared/packages/crypto/src/index.ts`. This file has zero dependencies and zero app-specific config — it is ready to ship as-is.

- [ ] **Step 5: Install deps and build**

```bash
cd /home/merm/projects/shared
npm install
cd packages/crypto
npm run build
```

Expected: `dist/` contains `index.js`, `index.cjs`, `index.d.ts`

- [ ] **Step 6: Commit**

```bash
cd /home/merm/projects/shared
git add packages/crypto
git commit -m "feat: add @codyjo/crypto package — E2E encryption library"
```

---

### Task 3: Write crypto tests

**Files:**
- Create: `/home/merm/projects/shared/packages/crypto/src/__tests__/crypto.test.ts`

- [ ] **Step 1: Write tests**

```typescript
import { describe, it, expect } from 'vitest';
import {
  toBase64, fromBase64,
  deriveWrappingKey, generateMasterKey, wrapMasterKey, unwrapMasterKey,
  encryptField, decryptField,
  encryptSensitiveFields, decryptSensitiveFields,
  generateRecoveryCodes, deriveRecoveryWrappingKey, hashRecoveryCode,
  generateSalt,
} from '../index';

describe('base64 helpers', () => {
  it('round-trips ArrayBuffer through base64', () => {
    const original = new Uint8Array([1, 2, 3, 4, 5]);
    const b64 = toBase64(original.buffer);
    const restored = new Uint8Array(fromBase64(b64));
    expect(restored).toEqual(original);
  });
});

describe('key derivation', () => {
  it('derives a wrapping key from password and salt', async () => {
    const salt = generateSalt();
    const key = await deriveWrappingKey('test-password', salt);
    expect(key.type).toBe('secret');
    expect(key.algorithm).toMatchObject({ name: 'AES-GCM', length: 256 });
    expect(key.usages).toContain('wrapKey');
    expect(key.usages).toContain('unwrapKey');
  });
});

describe('master key lifecycle', () => {
  it('generates, wraps, and unwraps a master key', async () => {
    const mk = await generateMasterKey();
    const salt = generateSalt();
    const wrappingKey = await deriveWrappingKey('password', salt);

    const { ciphertext, iv } = await wrapMasterKey(mk, wrappingKey);
    expect(ciphertext).toBeTruthy();
    expect(iv).toBeTruthy();

    const unwrapped = await unwrapMasterKey(ciphertext, iv, wrappingKey);
    expect(unwrapped.type).toBe('secret');
    expect(unwrapped.usages).toContain('encrypt');
    expect(unwrapped.usages).toContain('decrypt');
  });

  it('fails to unwrap with wrong password', async () => {
    const mk = await generateMasterKey();
    const salt = generateSalt();
    const rightKey = await deriveWrappingKey('right', salt);
    const wrongKey = await deriveWrappingKey('wrong', salt);

    const { ciphertext, iv } = await wrapMasterKey(mk, rightKey);
    await expect(unwrapMasterKey(ciphertext, iv, wrongKey)).rejects.toThrow();
  });
});

describe('field encryption', () => {
  it('encrypts and decrypts a string field', async () => {
    const mk = await generateMasterKey();
    const payload = await encryptField('hello world', mk);
    expect(payload.v).toBe(1);
    expect(payload.ct).toBeTruthy();

    const decrypted = await decryptField(payload, mk);
    expect(decrypted).toBe('hello world');
  });

  it('encrypts and decrypts sensitive fields object', async () => {
    const mk = await generateMasterKey();
    const fields = { content: 'secret', mood: 'happy' };
    const payload = await encryptSensitiveFields(fields, mk);

    const decrypted = await decryptSensitiveFields(payload, mk);
    expect(decrypted).toEqual(fields);
  });
});

describe('recovery codes', () => {
  it('generates 8 codes in XXXXX-XXXXX format', () => {
    const codes = generateRecoveryCodes();
    expect(codes).toHaveLength(8);
    codes.forEach(code => {
      expect(code).toMatch(/^[0-9A-F]{5}-[0-9A-F]{5}$/);
    });
  });

  it('derives recovery wrapping key and hashes code', async () => {
    const salt = generateSalt();
    const codes = generateRecoveryCodes();
    const key = await deriveRecoveryWrappingKey(codes[0], salt);
    expect(key.type).toBe('secret');

    const hash = await hashRecoveryCode(codes[0]);
    expect(hash).toBeTruthy();
    expect(typeof hash).toBe('string');
  });

  it('recovery key can wrap and unwrap master key', async () => {
    const mk = await generateMasterKey();
    const salt = generateSalt();
    const codes = generateRecoveryCodes();
    const recoveryKey = await deriveRecoveryWrappingKey(codes[0], salt);

    const { ciphertext, iv } = await wrapMasterKey(mk, recoveryKey);
    const unwrapped = await unwrapMasterKey(ciphertext, iv, recoveryKey);

    // Verify the unwrapped key works for encryption
    const encrypted = await encryptField('test', unwrapped);
    const decrypted = await decryptField(encrypted, mk);
    expect(decrypted).toBe('test');
  });
});
```

- [ ] **Step 2: Run tests**

```bash
cd /home/merm/projects/shared/packages/crypto
npm run test
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd /home/merm/projects/shared
git add packages/crypto/src/__tests__
git commit -m "test: add @codyjo/crypto unit tests"
```

---

## Chunk 2: @codyjo/ui Package

### Task 4: Create @codyjo/ui package scaffold

**Files:**
- Create: `/home/merm/projects/shared/packages/ui/package.json`
- Create: `/home/merm/projects/shared/packages/ui/tsconfig.json`
- Create: `/home/merm/projects/shared/packages/ui/tsup.config.ts`
- Create: `/home/merm/projects/shared/packages/ui/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@codyjo/ui",
  "version": "1.0.0",
  "description": "Shared React UI components — Toast, Theme, WhatsNew",
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.js",
      "types": "./dist/index.d.ts"
    }
  },
  "files": ["dist"],
  "scripts": {
    "build": "tsup",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "peerDependencies": {
    "react": ">=19.0.0",
    "lucide-react": ">=0.400.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16",
    "@types/react": "^19",
    "jsdom": "^28",
    "react": "^19",
    "react-dom": "^19",
    "lucide-react": "^0.577.0",
    "tsup": "^8",
    "typescript": "^5",
    "vitest": "^4"
  },
  "license": "MIT"
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022", "DOM"],
    "jsx": "react-jsx",
    "strict": true,
    "declaration": true,
    "outDir": "dist",
    "rootDir": "src",
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create tsup.config.ts**

```typescript
import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['esm'],
  dts: true,
  clean: true,
  splitting: false,
  banner: { js: "'use client';" },
  external: ['react', 'react-dom', 'lucide-react'],
});
```

- [ ] **Step 4: Commit scaffold**

```bash
cd /home/merm/projects/shared
npm install
git add packages/ui
git commit -m "chore: scaffold @codyjo/ui package"
```

---

### Task 5: Add Toast component (no config needed)

**Files:**
- Create: `/home/merm/projects/shared/packages/ui/src/toast.tsx`

- [ ] **Step 1: Copy Toast.tsx verbatim**

Copy the exact contents of `/home/merm/projects/selah/src/components/Toast.tsx` to `/home/merm/projects/shared/packages/ui/src/toast.tsx`. Remove the first line (`'use client';`) since the tsup banner handles this. No other changes needed — Toast has zero app-specific config.

- [ ] **Step 2: Export from index.ts**

```typescript
// /home/merm/projects/shared/packages/ui/src/index.ts
export { ToastProvider, useToast } from './toast';
```

- [ ] **Step 3: Build and verify**

```bash
cd /home/merm/projects/shared/packages/ui
npm run build
```

Expected: `dist/index.js` contains ToastProvider and useToast exports

- [ ] **Step 4: Commit**

```bash
cd /home/merm/projects/shared
git add packages/ui/src
git commit -m "feat: add Toast component to @codyjo/ui"
```

---

### Task 6: Add ThemeProvider with factory pattern

**Files:**
- Create: `/home/merm/projects/shared/packages/ui/src/theme.tsx`
- Modify: `/home/merm/projects/shared/packages/ui/src/index.ts`

- [ ] **Step 1: Create theme.tsx with factory function**

```typescript
import { createContext, useContext, useSyncExternalStore, type ReactNode } from 'react';

export type Theme = 'dark' | 'light';

export interface ThemeConfig {
  storageKey: string;
  defaultTheme?: Theme;
}

export interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggle: () => void;
}

export function createThemeContext(config: ThemeConfig) {
  const { storageKey, defaultTheme = 'dark' } = config;

  const ThemeContext = createContext<ThemeContextType>({
    theme: defaultTheme,
    setTheme: () => {},
    toggle: () => {},
  });

  let themeListeners: Array<() => void> = [];
  let cachedTheme: Theme = typeof window !== 'undefined'
    ? (localStorage.getItem(storageKey) as Theme) || defaultTheme
    : defaultTheme;

  function subscribeTheme(callback: () => void) {
    themeListeners.push(callback);
    return () => {
      themeListeners = themeListeners.filter(l => l !== callback);
    };
  }
  function getThemeSnapshot(): Theme { return cachedTheme; }
  function getServerSnapshot(): Theme { return defaultTheme; }
  function notifyTheme() { themeListeners.forEach(l => l()); }

  function applyTheme(theme: Theme) {
    if (typeof document === 'undefined') return;
    document.documentElement.classList.toggle('light', theme === 'light');
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }

  function ThemeProvider({ children }: { children: ReactNode }) {
    const theme = useSyncExternalStore(subscribeTheme, getThemeSnapshot, getServerSnapshot);

    if (typeof window !== 'undefined') {
      applyTheme(theme);
    }

    const setTheme = (t: Theme) => {
      cachedTheme = t;
      localStorage.setItem(storageKey, t);
      applyTheme(t);
      notifyTheme();
    };

    const toggle = () => {
      setTheme(theme === 'dark' ? 'light' : 'dark');
    };

    return (
      <ThemeContext.Provider value={{ theme, setTheme, toggle }}>
        {children}
      </ThemeContext.Provider>
    );
  }

  function useTheme() {
    return useContext(ThemeContext);
  }

  return { ThemeProvider, useTheme };
}
```

- [ ] **Step 2: Add export to index.ts**

```typescript
export { ToastProvider, useToast } from './toast';
export { createThemeContext, type Theme, type ThemeConfig, type ThemeContextType } from './theme';
```

- [ ] **Step 3: Build**

```bash
cd /home/merm/projects/shared/packages/ui
npm run build
```

- [ ] **Step 4: Commit**

```bash
cd /home/merm/projects/shared
git add packages/ui/src
git commit -m "feat: add ThemeProvider factory to @codyjo/ui"
```

---

### Task 7: Add WhatsNewModal with factory pattern

**Files:**
- Create: `/home/merm/projects/shared/packages/ui/src/whats-new.tsx`
- Modify: `/home/merm/projects/shared/packages/ui/src/index.ts`

- [ ] **Step 1: Create whats-new.tsx**

The WhatsNewModal from Selah with hardcoded strings (`LAST_SEEN_KEY`, `TUTORIAL_KEY`, brand name, `APP_VERSION`, `APP_UPDATES`) replaced by config. The `APP_UPDATES` and `APP_VERSION` imports are removed — they become config props.

```typescript
import { useState, useEffect, useCallback, useRef } from 'react';
import { X, Sparkles, Shield, Zap } from 'lucide-react';

export interface AppUpdate {
  id: string;
  version: string;
  date: string;
  title: string;
  description: string;
  tag: 'new' | 'improved' | 'security';
}

export interface WhatsNewConfig {
  lastSeenKey: string;
  tutorialKey: string;
  brandName: string;
  appVersion: string;
  updates: AppUpdate[];
}

function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] ?? 0;
    const nb = pb[i] ?? 0;
    if (na !== nb) return na - nb;
  }
  return 0;
}

function getTagIcon(tag: AppUpdate['tag']) {
  switch (tag) {
    case 'new': return <Sparkles size={14} className="text-accent" />;
    case 'security': return <Shield size={14} className="text-green-400" />;
    case 'improved': return <Zap size={14} className="text-gold" />;
  }
}

function getTagLabel(tag: AppUpdate['tag']) {
  switch (tag) {
    case 'new': return 'New';
    case 'security': return 'Security';
    case 'improved': return 'Improved';
  }
}

function getTagClasses(tag: AppUpdate['tag']) {
  switch (tag) {
    case 'new': return 'bg-accent/10 text-accent';
    case 'security': return 'bg-green-500/10 text-green-400';
    case 'improved': return 'bg-gold/10 text-gold';
  }
}

export function createWhatsNewModal(config: WhatsNewConfig) {
  const { lastSeenKey, tutorialKey, brandName, appVersion, updates: appUpdates } = config;

  function computeInitialState(): { visible: boolean; updates: AppUpdate[] } {
    if (typeof window === 'undefined') return { visible: false, updates: [] };

    const tutorialCompleted = localStorage.getItem(tutorialKey);
    if (!tutorialCompleted) {
      localStorage.setItem(lastSeenKey, appVersion);
      return { visible: false, updates: [] };
    }

    const lastSeen = localStorage.getItem(lastSeenKey);
    if (!lastSeen) {
      return appUpdates.length > 0
        ? { visible: true, updates: appUpdates }
        : { visible: false, updates: [] };
    }

    if (compareVersions(lastSeen, appVersion) < 0) {
      const newUpdates = appUpdates.filter(u => compareVersions(u.version, lastSeen) > 0);
      return newUpdates.length > 0
        ? { visible: true, updates: newUpdates }
        : { visible: false, updates: [] };
    }

    return { visible: false, updates: [] };
  }

  function WhatsNewModal() {
    const [{ visible, updates }, setState] = useState(computeInitialState);
    const overlayRef = useRef<HTMLDivElement>(null);
    const previouslyFocusedRef = useRef<HTMLElement | null>(null);

    useEffect(() => {
      if (visible) {
        previouslyFocusedRef.current = document.activeElement as HTMLElement;
        requestAnimationFrame(() => {
          const focusable = overlayRef.current?.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );
          if (focusable && focusable.length > 0) {
            focusable[0].focus();
          }
        });
      } else if (previouslyFocusedRef.current) {
        previouslyFocusedRef.current.focus();
      }
    }, [visible]);

    const dismiss = useCallback(() => {
      localStorage.setItem(lastSeenKey, appVersion);
      setState({ visible: false, updates: [] });
    }, []);

    const handleKeyDown = useCallback((e: KeyboardEvent) => {
      if (!visible || !overlayRef.current) return;
      if (e.key === 'Escape') { dismiss(); return; }
      if (e.key === 'Tab') {
        const focusable = overlayRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (!focusable || focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) { e.preventDefault(); last.focus(); }
        } else {
          if (document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
      }
    }, [visible, dismiss]);

    useEffect(() => {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }, [handleKeyDown]);

    if (!visible || updates.length === 0) return null;

    return (
      <div
        ref={overlayRef}
        className="fixed inset-0 z-[210] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
        role="dialog"
        aria-modal="true"
        aria-label={`What's new in ${brandName}`}
      >
        <div className="relative w-full max-w-md max-h-[85vh] overflow-y-auto rounded-2xl border border-card-border bg-[#0f1729] p-6 shadow-2xl">
          <button
            onClick={dismiss}
            className="absolute right-4 top-4 rounded-lg p-1 text-muted transition-colors hover:bg-surface-hover hover:text-foreground"
            aria-label="Close what's new"
          >
            <X size={18} />
          </button>
          <div className="mb-5 text-center">
            <h2 className="text-xl font-bold text-gold">What&apos;s New in {brandName}</h2>
            <p className="mt-1 text-xs text-muted">Version {appVersion}</p>
          </div>
          <div className="space-y-3">
            {updates.map((update) => (
              <div key={update.id} className="rounded-xl border border-card-border bg-background p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${getTagClasses(update.tag)}`}>
                    {getTagIcon(update.tag)}
                    {getTagLabel(update.tag)}
                  </span>
                  <span className="text-xs text-muted">{update.date}</span>
                </div>
                <h3 className="text-sm font-semibold text-foreground">{update.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted">{update.description}</p>
              </div>
            ))}
          </div>
          <button
            onClick={dismiss}
            className="mt-5 w-full rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent/80"
          >
            Got it
          </button>
        </div>
      </div>
    );
  }

  return { WhatsNewModal };
}
```

- [ ] **Step 2: Update index.ts exports**

```typescript
export { ToastProvider, useToast } from './toast';
export { createThemeContext, type Theme, type ThemeConfig, type ThemeContextType } from './theme';
export { createWhatsNewModal, type WhatsNewConfig, type AppUpdate } from './whats-new';
```

- [ ] **Step 3: Build**

```bash
cd /home/merm/projects/shared/packages/ui
npm run build
```

- [ ] **Step 4: Commit**

```bash
cd /home/merm/projects/shared
git add packages/ui/src
git commit -m "feat: add WhatsNewModal factory to @codyjo/ui"
```

---

## Chunk 3: Publish + GitHub Action + Selah Migration

### Task 8: Add GitHub Actions publish workflow

**Files:**
- Create: `/home/merm/projects/shared/.github/workflows/publish.yml`

- [ ] **Step 1: Create publish workflow**

```yaml
name: Publish
on:
  push:
    tags: ['v*']
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          registry-url: https://registry.npmjs.org
      - run: npm ci
      - run: npm run build
      - run: npm run test
      - run: npm publish --workspaces --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

- [ ] **Step 2: Create CI workflow**

Create: `/home/merm/projects/shared/.github/workflows/ci.yml`

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npm run build
      - run: npm run test
```

- [ ] **Step 3: Commit**

```bash
cd /home/merm/projects/shared
git add .github
git commit -m "ci: add publish and CI workflows"
```

---

### Task 9: Create GitHub repo and push

- [ ] **Step 1: Create public GitHub repo**

```bash
cd /home/merm/projects/shared
gh repo create CodyJo/shared --public --source=. --push
```

- [ ] **Step 2: Verify repo exists**

```bash
gh repo view CodyJo/shared --json name,url
```

---

### Task 10: Register npm org and publish initial versions

- [ ] **Step 1: Create @codyjo npm org (if not exists)**

```bash
npm org create codyjo 2>/dev/null || true
```

- [ ] **Step 2: Publish @codyjo/crypto**

```bash
cd /home/merm/projects/shared/packages/crypto
npm publish --access public
```

- [ ] **Step 3: Publish @codyjo/ui**

```bash
cd /home/merm/projects/shared/packages/ui
npm publish --access public
```

- [ ] **Step 4: Verify packages are on npm**

```bash
npm view @codyjo/crypto version
npm view @codyjo/ui version
```

Expected: Both return `1.0.0`

---

### Task 11: Migrate Selah — crypto

**Files:**
- Modify: `/home/merm/projects/selah/package.json` — add `@codyjo/crypto` dependency
- Modify: `/home/merm/projects/selah/src/lib/journal-crypto.ts` — replace with re-export

- [ ] **Step 1: Install @codyjo/crypto in Selah**

```bash
cd /home/merm/projects/selah
npm install @codyjo/crypto@1.0.0
```

- [ ] **Step 2: Replace journal-crypto.ts with re-export**

Replace the entire contents of `/home/merm/projects/selah/src/lib/journal-crypto.ts` with:

```typescript
export {
  toBase64,
  fromBase64,
  deriveWrappingKey,
  generateMasterKey,
  wrapMasterKey,
  unwrapMasterKey,
  encryptField,
  decryptField,
  encryptSensitiveFields,
  decryptSensitiveFields,
  generateRecoveryCodes,
  deriveRecoveryWrappingKey,
  hashRecoveryCode,
  generateSalt,
  type EncryptedPayload,
} from '@codyjo/crypto';
```

- [ ] **Step 3: Typecheck**

```bash
cd /home/merm/projects/selah
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 4: Run tests**

```bash
cd /home/merm/projects/selah
npm test
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
cd /home/merm/projects/selah
git add package.json package-lock.json src/lib/journal-crypto.ts
git commit -m "refactor: use @codyjo/crypto shared package"
```

---

### Task 12: Migrate Selah — Toast

**Files:**
- Modify: `/home/merm/projects/selah/package.json` — add `@codyjo/ui` dependency
- Modify: `/home/merm/projects/selah/src/components/Toast.tsx` — replace with re-export

- [ ] **Step 1: Install @codyjo/ui in Selah**

```bash
cd /home/merm/projects/selah
npm install @codyjo/ui@1.0.0
```

- [ ] **Step 2: Add Tailwind source for shared packages**

Add to `/home/merm/projects/selah/src/app/globals.css` (near the top, after the existing `@import` lines):

```css
@source "../node_modules/@codyjo/ui/dist";
```

- [ ] **Step 3: Replace Toast.tsx with re-export**

Replace the entire contents of `/home/merm/projects/selah/src/components/Toast.tsx` with:

```typescript
'use client';
export { ToastProvider, useToast } from '@codyjo/ui';
```

- [ ] **Step 4: Typecheck + test**

```bash
cd /home/merm/projects/selah
npx tsc --noEmit && npm test
```

Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd /home/merm/projects/selah
git add package.json package-lock.json src/components/Toast.tsx src/app/globals.css
git commit -m "refactor: use @codyjo/ui Toast from shared package"
```

---

### Task 13: Migrate Selah — ThemeProvider

**Files:**
- Modify: `/home/merm/projects/selah/src/lib/theme-context.tsx` — replace with adapter

- [ ] **Step 1: Replace theme-context.tsx with adapter**

Replace the entire contents of `/home/merm/projects/selah/src/lib/theme-context.tsx` with:

```typescript
'use client';
import { createThemeContext } from '@codyjo/ui';
export type { Theme } from '@codyjo/ui';

export const { ThemeProvider, useTheme } = createThemeContext({
  storageKey: 'selah_theme',
});
```

Note: `selah_theme` replaces the previous `bible_theme` (bug was already fixed earlier in this session).

- [ ] **Step 2: Check if `Theme` type is imported from `@/types` elsewhere**

Search for `import type { Theme }` across Selah `src/`. If any file imports `Theme` from `@/types`, verify the type definition still exists there or update the import to `@/lib/theme-context`.

```bash
cd /home/merm/projects/selah
grep -r "import.*Theme.*from.*@/types" src/
```

- [ ] **Step 3: Typecheck + test**

```bash
cd /home/merm/projects/selah
npx tsc --noEmit && npm test
```

- [ ] **Step 4: Commit**

```bash
cd /home/merm/projects/selah
git add src/lib/theme-context.tsx
git commit -m "refactor: use @codyjo/ui ThemeProvider from shared package"
```

---

### Task 14: Migrate Selah — WhatsNewModal

**Files:**
- Modify: `/home/merm/projects/selah/src/components/WhatsNewModal.tsx` — replace with adapter

- [ ] **Step 1: Replace WhatsNewModal.tsx with adapter**

Replace the entire contents of `/home/merm/projects/selah/src/components/WhatsNewModal.tsx` with:

```typescript
'use client';
import { createWhatsNewModal } from '@codyjo/ui';
import { APP_UPDATES, APP_VERSION } from '@/data/updates';

export const { WhatsNewModal } = createWhatsNewModal({
  lastSeenKey: 'selah_last_seen_version',
  tutorialKey: 'selah_tutorial_completed',
  brandName: 'Selah',
  appVersion: APP_VERSION,
  updates: APP_UPDATES,
});
```

- [ ] **Step 2: Verify AppUpdate type compatibility**

Check that `@/data/updates` exports match the `AppUpdate` interface from `@codyjo/ui`. The fields should be: `id`, `version`, `date`, `title`, `description`, `tag`.

```bash
cd /home/merm/projects/selah
head -20 src/data/updates.ts
```

If the app's `AppUpdate` type differs, either update the app's data file or cast.

- [ ] **Step 3: Typecheck + test**

```bash
cd /home/merm/projects/selah
npx tsc --noEmit && npm test
```

- [ ] **Step 4: Commit**

```bash
cd /home/merm/projects/selah
git add src/components/WhatsNewModal.tsx
git commit -m "refactor: use @codyjo/ui WhatsNewModal from shared package"
```

---

### Task 15: Build Selah and verify

- [ ] **Step 1: Full build**

```bash
cd /home/merm/projects/selah
npm run build
```

Expected: Successful static export to `out/`

- [ ] **Step 2: Run full test suite**

```bash
cd /home/merm/projects/selah
npm test
```

Expected: All tests pass including Plausible regression tests

- [ ] **Step 3: Final commit if any fixes needed**

If any adjustments were needed during build/test, commit them.
