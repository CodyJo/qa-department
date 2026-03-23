# CertStudy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build CertStudy, an AI-powered certification study platform at study.codyjo.com with 4 exam tracks, spaced repetition, adaptive planning, and AI tutoring.

**Architecture:** Static SPA (Next.js 16, React 19, Tailwind v4) deployed to S3+CloudFront. Three Lambda functions (API CRUD, AI Tutor, Planner) behind API Gateway v2. DynamoDB single-table. ~70% infrastructure copied from Selah/TNBM, ~30% purpose-built learning engine.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS v4, AWS (S3, CloudFront, Lambda Node 20, DynamoDB, API Gateway v2, Secrets Manager), Terraform, Vitest, GitHub Actions, Claude Sonnet (Anthropic SDK)

**Spec:** `docs/superpowers/specs/2026-03-22-certstudy-design.md`

**Source app for copying:** `/home/merm/projects/selah` (Selah Bible study app — same architecture)

**Anthropic API key:** Use the TNBM key from `/home/merm/projects/thenewbeautifulme/terraform/terraform.tfvars` — copy into certstudy's terraform.tfvars.

---

## File Structure

### Project Root: `/home/merm/projects/certstudy`

```
certstudy/
├── src/
│   ├── app/                          # Next.js App Router
│   │   ├── layout.tsx                # Root layout (providers, nav)
│   │   ├── globals.css               # Design tokens, theme
│   │   ├── page.tsx                  # Dashboard (home)
│   │   ├── login/page.tsx            # Auth pages (copied)
│   │   ├── reset-password/page.tsx   # (copied)
│   │   ├── tracks/
│   │   │   ├── page.tsx              # Track selection
│   │   │   └── [id]/setup/page.tsx   # Onboarding wizard
│   │   ├── study/[track]/[domain]/page.tsx  # Guided lessons
│   │   ├── flashcards/page.tsx       # SRS review
│   │   ├── quiz/[track]/page.tsx     # Practice quizzes + baseline
│   │   ├── tutor/page.tsx            # AI tutor chat
│   │   ├── progress/[track]/page.tsx # Readiness + domain breakdown
│   │   ├── plan/[track]/page.tsx     # Study plan calendar
│   │   ├── shared/[token]/page.tsx   # Public progress view
│   │   ├── settings/page.tsx         # (copied + adapted)
│   │   ├── updates/page.tsx          # (copied)
│   │   ├── privacy/page.tsx          # (copied)
│   │   └── accessibility/page.tsx    # (copied)
│   ├── components/
│   │   ├── AuthGuard.tsx             # (copied)
│   │   ├── LoginPageClient.tsx       # (copied, rebranded)
│   │   ├── Navigation.tsx            # (copied, new links/colors)
│   │   ├── Toast.tsx                 # (copied)
│   │   ├── Skeleton.tsx              # (copied)
│   │   ├── ErrorBoundary.tsx         # (copied)
│   │   ├── WhatsNewModal.tsx         # (copied)
│   │   ├── TutorialOverlay.tsx       # (copied, new steps)
│   │   ├── OnboardingManager.tsx     # (copied)
│   │   ├── PwaInstallPrompt.tsx      # (copied)
│   │   ├── ServiceWorker.tsx         # (copied)
│   │   ├── EmailVerificationBanner.tsx # (copied)
│   │   ├── KeyboardShortcuts.tsx     # (copied, adapted shortcuts)
│   │   ├── Markdown.tsx              # (copied from TNBM)
│   │   ├── FlashcardCard.tsx         # NEW — card flip + SRS buttons
│   │   ├── QuizQuestion.tsx          # NEW — question display + answer selection
│   │   ├── ReadinessGauge.tsx        # NEW — circular progress gauge
│   │   ├── DomainProgressBar.tsx     # NEW — domain bar with overlap tags
│   │   ├── OverlapMap.tsx            # NEW — knowledge overlap visualization
│   │   ├── TutorChat.tsx             # NEW — chat interface
│   │   ├── StudyPlanCalendar.tsx     # NEW — calendar with day status
│   │   ├── BaselineWizard.tsx        # NEW — 3-mode baseline assessment
│   │   └── TrackCard.tsx             # NEW — track selection card
│   ├── lib/
│   │   ├── auth-context.tsx          # (copied, key renames)
│   │   ├── journal-crypto.ts         # (copied, dormant)
│   │   ├── api.ts                    # NEW — API client for all endpoints
│   │   ├── study-context.tsx         # NEW — study state provider
│   │   ├── srs-engine.ts            # NEW — SM-2 spaced repetition
│   │   ├── readiness.ts             # NEW — readiness calculator
│   │   ├── urgency.ts              # NEW — progressive urgency checker
│   │   ├── knowledge-transfer.ts    # NEW — cross-track transfer logic
│   │   └── storage.ts              # NEW — localStorage helpers
│   ├── types/
│   │   └── index.ts                 # NEW — all TypeScript types
│   ├── data/
│   │   ├── tracks.ts                # NEW — track definitions
│   │   ├── knowledge-map.ts         # NEW — cross-track concept graph
│   │   ├── aplus-objectives.ts      # NEW — A+ exam domains/objectives
│   │   ├── aplus-diagnostic.ts      # NEW — baseline assessment bank
│   │   ├── aplus-questions.ts       # NEW — practice question bank
│   │   ├── aplus-flashcards.ts      # NEW — flashcard deck
│   │   ├── aplus-lessons.ts         # NEW — guided lesson content
│   │   ├── aws-ccp-objectives.ts    # NEW — AWS CCP domains
│   │   ├── aws-ccp-diagnostic.ts    # NEW
│   │   ├── aws-ccp-questions.ts     # NEW
│   │   ├── aws-ccp-flashcards.ts    # NEW
│   │   ├── aws-ccp-lessons.ts       # NEW
│   │   ├── cka-objectives.ts        # NEW — CKA domains
│   │   ├── cka-diagnostic.ts        # NEW
│   │   ├── cka-questions.ts         # NEW
│   │   ├── cka-flashcards.ts        # NEW
│   │   ├── cka-lessons.ts           # NEW
│   │   ├── puppet8-objectives.ts    # NEW — Puppet 8 domains
│   │   ├── puppet8-diagnostic.ts    # NEW
│   │   ├── puppet8-questions.ts     # NEW
│   │   ├── puppet8-flashcards.ts    # NEW
│   │   ├── puppet8-lessons.ts       # NEW
│   │   └── updates.ts              # NEW — version changelog
│   └── __tests__/
│       ├── setup.ts                 # (copied)
│       ├── srs-engine.test.ts       # NEW
│       ├── readiness.test.ts        # NEW
│       ├── urgency.test.ts          # NEW
│       ├── knowledge-transfer.test.ts # NEW
│       ├── types.test.ts            # NEW
│       ├── api-session.test.ts      # (copied pattern)
│       └── regression/
│           ├── plausible.test.tsx    # (copied pattern)
│           └── seo.test.ts          # (copied pattern)
├── lambda/
│   ├── api/
│   │   ├── index.mjs               # NEW — CRUD Lambda (auth + study data)
│   │   └── package.json             # Minimal (aws-sdk)
│   ├── tutor/
│   │   ├── index.mjs               # NEW — AI Tutor Lambda
│   │   └── package.json             # @anthropic-ai/sdk
│   └── planner/
│       ├── index.mjs               # NEW — Planner Lambda
│       └── package.json             # @anthropic-ai/sdk
├── terraform/
│   ├── main.tf                      # (copied, adapted)
│   ├── variables.tf                 # (copied, adapted)
│   ├── terraform.tfvars             # NEW — certstudy values + TNBM API key
│   ├── s3.tf                        # (copied, new bucket names)
│   ├── dynamodb.tf                  # (copied, new table name)
│   ├── lambda.tf                    # (adapted — 3 lambdas, new routing)
│   ├── api_gateway.tf               # (adapted — path-based routing to 3 lambdas)
│   ├── cloudfront.tf                # (copied, new domain)
│   ├── route53.tf                   # (copied, study.codyjo.com)
│   ├── monitoring.tf                # (copied, new alarm names)
│   ├── cd.tf                        # (copied, new repo name)
│   ├── waf.tf                       # (copied)
│   └── outputs.tf                   # (copied)
├── .github/workflows/
│   ├── ci.yml                       # (copied, adapted)
│   └── cd.yml                       # (copied, adapted)
├── public/
│   ├── manifest.json                # NEW — CertStudy PWA manifest
│   ├── sw.js                        # (copied)
│   ├── robots.txt                   # NEW
│   └── sitemap.xml                  # NEW
├── package.json                     # NEW
├── next.config.ts                   # (copied)
├── vitest.config.ts                 # (copied)
├── tsconfig.json                    # (copied)
├── postcss.config.mjs               # (copied)
├── CLAUDE.md                        # NEW — project instructions
└── .gitignore                       # (copied)
```

---

## Chunk 1: Project Scaffolding & Configuration

### Task 1: Initialize Next.js Project

**Files:**
- Create: `certstudy/package.json`
- Create: `certstudy/next.config.ts`
- Create: `certstudy/tsconfig.json`
- Create: `certstudy/vitest.config.ts`
- Create: `certstudy/postcss.config.mjs`
- Create: `certstudy/.gitignore`

- [ ] **Step 1: Create project directory and initialize git**

```bash
mkdir -p /home/merm/projects/certstudy
cd /home/merm/projects/certstudy
git init
```

- [ ] **Step 2: Create package.json with dependencies**

Copy from `/home/merm/projects/selah/package.json` and adapt:
- Change `name` to `certstudy`
- Keep all dependencies identical (Next.js 16, React 19, Tailwind v4, etc.)
- Add `@anthropic-ai/sdk` to dependencies (already in Selah's lambda but not in root)

```json
{
  "name": "certstudy",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```

Dependencies: copy exact versions from Selah's package.json.

- [ ] **Step 3: Copy config files from Selah**

```bash
cp /home/merm/projects/selah/next.config.ts /home/merm/projects/certstudy/
cp /home/merm/projects/selah/tsconfig.json /home/merm/projects/certstudy/
cp /home/merm/projects/selah/vitest.config.ts /home/merm/projects/certstudy/
cp /home/merm/projects/selah/postcss.config.mjs /home/merm/projects/certstudy/
cp /home/merm/projects/selah/.gitignore /home/merm/projects/certstudy/
cp /home/merm/projects/selah/.eslintrc.json /home/merm/projects/certstudy/ 2>/dev/null || true
```

- [ ] **Step 4: Install dependencies**

```bash
cd /home/merm/projects/certstudy
npm install
```

- [ ] **Step 5: Verify build scaffolding works**

Create minimal `src/app/layout.tsx` and `src/app/page.tsx`:

```tsx
// src/app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
```

```tsx
// src/app/page.tsx
export default function Home() {
  return <h1>CertStudy</h1>;
}
```

Run: `npm run build`
Expected: Successful static export to `out/`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: initialize certstudy project with Next.js 16 scaffolding"
```

### Task 2: Design Tokens & Global CSS

**Files:**
- Create: `src/app/globals.css`

- [ ] **Step 1: Copy globals.css from Selah**

```bash
cp /home/merm/projects/selah/src/app/globals.css /home/merm/projects/certstudy/src/app/globals.css
```

- [ ] **Step 2: Adapt design tokens for CertStudy**

Replace Selah's purple/spiritual palette with CertStudy's tech/teal palette:

| Token | Selah Value | CertStudy Value |
|-------|-------------|-----------------|
| `--background` | `#0c0a1a` | `#0a0f14` |
| `--foreground` | `#e8e0f0` | `#e2e8f0` |
| `--card-bg` | `#1a1530` | `#0d1117` |
| `--card-border` | `#3d2a6e` | `#1e2a3a` |
| `--accent` | `#8B5CF6` | `#00d4aa` |
| `--accent-glow` | `#7c4dff` | `#00e4bb` |
| `--gold` | `#d4a843` | `#f39c12` |
| `--surface` | `#151025` | `#1a2332` |
| `--surface-hover` | `#1e1840` | `#243347` |

Also update the starfield background gradients to use blue-teal instead of purple-gold.

- [ ] **Step 3: Update layout.tsx to import globals.css**

```tsx
import './globals.css';
```

- [ ] **Step 4: Verify — run dev server, check colors render**

```bash
npm run dev
```

Open localhost:3000, verify dark background renders.

- [ ] **Step 5: Commit**

```bash
git add src/app/globals.css src/app/layout.tsx
git commit -m "feat: add CertStudy design tokens and global styles"
```

### Task 3: TypeScript Types

**Files:**
- Create: `src/types/index.ts`
- Test: `src/__tests__/types.test.ts`

- [ ] **Step 1: Write type validation test**

```typescript
// src/__tests__/types.test.ts
import { describe, it, expect } from 'vitest';
import type {
  Track, Domain, Objective, Question, Flashcard, Lesson,
  StudyPlan, PlanDay, DomainProgress, QuizResult, FlashcardState,
  TutorSession, TutorMode, BaselineType, PlanStyle, UrgencyLevel,
  KnowledgeGroup, ReadinessScore
} from '@/types';

describe('Types', () => {
  it('Track type has required fields', () => {
    const track: Track = {
      id: 'aplus',
      name: 'CompTIA A+',
      examCode: '220-1101 & 1102',
      domains: [],
      passingScore: 675,
      totalQuestions: 90,
      examDuration: 90,
      color: '#22c55e',
    };
    expect(track.id).toBe('aplus');
  });

  it('FlashcardState tracks SRS fields', () => {
    const state: FlashcardState = {
      cardId: 'aplus-net-001',
      ease: 2.5,
      interval: 6,
      nextReview: '2026-04-01',
      repetitions: 2,
      source: 'curated',
    };
    expect(state.ease).toBeGreaterThanOrEqual(1.3);
  });

  it('DomainProgress aggregates three signals', () => {
    const progress: DomainProgress = {
      trackId: 'aplus',
      domainId: 'networking',
      quizScore: 72,
      flashcardMastery: 45,
      aiConfidence: 68,
      lessonsCompleted: 3,
      totalLessons: 5,
    };
    expect(progress.quizScore).toBeLessThanOrEqual(100);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npx vitest run src/__tests__/types.test.ts
```

Expected: FAIL — types don't exist yet.

- [ ] **Step 3: Create all types**

```typescript
// src/types/index.ts

// === Track & Content Types ===

export interface Track {
  id: string;
  name: string;
  examCode: string;
  domains: Domain[];
  passingScore: number;
  totalQuestions: number;
  examDuration: number; // minutes
  color: string;
}

export interface Domain {
  id: string;
  name: string;
  weight: number; // exam percentage (e.g., 20)
  objectives: Objective[];
}

export interface Objective {
  id: string;
  code: string; // e.g., "2.1"
  title: string;
  description: string;
}

export interface Question {
  id: string; // deterministic: "aplus-net-001"
  trackId: string;
  domainId: string;
  objectiveId?: string;
  question: string;
  options: string[];
  correctIndex: number;
  explanation: string;
  difficulty: 'easy' | 'medium' | 'hard';
}

export interface Flashcard {
  id: string; // deterministic: "aplus-net-fc-001"
  trackId: string;
  domainId: string;
  front: string;
  back: string;
  difficulty: 'easy' | 'medium' | 'hard';
}

export interface Lesson {
  id: string;
  trackId: string;
  domainId: string;
  objectiveId: string;
  title: string;
  body: string; // markdown
  keyConcepts: string[];
  examTips?: string[];
}

// === User Progress Types ===

export interface TrackEnrollment {
  trackId: string;
  examDate: string; // ISO date
  baselineType: BaselineType;
  planStyle: PlanStyle;
  startedAt: string;
  status: 'active' | 'completed' | 'paused';
}

export interface DomainProgress {
  trackId: string;
  domainId: string;
  quizScore: number; // 0-100
  flashcardMastery: number; // 0-100 (% mature cards)
  aiConfidence: number; // 0-100
  lessonsCompleted: number;
  totalLessons: number;
}

export interface ReadinessScore {
  overall: number; // 0-100
  byDomain: Record<string, number>;
  isExamReady: boolean; // overall >= 85 && all domains >= 70
}

export type BaselineType = 'diagnostic' | 'quick-placement' | 'self-assessment';
export type PlanStyle = 'strict' | 'flexible' | 'hybrid';
export type UrgencyLevel = 'on-track' | 'gentle-nudge' | 'auto-rebalance' | 'smart-triage';
export type TutorMode = 'teach' | 'quiz' | 'socratic' | 'assess';

// === Study Plan Types ===

export interface StudyPlan {
  trackId: string;
  planStyle: PlanStyle;
  urgencyLevel: UrgencyLevel;
  lastRebalanced?: string;
  days: PlanDay[];
}

export interface PlanDay {
  date: string; // ISO date
  scheduledTopics: ScheduledTopic[];
  completedTopics: string[]; // topic IDs
  minutesPlanned: number;
  minutesActual: number;
}

export interface ScheduledTopic {
  id: string;
  domainId: string;
  type: 'lesson' | 'quiz' | 'flashcards' | 'tutor';
  title: string;
}

// === Spaced Repetition Types ===

export interface FlashcardState {
  cardId: string;
  ease: number; // >= 1.3
  interval: number; // days
  nextReview: string; // ISO date
  repetitions: number;
  source: 'curated' | 'ai';
}

export type SRSRating = 0 | 1 | 2 | 3; // Again | Hard | Good | Easy

// === Quiz Types ===

export interface QuizResult {
  id: string;
  trackId: string;
  domainId: string;
  score: number; // 0-100
  answers: QuizAnswer[];
  timestamp: string;
  type: 'baseline' | 'practice' | 'review';
  duration: number; // seconds
}

export interface QuizAnswer {
  questionId: string;
  selectedIndex: number;
  correct: boolean;
}

// === AI Tutor Types ===

export interface TutorSession {
  id: string;
  trackId: string;
  domainId: string;
  messages: TutorMessage[];
  aiAssessment?: AIAssessment;
  timestamp: string;
}

export interface TutorMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface AIAssessment {
  domainId: string;
  confidence: number;
  strengths: string[];
  weaknesses: string[];
  misconceptions: string[];
  recommendedFocus: string[];
}

// === Knowledge Transfer Types ===

export interface KnowledgeGroup {
  id: string;
  name: string;
  color: string;
  tracks: KnowledgeTrackMapping[];
  transferRate: number; // 0-1
  description: string;
}

export interface KnowledgeTrackMapping {
  trackId: string;
  domainIds: string[];
}

// === Shared Progress Types ===

export interface SharedProgress {
  token: string;
  userId: string;
  trackId: string;
  expiresAt: string;
}

// === Daily Activity ===

export interface DailyActivity {
  date: string;
  minutesStudied: number;
  cardsReviewed: number;
  quizzesTaken: number;
  lessonsCompleted: number;
}

export interface Streak {
  current: number;
  longest: number;
  lastDate: string;
}

// === User Preferences ===

export interface UserPreferences {
  dailyGoalMinutes: number;
  reminderEnabled: boolean;
  activeTrackId?: string;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npx vitest run src/__tests__/types.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/types/index.ts src/__tests__/types.test.ts
git commit -m "feat: add TypeScript types for tracks, progress, SRS, tutor, and knowledge transfer"
```

### Task 4: Static Track Data — A+ (Seed)

**Files:**
- Create: `src/data/tracks.ts`
- Create: `src/data/knowledge-map.ts`
- Create: `src/data/aplus-objectives.ts`
- Create: `src/data/aplus-questions.ts` (seed — 5 per domain to start)
- Create: `src/data/aplus-flashcards.ts` (seed — 5 per domain)
- Create: `src/data/aplus-lessons.ts` (seed — 1 per domain)
- Create: `src/data/aplus-diagnostic.ts` (seed — 3 per domain)
- Create: `src/data/updates.ts`

- [ ] **Step 1: Create tracks.ts with all 4 track definitions**

```typescript
// src/data/tracks.ts
import type { Track } from '@/types';

export const tracks: Track[] = [
  {
    id: 'aplus',
    name: 'CompTIA A+',
    examCode: '220-1101 & 1102',
    domains: [], // populated from objectives files
    passingScore: 675,
    totalQuestions: 90,
    examDuration: 90,
    color: '#22c55e',
  },
  {
    id: 'aws-ccp',
    name: 'AWS Cloud Practitioner',
    examCode: 'CLF-C02',
    domains: [],
    passingScore: 700,
    totalQuestions: 65,
    examDuration: 90,
    color: '#6c5ce7',
  },
  {
    id: 'cka',
    name: 'Certified Kubernetes Administrator',
    examCode: 'CKA',
    domains: [],
    passingScore: 66,
    totalQuestions: 17, // performance-based
    examDuration: 120,
    color: '#3498db',
  },
  {
    id: 'puppet8',
    name: 'Puppet 8 Practitioner',
    examCode: 'Puppet-8',
    domains: [],
    passingScore: 70,
    totalQuestions: 60,
    examDuration: 90,
    color: '#e056a0',
  },
];

export function getTrack(id: string): Track | undefined {
  return tracks.find(t => t.id === id);
}
```

- [ ] **Step 2: Create knowledge-map.ts with 6 overlap groups**

```typescript
// src/data/knowledge-map.ts
import type { KnowledgeGroup } from '@/types';

export const knowledgeGroups: KnowledgeGroup[] = [
  {
    id: 'networking',
    name: 'Networking',
    color: '#00d4aa',
    transferRate: 0.7,
    description: 'TCP/IP, DNS, DHCP, subnets, ports — learn once, apply across exams',
    tracks: [
      { trackId: 'aplus', domainIds: ['aplus-networking'] },
      { trackId: 'aws-ccp', domainIds: ['aws-ccp-technology'] },
      { trackId: 'cka', domainIds: ['cka-networking'] },
    ],
  },
  {
    id: 'security',
    name: 'Security',
    color: '#6c5ce7',
    transferRate: 0.5,
    description: 'Authentication, encryption, access control — A+ foundations unlock AWS security',
    tracks: [
      { trackId: 'aplus', domainIds: ['aplus-security'] },
      { trackId: 'aws-ccp', domainIds: ['aws-ccp-security'] },
    ],
  },
  {
    id: 'cloud-virtualization',
    name: 'Cloud & Virtualization',
    color: '#f39c12',
    transferRate: 0.6,
    description: 'VMs, containers, cloud models — the foundation chain from hardware to orchestration',
    tracks: [
      { trackId: 'aplus', domainIds: ['aplus-virtualization'] },
      { trackId: 'aws-ccp', domainIds: ['aws-ccp-cloud-concepts'] },
      { trackId: 'cka', domainIds: ['cka-cluster-architecture'] },
    ],
  },
  {
    id: 'troubleshooting',
    name: 'Troubleshooting',
    color: '#e74c3c',
    transferRate: 0.4,
    description: 'Systematic debugging methodology — same mindset, different stack layers',
    tracks: [
      { trackId: 'aplus', domainIds: ['aplus-hw-troubleshooting', 'aplus-sw-troubleshooting'] },
      { trackId: 'cka', domainIds: ['cka-troubleshooting'] },
    ],
  },
  {
    id: 'infra-automation',
    name: 'Infrastructure Automation',
    color: '#3498db',
    transferRate: 0.5,
    description: 'Declarative config, desired state, idempotency — core concepts shared between K8s and Puppet',
    tracks: [
      { trackId: 'cka', domainIds: ['cka-workloads'] },
      { trackId: 'puppet8', domainIds: ['puppet8-orchestration'] },
    ],
  },
  {
    id: 'server-admin',
    name: 'Server Administration',
    color: '#e056a0',
    transferRate: 0.45,
    description: 'Server config, certificates, scaling — managing infrastructure at the server level',
    tracks: [
      { trackId: 'cka', domainIds: ['cka-cluster-architecture'] },
      { trackId: 'puppet8', domainIds: ['puppet8-server-admin'] },
    ],
  },
];

export function getOverlapsForDomain(trackId: string, domainId: string): KnowledgeGroup[] {
  return knowledgeGroups.filter(g =>
    g.tracks.some(t => t.trackId === trackId && t.domainIds.includes(domainId))
  );
}

export function getTransferTargets(trackId: string, domainId: string): { trackId: string; domainId: string; transferRate: number; groupName: string }[] {
  const groups = getOverlapsForDomain(trackId, domainId);
  const targets: { trackId: string; domainId: string; transferRate: number; groupName: string }[] = [];
  for (const group of groups) {
    for (const mapping of group.tracks) {
      if (mapping.trackId !== trackId) {
        for (const did of mapping.domainIds) {
          targets.push({ trackId: mapping.trackId, domainId: did, transferRate: group.transferRate, groupName: group.name });
        }
      }
    }
  }
  return targets;
}
```

- [ ] **Step 3: Create aplus-objectives.ts with all 9 domains**

Create with real CompTIA A+ Core 1 (220-1101) and Core 2 (220-1102) exam domains and objectives. Each domain needs: id, name, weight, and array of objectives with code, title, description.

A+ Core 1 domains: Mobile Devices (15%), Networking (20%), Hardware (27%), Virtualization & Cloud Computing (12%), Hardware & Network Troubleshooting (26%).
A+ Core 2 domains: Operating Systems (22%), Security (16%), Software Troubleshooting (22%), Operational Procedures (18%).

Example structure (complete one domain, repeat pattern for all 9):

```typescript
// src/data/aplus-objectives.ts
import type { Domain } from '@/types';

export const aplusDomains: Domain[] = [
  {
    id: 'aplus-mobile',
    name: 'Mobile Devices',
    weight: 15,
    objectives: [
      { id: 'aplus-mobile-1.1', code: '1.1', title: 'Install and configure laptop hardware and components', description: 'Given a scenario, install and configure laptop hardware and components.' },
      { id: 'aplus-mobile-1.2', code: '1.2', title: 'Compare and contrast the display components of mobile devices', description: 'Types of displays (IPS, TN, OLED), Wi-Fi antenna connector/placement, camera/microphone.' },
      // ... remaining objectives for this domain
    ],
  },
  {
    id: 'aplus-networking',
    name: 'Networking',
    weight: 20,
    objectives: [
      { id: 'aplus-net-2.1', code: '2.1', title: 'Compare and contrast TCP and UDP ports, protocols, and their purposes', description: 'Common ports (21, 22, 23, 25, 53, 80, 110, 143, 443, 3389, etc.).' },
      // ...
    ],
  },
  // ... remaining 7 domains following same pattern
];
```

*Use official CompTIA A+ 220-1101 and 220-1102 exam objectives for codes and titles.*

- [ ] **Step 4: Create seed question, flashcard, diagnostic, and lesson files for A+**

Create `aplus-questions.ts`, `aplus-flashcards.ts`, `aplus-diagnostic.ts`, `aplus-lessons.ts` with 5 seed items per domain (will be expanded later or supplemented by AI). Example templates:

```typescript
// src/data/aplus-questions.ts
import type { Question } from '@/types';

export const aplusQuestions: Question[] = [
  {
    id: 'aplus-net-001',
    trackId: 'aplus',
    domainId: 'aplus-networking',
    objectiveId: 'aplus-net-2.1',
    question: 'Which port is used by HTTPS by default?',
    options: ['Port 80', 'Port 443', 'Port 8080', 'Port 3389'],
    correctIndex: 1,
    explanation: 'HTTPS uses port 443 by default. Port 80 is HTTP, 8080 is an alternative HTTP port, and 3389 is RDP.',
    difficulty: 'easy',
  },
  // ... 4 more per domain, 9 domains = 45 total seed questions
];
```

```typescript
// src/data/aplus-flashcards.ts
import type { Flashcard } from '@/types';

export const aplusFlashcards: Flashcard[] = [
  {
    id: 'aplus-net-fc-001',
    trackId: 'aplus',
    domainId: 'aplus-networking',
    front: 'What port does DNS use?',
    back: 'Port 53 (both TCP and UDP)',
    difficulty: 'easy',
  },
  // ... 4 more per domain, 9 domains = 45 total seed flashcards
];
```

```typescript
// src/data/aplus-lessons.ts
import type { Lesson } from '@/types';

export const aplusLessons: Lesson[] = [
  {
    id: 'aplus-net-lesson-001',
    trackId: 'aplus',
    domainId: 'aplus-networking',
    objectiveId: 'aplus-net-2.1',
    title: 'TCP/IP Ports and Protocols',
    body: '## Common Ports\n\nNetwork services communicate through numbered ports...\n\n### Well-Known Ports (0-1023)\n\n| Port | Protocol | Service |\n|------|----------|--------|\n| 21 | TCP | FTP |\n| 22 | TCP | SSH |\n| 53 | TCP/UDP | DNS |\n| 80 | TCP | HTTP |\n| 443 | TCP | HTTPS |\n\n...',
    keyConcepts: ['TCP vs UDP', 'Well-known ports', 'Port ranges', 'Protocol purposes'],
    examTips: ['Memorize ports 20-23, 25, 53, 67-68, 80, 110, 143, 443, 445, 3389', 'Know which protocols use TCP vs UDP vs both'],
  },
  // ... 1 per domain, 9 domains = 9 seed lessons
];
```

`aplus-diagnostic.ts` follows the same `Question[]` shape as `aplus-questions.ts` but with 3 items per domain (27 total), kept separate to avoid repetition during practice quizzes.

- [ ] **Step 5: Create updates.ts**

```typescript
// src/data/updates.ts
export const APP_VERSION = '0.1.0';

export const updates = [
  {
    version: '0.1.0',
    date: '2026-03-22',
    title: 'Welcome to CertStudy',
    highlights: [
      'AI-powered certification study platform',
      'Spaced repetition flashcards',
      'Adaptive study planning',
      'Cross-exam knowledge transfer',
    ],
  },
];
```

- [ ] **Step 6: Commit**

```bash
git add src/data/
git commit -m "feat: add track definitions, knowledge map, and A+ seed content"
```

### Task 5: Copy Test Infrastructure

**Files:**
- Copy: `src/__tests__/setup.ts`
- Copy: `vitest.config.ts` (already done in Task 1)

- [ ] **Step 1: Copy test setup from Selah**

```bash
mkdir -p /home/merm/projects/certstudy/src/__tests__
cp /home/merm/projects/selah/src/__tests__/setup.ts /home/merm/projects/certstudy/src/__tests__/setup.ts
```

- [ ] **Step 2: Adapt localStorage key mocks**

In `setup.ts`, change any Selah-specific localStorage key references:
- `bible_token` → `cert_token`
- `bible_user` → `cert_user`
- `selah_*` → `cert_*`

- [ ] **Step 3: Run existing types test to verify infrastructure works**

```bash
npx vitest run
```

Expected: PASS (types.test.ts passes)

- [ ] **Step 4: Commit**

```bash
git add src/__tests__/setup.ts
git commit -m "feat: add test infrastructure from Selah"
```

---

## Chunk 2: Learning Engine (Client-Side)

### Task 6: SM-2 Spaced Repetition Engine

**Files:**
- Create: `src/lib/srs-engine.ts`
- Test: `src/__tests__/srs-engine.test.ts`

- [ ] **Step 1: Write SRS engine tests**

```typescript
// src/__tests__/srs-engine.test.ts
import { describe, it, expect } from 'vitest';
import { calculateNextReview, isDue, getNewCardDefaults } from '@/lib/srs-engine';
import type { FlashcardState, SRSRating } from '@/types';

describe('SRS Engine', () => {
  it('new card defaults have ease 2.5 and interval 0', () => {
    const defaults = getNewCardDefaults('aplus-net-001', 'curated');
    expect(defaults.ease).toBe(2.5);
    expect(defaults.interval).toBe(0);
    expect(defaults.repetitions).toBe(0);
  });

  it('first correct answer sets interval to 1 day', () => {
    const state = getNewCardDefaults('card1', 'curated');
    const next = calculateNextReview(state, 2); // Good
    expect(next.interval).toBe(1);
    expect(next.repetitions).toBe(1);
  });

  it('second correct answer sets interval to 6 days', () => {
    const state: FlashcardState = {
      cardId: 'card1', ease: 2.5, interval: 1, nextReview: '2026-03-22', repetitions: 1, source: 'curated',
    };
    const next = calculateNextReview(state, 2); // Good
    expect(next.interval).toBe(6);
  });

  it('subsequent correct uses ease factor', () => {
    const state: FlashcardState = {
      cardId: 'card1', ease: 2.5, interval: 6, nextReview: '2026-03-22', repetitions: 2, source: 'curated',
    };
    const next = calculateNextReview(state, 2); // Good
    expect(next.interval).toBe(15); // 6 * 2.5 = 15
  });

  it('"Again" resets interval to 1 and drops ease', () => {
    const state: FlashcardState = {
      cardId: 'card1', ease: 2.5, interval: 15, nextReview: '2026-03-22', repetitions: 3, source: 'curated',
    };
    const next = calculateNextReview(state, 0); // Again
    expect(next.interval).toBe(1);
    expect(next.ease).toBeLessThan(2.5);
    expect(next.repetitions).toBe(0);
  });

  it('ease never drops below 1.3', () => {
    let state = getNewCardDefaults('card1', 'curated');
    // Hit "Again" many times
    for (let i = 0; i < 20; i++) {
      state = calculateNextReview(state, 0);
    }
    expect(state.ease).toBeGreaterThanOrEqual(1.3);
  });

  it('isDue returns true when nextReview is today or earlier', () => {
    const pastState: FlashcardState = {
      cardId: 'card1', ease: 2.5, interval: 1, nextReview: '2026-03-20', repetitions: 1, source: 'curated',
    };
    expect(isDue(pastState, '2026-03-22')).toBe(true);
  });

  it('isDue returns false when nextReview is in the future', () => {
    const futureState: FlashcardState = {
      cardId: 'card1', ease: 2.5, interval: 1, nextReview: '2026-03-25', repetitions: 1, source: 'curated',
    };
    expect(isDue(futureState, '2026-03-22')).toBe(false);
  });

  it('"Easy" gives longer interval than "Good"', () => {
    const state: FlashcardState = {
      cardId: 'card1', ease: 2.5, interval: 6, nextReview: '2026-03-22', repetitions: 2, source: 'curated',
    };
    const good = calculateNextReview(state, 2);
    const easy = calculateNextReview(state, 3);
    expect(easy.interval).toBeGreaterThan(good.interval);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npx vitest run src/__tests__/srs-engine.test.ts
```

Expected: FAIL

- [ ] **Step 3: Implement SM-2 engine**

```typescript
// src/lib/srs-engine.ts
import type { FlashcardState, SRSRating } from '@/types';

export function getNewCardDefaults(cardId: string, source: 'curated' | 'ai'): FlashcardState {
  return {
    cardId,
    ease: 2.5,
    interval: 0,
    nextReview: new Date().toISOString().split('T')[0],
    repetitions: 0,
    source,
  };
}

export function calculateNextReview(state: FlashcardState, rating: SRSRating): FlashcardState {
  let { ease, interval, repetitions } = state;

  // Update ease factor
  ease = Math.max(1.3, ease + (0.1 - (3 - rating) * (0.08 + (3 - rating) * 0.02)));

  if (rating === 0) {
    // "Again" — reset
    interval = 1;
    repetitions = 0;
  } else {
    repetitions += 1;
    if (repetitions === 1) {
      interval = 1;
    } else if (repetitions === 2) {
      interval = 6;
    } else {
      interval = Math.round(interval * ease);
    }

    // "Easy" bonus: multiply interval by 1.3
    if (rating === 3) {
      interval = Math.round(interval * 1.3);
    }
  }

  const today = new Date();
  const nextDate = new Date(today);
  nextDate.setDate(today.getDate() + interval);
  const nextReview = nextDate.toISOString().split('T')[0];

  return { ...state, ease, interval, nextReview, repetitions };
}

export function isDue(state: FlashcardState, today: string): boolean {
  return state.nextReview <= today;
}

export function getDueCards(states: FlashcardState[], today: string): FlashcardState[] {
  return states.filter(s => isDue(s, today)).sort((a, b) => a.nextReview.localeCompare(b.nextReview));
}

export function isMature(state: FlashcardState): boolean {
  return state.interval >= 21;
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run src/__tests__/srs-engine.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/srs-engine.ts src/__tests__/srs-engine.test.ts
git commit -m "feat: implement SM-2 spaced repetition engine with tests"
```

### Task 7: Readiness Calculator

**Files:**
- Create: `src/lib/readiness.ts`
- Test: `src/__tests__/readiness.test.ts`

- [ ] **Step 1: Write readiness tests**

```typescript
// src/__tests__/readiness.test.ts
import { describe, it, expect } from 'vitest';
import { calculateReadiness, calculateDomainReadiness } from '@/lib/readiness';
import type { DomainProgress, Domain } from '@/types';

describe('Readiness Calculator', () => {
  const domains: Domain[] = [
    { id: 'networking', name: 'Networking', weight: 20, objectives: [] },
    { id: 'hardware', name: 'Hardware', weight: 27, objectives: [] },
    { id: 'security', name: 'Security', weight: 16, objectives: [] },
  ];

  it('calculates domain readiness as weighted sum of 3 signals', () => {
    const progress: DomainProgress = {
      trackId: 'aplus', domainId: 'networking',
      quizScore: 80, flashcardMastery: 60, aiConfidence: 70,
      lessonsCompleted: 3, totalLessons: 5,
    };
    const score = calculateDomainReadiness(progress);
    // (80 * 0.4) + (60 * 0.3) + (70 * 0.3) = 32 + 18 + 21 = 71
    expect(score).toBe(71);
  });

  it('calculates overall readiness weighted by domain exam weight', () => {
    const progressMap: DomainProgress[] = [
      { trackId: 'aplus', domainId: 'networking', quizScore: 80, flashcardMastery: 60, aiConfidence: 70, lessonsCompleted: 3, totalLessons: 5 },
      { trackId: 'aplus', domainId: 'hardware', quizScore: 90, flashcardMastery: 80, aiConfidence: 85, lessonsCompleted: 5, totalLessons: 5 },
      { trackId: 'aplus', domainId: 'security', quizScore: 70, flashcardMastery: 50, aiConfidence: 60, lessonsCompleted: 2, totalLessons: 4 },
    ];
    const result = calculateReadiness(progressMap, domains);
    expect(result.overall).toBeGreaterThan(0);
    expect(result.overall).toBeLessThanOrEqual(100);
    expect(result.byDomain).toHaveProperty('networking');
    expect(result.byDomain).toHaveProperty('hardware');
  });

  it('isExamReady requires overall >= 85 and all domains >= 70', () => {
    const highProgress: DomainProgress[] = [
      { trackId: 'aplus', domainId: 'networking', quizScore: 95, flashcardMastery: 90, aiConfidence: 90, lessonsCompleted: 5, totalLessons: 5 },
      { trackId: 'aplus', domainId: 'hardware', quizScore: 90, flashcardMastery: 85, aiConfidence: 88, lessonsCompleted: 5, totalLessons: 5 },
      { trackId: 'aplus', domainId: 'security', quizScore: 88, flashcardMastery: 80, aiConfidence: 82, lessonsCompleted: 4, totalLessons: 4 },
    ];
    const result = calculateReadiness(highProgress, domains);
    expect(result.isExamReady).toBe(true);
  });

  it('not exam ready if any domain below 70', () => {
    const mixedProgress: DomainProgress[] = [
      { trackId: 'aplus', domainId: 'networking', quizScore: 95, flashcardMastery: 90, aiConfidence: 90, lessonsCompleted: 5, totalLessons: 5 },
      { trackId: 'aplus', domainId: 'hardware', quizScore: 90, flashcardMastery: 85, aiConfidence: 88, lessonsCompleted: 5, totalLessons: 5 },
      { trackId: 'aplus', domainId: 'security', quizScore: 40, flashcardMastery: 30, aiConfidence: 35, lessonsCompleted: 1, totalLessons: 4 },
    ];
    const result = calculateReadiness(mixedProgress, domains);
    expect(result.isExamReady).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npx vitest run src/__tests__/readiness.test.ts
```

- [ ] **Step 3: Implement readiness calculator**

```typescript
// src/lib/readiness.ts
import type { DomainProgress, Domain, ReadinessScore } from '@/types';

export function calculateDomainReadiness(progress: DomainProgress): number {
  return Math.round(
    (progress.quizScore * 0.4) +
    (progress.flashcardMastery * 0.3) +
    (progress.aiConfidence * 0.3)
  );
}

export function calculateReadiness(
  progressList: DomainProgress[],
  domains: Domain[]
): ReadinessScore {
  const totalWeight = domains.reduce((sum, d) => sum + d.weight, 0);
  const byDomain: Record<string, number> = {};
  let weightedSum = 0;

  for (const domain of domains) {
    const progress = progressList.find(p => p.domainId === domain.id);
    const score = progress ? calculateDomainReadiness(progress) : 0;
    byDomain[domain.id] = score;
    weightedSum += score * (domain.weight / totalWeight);
  }

  const overall = Math.round(weightedSum);
  const allDomainsAbove70 = Object.values(byDomain).every(s => s >= 70);
  const isExamReady = overall >= 85 && allDomainsAbove70;

  return { overall, byDomain, isExamReady };
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run src/__tests__/readiness.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/readiness.ts src/__tests__/readiness.test.ts
git commit -m "feat: implement readiness calculator with weighted domain scoring"
```

### Task 8: Progressive Urgency Checker

**Files:**
- Create: `src/lib/urgency.ts`
- Test: `src/__tests__/urgency.test.ts`

- [ ] **Step 1: Write urgency tests**

```typescript
// src/__tests__/urgency.test.ts
import { describe, it, expect } from 'vitest';
import { calculateUrgency } from '@/lib/urgency';
import type { PlanDay } from '@/types';

describe('Urgency Checker', () => {
  function makeDays(completionRates: number[]): PlanDay[] {
    return completionRates.map((rate, i) => ({
      date: `2026-03-${String(15 + i).padStart(2, '0')}`,
      scheduledTopics: [{ id: 't1', domainId: 'd1', type: 'lesson' as const, title: 'Test' }],
      completedTopics: rate >= 1 ? ['t1'] : [],
      minutesPlanned: 60,
      minutesActual: rate * 60,
    }));
  }

  it('on-track when >= 80% weekly completion', () => {
    const days = makeDays([1, 1, 1, 1, 1, 0, 1]); // 6/7 = 86%
    const result = calculateUrgency(days, '2026-04-14', '2026-03-22');
    expect(result).toBe('on-track');
  });

  it('gentle-nudge when 1-2 days missed', () => {
    const days = makeDays([1, 1, 0, 1, 0, 1, 1]); // 5/7 = 71%
    const result = calculateUrgency(days, '2026-04-14', '2026-03-22');
    expect(result).toBe('gentle-nudge');
  });

  it('auto-rebalance when < 60% weekly completion', () => {
    const days = makeDays([1, 0, 0, 0, 0, 0, 1]); // 2/7 = 29%
    const result = calculateUrgency(days, '2026-04-14', '2026-03-22');
    expect(result).toBe('auto-rebalance');
  });

  it('smart-triage when < 2 weeks to exam and < 70% covered', () => {
    const days = makeDays([0, 0, 0, 1, 0, 0, 0]); // 1/7 = 14%
    const result = calculateUrgency(days, '2026-03-30', '2026-03-22'); // 8 days to exam
    expect(result).toBe('smart-triage');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement urgency checker**

```typescript
// src/lib/urgency.ts
import type { PlanDay, UrgencyLevel } from '@/types';

export function calculateUrgency(
  recentDays: PlanDay[],
  examDate: string,
  today: string
): UrgencyLevel {
  const daysToExam = Math.ceil(
    (new Date(examDate).getTime() - new Date(today).getTime()) / (1000 * 60 * 60 * 24)
  );

  // Calculate weekly completion rate
  const lastWeek = recentDays.slice(-7);
  const completedCount = lastWeek.filter(d => {
    if (d.scheduledTopics.length === 0) return true; // rest day
    return d.completedTopics.length >= d.scheduledTopics.length;
  }).length;
  const completionRate = lastWeek.length > 0 ? completedCount / lastWeek.length : 1;

  // Calculate overall material coverage
  const allDays = recentDays;
  const totalScheduled = allDays.reduce((s, d) => s + d.scheduledTopics.length, 0);
  const totalCompleted = allDays.reduce((s, d) => s + d.completedTopics.length, 0);
  const coverageRate = totalScheduled > 0 ? totalCompleted / totalScheduled : 0;

  // Smart Triage: < 2 weeks to exam AND < 70% covered
  if (daysToExam < 14 && coverageRate < 0.7) {
    return 'smart-triage';
  }

  // Auto-Rebalance: < 60% weekly completion (spec says "for 2 weeks" but
  // we check the last 7 days available — the planner Lambda can check longer history server-side)
  if (completionRate < 0.6) {
    return 'auto-rebalance';
  }

  // Gentle Nudge: < 80% weekly completion
  if (completionRate < 0.8) {
    return 'gentle-nudge';
  }

  return 'on-track';
}

export function getUrgencyColor(level: UrgencyLevel): string {
  switch (level) {
    case 'on-track': return '#00d4aa';
    case 'gentle-nudge': return '#f39c12';
    case 'auto-rebalance': return '#e67e22';
    case 'smart-triage': return '#e74c3c';
  }
}

export function getUrgencyLabel(level: UrgencyLevel): string {
  switch (level) {
    case 'on-track': return 'On Track';
    case 'gentle-nudge': return 'Slightly Behind';
    case 'auto-rebalance': return 'Plan Adjusted';
    case 'smart-triage': return 'Focus Mode';
  }
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run src/__tests__/urgency.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/urgency.ts src/__tests__/urgency.test.ts
git commit -m "feat: implement progressive urgency checker"
```

### Task 9: Knowledge Transfer Engine

**Files:**
- Create: `src/lib/knowledge-transfer.ts`
- Test: `src/__tests__/knowledge-transfer.test.ts`

- [ ] **Step 1: Write knowledge transfer tests**

```typescript
// src/__tests__/knowledge-transfer.test.ts
import { describe, it, expect } from 'vitest';
import { calculateTransferBonus, applyTransfers } from '@/lib/knowledge-transfer';
import type { DomainProgress } from '@/types';

describe('Knowledge Transfer', () => {
  it('transfers mastery at the configured rate', () => {
    const bonus = calculateTransferBonus(80, 0.7); // 80% mastery, 70% transfer
    expect(bonus).toBe(56); // 80 * 0.7
  });

  it('transfer bonus does not exceed 100', () => {
    const bonus = calculateTransferBonus(100, 0.7);
    expect(bonus).toBeLessThanOrEqual(100);
  });

  it('applyTransfers returns boosted progress for linked domains', () => {
    const sourceProgress: DomainProgress[] = [
      { trackId: 'aplus', domainId: 'aplus-networking', quizScore: 80, flashcardMastery: 70, aiConfidence: 75, lessonsCompleted: 3, totalLessons: 5 },
    ];
    const targetProgress: DomainProgress[] = [
      { trackId: 'aws-ccp', domainId: 'aws-ccp-technology', quizScore: 20, flashcardMastery: 10, aiConfidence: 15, lessonsCompleted: 0, totalLessons: 4 },
    ];
    const result = applyTransfers(sourceProgress, targetProgress);
    const awsTech = result.find(p => p.domainId === 'aws-ccp-technology');
    expect(awsTech).toBeDefined();
    // Should have some boost from A+ networking
    expect(awsTech!.quizScore).toBeGreaterThan(20);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement knowledge transfer**

```typescript
// src/lib/knowledge-transfer.ts
import type { DomainProgress } from '@/types';
import { knowledgeGroups, getTransferTargets } from '@/data/knowledge-map';

export function calculateTransferBonus(mastery: number, transferRate: number): number {
  return Math.min(100, Math.round(mastery * transferRate));
}

export function applyTransfers(
  allProgress: DomainProgress[],
  targetProgress: DomainProgress[]
): DomainProgress[] {
  const result = targetProgress.map(p => ({ ...p }));

  for (const source of allProgress) {
    const targets = getTransferTargets(source.trackId, source.domainId);
    for (const target of targets) {
      const existing = result.find(p => p.trackId === target.trackId && p.domainId === target.domainId);
      if (existing) {
        const quizBonus = calculateTransferBonus(source.quizScore, target.transferRate);
        const flashBonus = calculateTransferBonus(source.flashcardMastery, target.transferRate);
        const aiBonus = calculateTransferBonus(source.aiConfidence, target.transferRate);
        existing.quizScore = Math.min(100, Math.max(existing.quizScore, quizBonus));
        existing.flashcardMastery = Math.min(100, Math.max(existing.flashcardMastery, flashBonus));
        existing.aiConfidence = Math.min(100, Math.max(existing.aiConfidence, aiBonus));
      }
    }
  }

  return result;
}

export function getTransferIndicators(
  allProgress: DomainProgress[],
  trackId: string,
  domainId: string
): { fromTrack: string; bonus: number }[] {
  const indicators: { fromTrack: string; bonus: number }[] = [];
  const groups = knowledgeGroups.filter(g =>
    g.tracks.some(t => t.trackId === trackId && t.domainIds.includes(domainId))
  );

  for (const group of groups) {
    for (const mapping of group.tracks) {
      if (mapping.trackId !== trackId) {
        for (const srcDomainId of mapping.domainIds) {
          const srcProgress = allProgress.find(p => p.trackId === mapping.trackId && p.domainId === srcDomainId);
          if (srcProgress) {
            const avgMastery = (srcProgress.quizScore + srcProgress.flashcardMastery + srcProgress.aiConfidence) / 3;
            const bonus = calculateTransferBonus(avgMastery, group.transferRate);
            if (bonus > 0) {
              indicators.push({ fromTrack: mapping.trackId, bonus });
            }
          }
        }
      }
    }
  }

  return indicators;
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run src/__tests__/knowledge-transfer.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/knowledge-transfer.ts src/__tests__/knowledge-transfer.test.ts
git commit -m "feat: implement cross-track knowledge transfer engine"
```

---

## Chunk 3: Auth System & UI Shell (Copied from Selah)

### Task 10: Copy Auth System

**Files:**
- Copy: `src/lib/auth-context.tsx` from Selah
- Copy: `src/lib/journal-crypto.ts` from Selah
- Copy: `src/components/AuthGuard.tsx` from Selah
- Copy: `src/components/LoginPageClient.tsx` from Selah
- Copy: `src/components/EmailVerificationBanner.tsx` from Selah
- Copy: `src/components/EncryptionRecoveryModal.tsx` from Selah
- Copy: `src/components/RecoveryCodesModal.tsx` from Selah
- Copy: `src/app/login/page.tsx` from Selah
- Copy: `src/app/reset-password/page.tsx` from Selah

- [ ] **Step 1: Copy all auth files**

```bash
cd /home/merm/projects/certstudy
cp /home/merm/projects/selah/src/lib/auth-context.tsx src/lib/
cp /home/merm/projects/selah/src/lib/journal-crypto.ts src/lib/
cp /home/merm/projects/selah/src/components/AuthGuard.tsx src/components/
cp /home/merm/projects/selah/src/components/LoginPageClient.tsx src/components/
cp /home/merm/projects/selah/src/components/EmailVerificationBanner.tsx src/components/
cp /home/merm/projects/selah/src/components/EncryptionRecoveryModal.tsx src/components/ 2>/dev/null || true
cp /home/merm/projects/selah/src/components/RecoveryCodesModal.tsx src/components/ 2>/dev/null || true
mkdir -p src/app/login src/app/reset-password
cp /home/merm/projects/selah/src/app/login/page.tsx src/app/login/
cp /home/merm/projects/selah/src/app/reset-password/page.tsx src/app/reset-password/
```

- [ ] **Step 2: Adapt localStorage keys**

In `auth-context.tsx`, find and replace:
- `bible_token` → `cert_token`
- `bible_user` → `cert_user`
- `selah_` prefix → `cert_` prefix
- Any Selah-specific branding text

- [ ] **Step 3: Adapt LoginPageClient.tsx branding**

- Change app name references from "Selah" to "CertStudy"
- Change tagline to "Master your certifications"
- Change accent colors to teal (`#00d4aa`)
- Change logo/icon to lightning bolt ⚡

- [ ] **Step 4: Create API stub for auth imports**

The auth-context imports from an API client that doesn't exist yet (Task 14). Create a minimal stub:

```typescript
// src/lib/api.ts (stub — will be replaced in Task 14)
const API_BASE = typeof window !== 'undefined' ? window.location.origin : '';

export function buildApiUrl(path: string): string {
  return `${API_BASE}${path.startsWith('/') ? path : '/' + path}`;
}
```

Also create a stub for any Selah-specific imports that auth-context references (e.g., `api-url.ts`):
```bash
cp /home/merm/projects/selah/src/lib/api-url.ts src/lib/ 2>/dev/null || true
```

- [ ] **Step 5: Verify build compiles**

```bash
npm run typecheck
```

Fix remaining import errors — the User type in auth-context references `BibleVersion` which needs to be removed and replaced with CertStudy's User type (no version field, add `preferences?: UserPreferences`).

- [ ] **Step 5: Commit**

```bash
git add src/lib/auth-context.tsx src/lib/journal-crypto.ts src/components/AuthGuard.tsx src/components/LoginPageClient.tsx src/components/EmailVerificationBanner.tsx src/app/login/ src/app/reset-password/
git commit -m "feat: copy auth system from Selah and adapt for CertStudy"
```

### Task 11: Copy UI Shell Components

**Files:**
- Copy: `src/components/Navigation.tsx`
- Copy: `src/components/Toast.tsx`
- Copy: `src/components/Skeleton.tsx`
- Copy: `src/components/ErrorBoundary.tsx`
- Copy: `src/components/WhatsNewModal.tsx`
- Copy: `src/components/TutorialOverlay.tsx`
- Copy: `src/components/OnboardingManager.tsx`
- Copy: `src/components/PwaInstallPrompt.tsx`
- Copy: `src/components/ServiceWorker.tsx`
- Copy: `src/components/Markdown.tsx` (from TNBM)

- [ ] **Step 1: Copy all UI shell components**

```bash
cd /home/merm/projects/certstudy
for comp in Navigation Toast Skeleton ErrorBoundary WhatsNewModal TutorialOverlay OnboardingManager PwaInstallPrompt ServiceWorker KeyboardShortcuts; do
  cp /home/merm/projects/selah/src/components/${comp}.tsx src/components/ 2>/dev/null || true
done
cp /home/merm/projects/thenewbeautifulme/src/components/Markdown.tsx src/components/
```

- [ ] **Step 2: Adapt Navigation.tsx**

Replace Selah nav links with CertStudy links:
- Dashboard (`/`)
- Study (dropdown or link to `/tracks`)
- Flashcards (`/flashcards`)
- Tutor (`/tutor`)
- Progress (`/progress/aplus` — default to active track)
- Settings (`/settings`)

Change branding: "Selah" → "⚡ CertStudy", accent color to `#00d4aa`.

Add status pills to nav: streak count, active track + readiness %.

- [ ] **Step 3: Adapt TutorialOverlay.tsx**

Replace Selah tutorial steps with CertStudy steps:
1. Welcome to CertStudy
2. Choose your certification track
3. Take a baseline assessment
4. Follow your personalized study plan
5. Review flashcards daily
6. Chat with your AI tutor when stuck

- [ ] **Step 4: Verify typecheck passes**

```bash
npm run typecheck
```

- [ ] **Step 5: Commit**

```bash
git add src/components/
git commit -m "feat: copy UI shell components from Selah and adapt for CertStudy"
```

### Task 12: Root Layout & Providers

**Files:**
- Modify: `src/app/layout.tsx`

- [ ] **Step 1: Copy layout structure from Selah**

Reference `/home/merm/projects/selah/src/app/layout.tsx` for the provider wrapping pattern. Create CertStudy's layout with:
- `<AuthProvider>`
- `<ThemeProvider>` (copy `src/lib/theme-context.tsx` from Selah first if needed)
- `<ToastProvider>`
- `<Navigation />`
- `<OnboardingManager />`
- `<ServiceWorker />`
- Metadata: title "CertStudy", description "AI-powered certification study platform"

- [ ] **Step 2: Copy theme context from Selah (required for ThemeProvider)**

```bash
cp /home/merm/projects/selah/src/lib/theme-context.tsx src/lib/
```

Adapt localStorage key: `bible_theme` → `cert_theme`.

- [ ] **Step 3: Verify dev server runs**

```bash
npm run dev
```

Open localhost:3000, verify navigation renders with CertStudy branding.

- [ ] **Step 4: Commit**

```bash
git add src/app/layout.tsx src/lib/theme-context.tsx
git commit -m "feat: add root layout with auth, theme, and toast providers"
```

### Task 13: Copy Settings, Privacy, Accessibility Pages

**Files:**
- Copy: `src/app/settings/page.tsx`
- Copy: `src/app/privacy/page.tsx`
- Copy: `src/app/accessibility/page.tsx`
- Copy: `src/app/updates/page.tsx`

- [ ] **Step 1: Copy pages from Selah**

```bash
for page in settings privacy accessibility updates; do
  mkdir -p src/app/${page}
  cp /home/merm/projects/selah/src/app/${page}/page.tsx src/app/${page}/
done
```

- [ ] **Step 2: Adapt settings page**

- Remove Bible-specific settings (preferred version)
- Add: "Share Progress" section with generate/copy/revoke link
- Add: "Study Preferences" section (daily goal minutes, reminder toggle)
- Change branding references

- [ ] **Step 3: Adapt privacy and accessibility pages**

- Change "Selah" → "CertStudy" throughout
- Change domain references to study.codyjo.com

- [ ] **Step 4: Verify typecheck passes**

```bash
npm run typecheck
```

Expected: No errors. If settings page references Bible-specific types, remove those imports.

- [ ] **Step 5: Commit**

```bash
git add src/app/settings/ src/app/privacy/ src/app/accessibility/ src/app/updates/
git commit -m "feat: copy settings, privacy, accessibility, and updates pages"
```

---

## Chunk 4: API Client & Backend Lambdas

### Task 14: API Client

**Files:**
- Create: `src/lib/api.ts`

- [ ] **Step 1: Create API client with auth + study endpoints**

Reference `/home/merm/projects/selah/src/lib/api.ts` for the pattern (token handling, error handling, base URL). Create CertStudy's API client with these function groups:

**Auth (copied pattern):** `register()`, `login()`, `loginWithToken()`, `logout()`, `changePassword()`, `changeEmail()`, `deleteAccount()`, `verifyEmail()`, `forgotPassword()`, `resetPassword()`

**Tracks:** `getEnrollments()`, `enrollTrack(trackId, examDate, baselineType, planStyle)`, `updateEnrollment(trackId, data)`, `unenrollTrack(trackId)`

**Progress:** `getDomainProgress(trackId)`, `updateDomainProgress(trackId, domainId, data)`, `getDailyActivity(startDate, endDate)`, `logDailyActivity(data)`, `getStreak()`, `updateStreak(data)`

**SRS:** `getFlashcardStates(trackId?)`, `updateFlashcardState(cardId, state)`, `batchUpdateFlashcardStates(states)`

**Quiz:** `saveQuizResult(result)`, `getQuizResults(trackId, domainId?)`

**Lessons:** `getLessonProgress(trackId)`, `markLessonComplete(trackId, lessonId, timeSpent)`

**Tutor:** `sendTutorMessage(trackId, domainId, mode, messages, context)`, `generateContent(trackId, domainId, type)`, `getTutorSessions(trackId, domainId?)`

**Planner:** `generatePlan(trackId, proficiencyMap, examDate, planStyle)`, `rebalancePlan(trackId)`, `getPlan(trackId)`, `updatePlanDay(trackId, date, data)`

**Share:** `createShareLink(trackId)`, `revokeShareLink(token)`, `getSharedProgress(token)`

**Stats:** `getUserStats()`, `exportData()`

- [ ] **Step 2: Verify typecheck**

```bash
npm run typecheck
```

- [ ] **Step 3: Commit**

```bash
git add src/lib/api.ts
git commit -m "feat: add API client with auth, study, tutor, and planner endpoints"
```

### Task 15: API Lambda (CRUD)

**Files:**
- Create: `lambda/api/index.mjs`
- Create: `lambda/api/package.json`

- [ ] **Step 1: Create Lambda package.json**

```json
{
  "name": "certstudy-api",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@aws-sdk/client-dynamodb": "^3.500.0",
    "@aws-sdk/lib-dynamodb": "^3.500.0",
    "@aws-sdk/client-secrets-manager": "^3.500.0"
  }
}
```

- [ ] **Step 2: Create API Lambda**

Reference `/home/merm/projects/selah/lambda/api/index.mjs` for the auth route patterns (register, login, JWT verification, rate limiting). Build the CRUD Lambda with these route groups:

**Auth routes (copy from Selah, adapt table name):**
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/verify-email`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `POST /api/auth/change-password`
- `POST /api/auth/change-email`
- `DELETE /api/auth/account`
- `POST /api/auth/encrypt/setup`
- `POST /api/auth/encrypt/unlock`

**Study routes (new):**
- `GET /api/tracks` — list user's track enrollments
- `POST /api/tracks` — enroll in a track
- `PUT /api/tracks/:trackId` — update enrollment (exam date, etc.)
- `DELETE /api/tracks/:trackId` — unenroll
- `GET /api/progress/:trackId` — get all domain progress for a track
- `PUT /api/progress/:trackId/:domainId` — update domain progress
- `GET /api/srs` — get all flashcard states (optionally filtered by track)
- `PUT /api/srs/:cardId` — update flashcard SRS state
- `POST /api/srs/batch` — batch update flashcard states
- `POST /api/quiz` — save quiz result
- `GET /api/quiz/:trackId` — get quiz results
- `PUT /api/lessons/:trackId/:lessonId` — mark lesson complete
- `GET /api/lessons/:trackId` — get lesson progress
- `GET /api/plan/:trackId` — get study plan
- `PUT /api/plan/:trackId/day/:date` — update plan day
- `GET /api/activity` — get daily activity range
- `POST /api/activity` — log daily activity
- `GET /api/streak` — get streak
- `PUT /api/streak` — update streak
- `POST /api/share` — create share link
- `DELETE /api/share/:token` — revoke share link
- `GET /api/shared/:token` — get shared progress (no auth)
- `GET /api/stats` — get user stats
- `GET /api/tutor/sessions` — list tutor sessions (for history)
- `GET /api/export` — export all user data

**DynamoDB table:** `certstudy-data` (from env var `TABLE_NAME`)

- [ ] **Step 3: Install Lambda dependencies**

```bash
cd /home/merm/projects/certstudy/lambda/api && npm ci
```

- [ ] **Step 4: Commit**

```bash
git add lambda/api/
git commit -m "feat: add API Lambda with auth and study CRUD routes"
```

### Task 16: AI Tutor Lambda

**Files:**
- Create: `lambda/tutor/index.mjs`
- Create: `lambda/tutor/package.json`

- [ ] **Step 1: Create Tutor Lambda package.json**

```json
{
  "name": "certstudy-tutor",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@anthropic-ai/sdk": "^0.78.0",
    "@aws-sdk/client-dynamodb": "^3.500.0",
    "@aws-sdk/lib-dynamodb": "^3.500.0",
    "@aws-sdk/client-secrets-manager": "^3.500.0"
  }
}
```

- [ ] **Step 2: Create Tutor Lambda**

Reference `/home/merm/projects/selah/lambda/interpret/index.mjs` for the Claude API call pattern. Build the tutor with:

**Routes:**
- `POST /api/tutor/chat` — tutor conversation (teach/quiz/socratic/assess modes)
- `POST /api/tutor/generate` — content generation (questions/flashcards)

**System prompt construction per mode:**

For `teach` mode:
```
You are a certification exam tutor. Explain the following concept clearly with examples.
Exam: {trackName} ({examCode})
Domain: {domainName}
Objective: {objectiveTitle}
Student's current level: {quizScore}% on quizzes, {lessonsCompleted}/{totalLessons} lessons completed.
Recent mistakes: {recentMistakes}
After explaining, ask one follow-up question to check understanding.
```

For `socratic` mode:
```
You are a Socratic tutor. Do NOT give direct answers. Instead, ask guiding questions that lead the student to discover the answer themselves.
[Same context as teach mode]
The student is struggling with: {topic}
```

For `quiz` mode:
```
You are a certification exam quiz master. Ask one question at a time matching the real exam format.
Exam: {trackName} ({examCode})
Domain: {domainName}
Student's current level: {quizScore}% on quizzes
Recent mistakes: {recentMistakes}
Start at {difficulty} difficulty. If the student answers correctly, increase difficulty. If wrong, decrease.
After each answer, explain why the correct answer is right and why the chosen answer (if wrong) is incorrect.
Then ask the next question. Format questions with 4 options (A-D).
```

For `assess` mode:
```
[Same as teach mode, plus:]
Evaluate the student's understanding depth. Return a JSON assessment alongside your response:
{"assessment": {"domainId": "...", "confidence": 0-100, "strengths": [...], "weaknesses": [...], "misconceptions": [...], "recommendedFocus": [...]}}
```

For `generate` mode (questions, type="question"):
```
Generate {count} practice questions for {examCode} exam, domain: {domainName}.
Match the difficulty and style of the actual exam.
Return as JSON array: [{"question": "...", "options": ["A...", "B...", "C...", "D..."], "correctIndex": 0, "explanation": "..."}]
```

For `generate` mode (flashcards, type="flashcard"):
```
Generate {count} flashcards for {examCode} exam, domain: {domainName}.
Target the student's weak areas: {weaknesses}
Each card should test one specific concept. Front = question or prompt. Back = concise answer.
Return as JSON array: [{"front": "...", "back": "...", "difficulty": "easy|medium|hard"}]
```

**JWT verification:** Require valid Bearer token (same pattern as Selah's interpret Lambda).

**Rate limits:** 30/user/hour for chat, 20/user/hour for generate. Use DynamoDB counters with TTL.

- [ ] **Step 3: Install dependencies**

```bash
cd /home/merm/projects/certstudy/lambda/tutor && npm ci
```

- [ ] **Step 4: Commit**

```bash
git add lambda/tutor/
git commit -m "feat: add AI Tutor Lambda with teach/quiz/socratic/assess modes"
```

### Task 17: Planner Lambda

**Files:**
- Create: `lambda/planner/index.mjs`
- Create: `lambda/planner/package.json`

- [ ] **Step 1: Create Planner Lambda package.json**

```json
{
  "name": "certstudy-planner",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@anthropic-ai/sdk": "^0.78.0",
    "@aws-sdk/client-dynamodb": "^3.500.0",
    "@aws-sdk/lib-dynamodb": "^3.500.0",
    "@aws-sdk/client-secrets-manager": "^3.500.0"
  }
}
```

- [ ] **Step 2: Create Planner Lambda**

**Routes:**
- `POST /api/plan/generate` — generate initial study plan
- `POST /api/plan/rebalance` — rebalance existing plan

**System prompt for plan generation:**
```
You are a certification exam study planner. Generate a day-by-day study plan.

Exam: {trackName} ({examCode}), exam date: {examDate}
Days remaining: {daysRemaining}
Plan style: {planStyle}

Domain proficiency scores (from baseline):
{domainScores as formatted list}

Domain exam weights:
{domainWeights as formatted list}

Rules:
1. Front-load weak + high-weight domains
2. Space review sessions (revisit topics at increasing intervals)
3. Mix study modes: lessons for new material, quizzes for testing, flashcards daily
4. Each day should have 45-90 minutes of work
5. Include 1 rest day per week

Return as JSON: {"days": [{"date": "YYYY-MM-DD", "topics": [{"domainId": "...", "type": "lesson|quiz|flashcards|tutor", "title": "..."}], "minutesPlanned": N}]}
```

**System prompt for rebalance:**
```
You are a certification exam study planner. Rebalance an existing study plan.

Exam: {trackName} ({examCode}), exam date: {examDate}
Days remaining: {daysRemaining}
Plan style: {planStyle}
Current urgency level: {urgencyLevel}

Current domain progress:
{domainId}: quiz={quizScore}%, flashcards={flashcardMastery}%, ai={aiConfidence}%, lessons={completed}/{total}
[repeat for each domain]

Plan completion so far:
- Total days planned: {totalDays}
- Days completed: {completedDays}
- Days partially completed: {partialDays}
- Days missed: {missedDays}

Rebalance rules:
1. Redistribute remaining uncovered material across remaining days
2. Prioritize domains with highest (exam_weight × gap_to_passing)
3. If urgency is "smart-triage": drop domains already above passing threshold, focus only on highest-impact gaps
4. Keep daily load between 30-120 minutes
5. Include 1 rest day per week unless in triage mode

Return same JSON format as initial plan: {"days": [{"date": "YYYY-MM-DD", "topics": [...], "minutesPlanned": N}]}
```

- [ ] **Step 3: Install dependencies and commit**

```bash
cd /home/merm/projects/certstudy/lambda/planner && npm ci
git add lambda/planner/
git commit -m "feat: add Planner Lambda for study plan generation and rebalancing"
```

---

## Chunk 5: Terraform & CI/CD

### Task 18: Copy and Adapt Terraform

**Files:**
- Copy and adapt: all files in `terraform/`

- [ ] **Step 1: Copy entire Terraform directory from Selah**

```bash
cp -r /home/merm/projects/selah/terraform /home/merm/projects/certstudy/terraform
```

- [ ] **Step 2: Create terraform.tfvars for CertStudy**

```hcl
project            = "certstudy"
domain             = "study.codyjo.com"
region             = "us-west-2"
anthropic_api_key  = "<copy from /home/merm/projects/thenewbeautifulme/terraform/terraform.tfvars>"
```

- [ ] **Step 3: Adapt variables.tf**

Change default values:
- `project` default → `"certstudy"`
- `domain` default → `"study.codyjo.com"`
- Remove Bible-specific variables (preferred_version, etc.)

- [ ] **Step 4: Adapt s3.tf**

Change bucket names:
- `bible-app-site` → `certstudy-site`
- `admin-bible-app-site` → `admin-certstudy-site`

- [ ] **Step 5: Adapt dynamodb.tf**

Change table name: `selah-data` → `certstudy-data` (or use `var.project` if already parameterized).

- [ ] **Step 6: Adapt lambda.tf — 3 Lambdas instead of 2**

Selah has 2 Lambdas (api + interpret). CertStudy needs 3 (api + tutor + planner).

Add third Lambda resource for `certstudy-planner`:
- Runtime: Node 20, ARM64
- Memory: 256MB, Timeout: 30s
- Environment: TABLE_NAME, ANTHROPIC_SECRET_ARN, JWT_SECRET_ARN
- Source: `lambda/planner/`

- [ ] **Step 7: Adapt api_gateway.tf — path-based routing to 3 Lambdas**

Add route integrations:
- `POST /api/tutor/{proxy+}` → tutor Lambda
- `POST /api/plan/{proxy+}` → planner Lambda
- `$default` → api Lambda (catches everything else)

- [ ] **Step 8: Adapt route53.tf**

Change domain to `study.codyjo.com`. This likely uses the existing `codyjo.com` hosted zone — add A/AAAA records pointing to the new CloudFront distribution.

- [ ] **Step 9: Adapt cloudfront.tf, monitoring.tf, cd.tf, waf.tf**

Change resource names and references from `selah`/`bible` to `certstudy`.

- [ ] **Step 10: Commit**

```bash
git add terraform/
git commit -m "feat: adapt Terraform infrastructure for CertStudy with 3 Lambdas"
```

### Task 19: Copy and Adapt CI/CD

**Files:**
- Copy and adapt: `.github/workflows/ci.yml`
- Copy and adapt: `.github/workflows/cd.yml`

- [ ] **Step 1: Copy workflows from Selah**

```bash
mkdir -p /home/merm/projects/certstudy/.github/workflows
cp /home/merm/projects/selah/.github/workflows/ci.yml /home/merm/projects/certstudy/.github/workflows/
cp /home/merm/projects/selah/.github/workflows/cd.yml /home/merm/projects/certstudy/.github/workflows/
```

- [ ] **Step 2: Adapt ci.yml**

- Change any repo-specific references
- Ensure test command is `npm test`
- Ensure build command is `npm run build`

- [ ] **Step 3: Adapt cd.yml**

- Change Lambda install paths to include `lambda/tutor` and `lambda/planner` (3 Lambdas)
- Change S3 bucket name for deployment
- Change CloudFront distribution ID
- Change Terraform workspace/backend references

- [ ] **Step 4: Commit**

```bash
git add .github/
git commit -m "feat: add CI/CD workflows adapted from Selah"
```

### Task 20: PWA & Static Assets

**Files:**
- Create: `public/manifest.json`
- Copy: `public/sw.js` from Selah
- Create: `public/robots.txt`
- Create: `public/sitemap.xml`
- Create: `CLAUDE.md`

- [ ] **Step 1: Create PWA manifest**

```json
{
  "name": "CertStudy",
  "short_name": "CertStudy",
  "description": "AI-powered certification study platform",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a0f14",
  "theme_color": "#00d4aa",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

- [ ] **Step 2: Copy service worker, create robots.txt and sitemap**

```bash
cp /home/merm/projects/selah/public/sw.js public/
```

Create `robots.txt` and `sitemap.xml` for study.codyjo.com.

- [ ] **Step 3: Create CLAUDE.md**

```markdown
# CertStudy

AI-powered certification study platform at study.codyjo.com.

## Tech Stack
Next.js 16, React 19, TypeScript, Tailwind CSS v4, AWS (S3, CloudFront, Lambda, DynamoDB, API Gateway v2), Terraform

## Commands
- `npm run dev` — dev server (localhost:3000)
- `npm run build` — production build (static export to out/)
- `npm run lint` — ESLint
- `npm run typecheck` — TypeScript check
- `npm test` — Vitest (run once)

## Deployment
- Static export to S3 (`certstudy-site`), served by CloudFront
- Domain: study.codyjo.com
- CD triggers: push to main → lint → typecheck → test → build → deploy
- Region: us-west-2

## localStorage Keys
- `cert_token` — JWT auth token
- `cert_user` — cached user object
- `cert_theme` — dark/light preference
- `cert_preferences` — study preferences JSON
- `cert_srs_cache` — flashcard SRS state cache
- `cert_last_seen_version` — version tracking for What's New
- `cert_enc_cache` — encryption key material
- `tutorial_completed` — onboarding flag

## Design Tokens
- Accent: #00d4aa (teal-green)
- Background: #0a0f14 (deep blue-black)
- Track colors: A+ #22c55e, AWS #6c5ce7, CKA #3498db, Puppet #e056a0
- Fonts: Inter + JetBrains Mono

## Testing
- Vitest + jsdom + Testing Library
- Run `npm test` before committing
- Regression suites in src/__tests__/regression/

## Architecture
- Static SPA (no SSR) — output: 'export'
- 3 Lambdas: API (CRUD), Tutor (Claude Sonnet), Planner (Claude Sonnet)
- DynamoDB single-table: certstudy-data
- Learning engine runs client-side (SRS, readiness, urgency)
```

- [ ] **Step 4: Commit**

```bash
git add public/ CLAUDE.md
git commit -m "feat: add PWA manifest, service worker, and project documentation"
```

---

## Chunk 6: Frontend Pages — Core Study Experience

### Task 21: Dashboard Page

**Files:**
- Create: `src/app/page.tsx`
- Create: `src/lib/study-context.tsx`
- Create: `src/lib/storage.ts`

- [ ] **Step 1: Create storage.ts with localStorage helpers**

Pattern from `/home/merm/projects/selah/src/lib/storage.ts`. Key functions: `getFlashcardStates()`, `setFlashcardStates()`, `getPlanProgress()`, `setPlanProgress()`, `getDailyActivity()`, `getStreak()`, etc.

- [ ] **Step 2: Create study-context.tsx**

React context providing:
- `activeTrack` — currently selected track
- `enrollments` — all track enrollments
- `domainProgress` — progress for active track
- `readiness` — calculated readiness score
- `urgency` — current urgency level
- `todaysPlan` — today's scheduled topics
- `dueCards` — flashcards due for review
- Actions: `setActiveTrack()`, `refreshProgress()`, `syncToServer()`

- [ ] **Step 3: Create Dashboard page**

Dashboard shows:
- Readiness gauge (large percentage)
- Days to exam countdown
- Today's plan (checklist of scheduled topics)
- Quick actions: "Start Studying", "Ask Tutor"
- Streak indicator
- Active track selector (if multiple enrolled)

- [ ] **Step 4: Verify page renders**

```bash
npm run dev
```

- [ ] **Step 5: Commit**

```bash
git add src/app/page.tsx src/lib/study-context.tsx src/lib/storage.ts
git commit -m "feat: add dashboard page with study context and today's plan"
```

### Task 22: Track Selection & Onboarding

**Files:**
- Create: `src/app/tracks/page.tsx`
- Create: `src/app/tracks/[id]/setup/page.tsx`
- Create: `src/components/TrackCard.tsx`
- Create: `src/components/BaselineWizard.tsx`

- [ ] **Step 1: Create TrackCard component**

Displays track info: name, exam code, domain count, progress bar, color accent, status badge (active/not started).

- [ ] **Step 2: Create tracks page**

Lists all 4 tracks as TrackCards. Active tracks show progress. Non-enrolled tracks show "Start" button leading to setup wizard.

- [ ] **Step 3: Create onboarding wizard (4 steps)**

Step 1: Set exam date (date picker)
Step 2: Choose baseline type (diagnostic / quick placement / self-assessment) — 3 radio cards
Step 3: Choose plan style (strict / flexible / hybrid) — 3 radio cards
Step 4: Run baseline → generate plan → redirect to dashboard

- [ ] **Step 4: Create BaselineWizard component**

Handles the 3 baseline modes:
- Diagnostic: Full quiz using questions from `{track}-diagnostic.ts`
- Quick Placement: Short adaptive quiz per domain
- Self-Assessment: Confidence slider per domain + AI verification questions

- [ ] **Step 5: Commit**

```bash
git add src/app/tracks/ src/components/TrackCard.tsx src/components/BaselineWizard.tsx
git commit -m "feat: add track selection and onboarding wizard with 3 baseline modes"
```

### Task 23: Flashcard Review Page

**Files:**
- Create: `src/app/flashcards/page.tsx`
- Create: `src/components/FlashcardCard.tsx`

- [ ] **Step 1: Create FlashcardCard component**

Card with flip animation (reference TNBM's TarotCard.tsx for flip pattern):
- Front: question text, track color indicator, domain label
- Back: answer text
- SRS rating buttons: Again (red), Hard (amber), Good (green), Easy (purple) with interval preview

- [ ] **Step 2: Create flashcards page**

- Shows due card count per track
- Track filter toggle (all / specific track)
- Card display with flip interaction
- After rating, advances to next card
- Progress indicator: "Card 7 of 15 due today"
- Summary screen when all cards reviewed

- [ ] **Step 3: Wire SRS engine**

On each rating:
1. Call `calculateNextReview()` from srs-engine
2. Update local FlashcardState
3. Sync to DynamoDB via `api.updateFlashcardState()`
4. Update domain progress (flashcardMastery)
5. Check knowledge transfer for cross-track boosts

- [ ] **Step 4: Commit**

```bash
git add src/app/flashcards/ src/components/FlashcardCard.tsx
git commit -m "feat: add spaced repetition flashcard review page"
```

### Task 24: Guided Lesson Page

**Files:**
- Create: `src/app/study/[track]/[domain]/page.tsx`

- [ ] **Step 1: Create lesson page**

- Load lesson content from static data based on track + domain route params
- Render markdown body via `<Markdown />` component
- Show key concepts as highlighted cards
- Show exam tips in a callout box
- "Ask Tutor About This" button → navigates to `/tutor` pre-scoped to this domain
- "Mark Complete" button → saves lesson progress
- "Next Lesson" navigation

- [ ] **Step 2: Wire lesson completion**

On mark complete:
1. Call `api.markLessonComplete(trackId, lessonId, timeSpent)`
2. Update domain progress (lessonsCompleted)
3. Update plan day (completedTopics)

- [ ] **Step 3: Commit**

```bash
git add src/app/study/
git commit -m "feat: add guided lesson page with markdown rendering and completion tracking"
```

### Task 25: Practice Quiz Page

**Files:**
- Create: `src/app/quiz/[track]/page.tsx`
- Create: `src/components/QuizQuestion.tsx`

- [ ] **Step 1: Create QuizQuestion component**

- Question text
- 4 answer options (A/B/C/D) as selectable cards
- After selection: show correct/incorrect with explanation
- Timer (optional, for baseline diagnostic)

- [ ] **Step 2: Create quiz page**

- Domain selector (which domain to quiz on)
- Question count selector (5/10/20)
- Quiz flow: question → answer → explanation → next
- Score summary at end with per-domain breakdown
- "Review Wrong Answers" option
- Type indicator: baseline / practice / review

- [ ] **Step 3: Wire quiz results**

On quiz complete:
1. Save via `api.saveQuizResult(result)`
2. Update domain progress (quizScore)
3. Generate flashcards for missed questions (if connected to tutor)
4. Update plan day (completedTopics)

- [ ] **Step 4: Commit**

```bash
git add src/app/quiz/ src/components/QuizQuestion.tsx
git commit -m "feat: add practice quiz page with scoring and result tracking"
```

### Task 26: AI Tutor Chat Page

**Files:**
- Create: `src/app/tutor/page.tsx`
- Create: `src/components/TutorChat.tsx`

- [ ] **Step 1: Create TutorChat component**

Chat interface (reference TNBM's ReadingChat.tsx for pattern):
- Message bubbles (user = right/purple, tutor = left/teal)
- Text input with send button
- Mode indicator (Teach/Quiz/Socratic/Assess)
- Typing indicator while waiting for AI response
- Domain context display at top

- [ ] **Step 2: Create tutor page**

- Landing state: track/domain picker grid
- Active state: TutorChat scoped to selected track + domain
- Can also be launched pre-scoped from lesson pages via query params
- Conversation persists within session (stored in TutorSession)
- Assessment results feed back to domain progress

- [ ] **Step 3: Wire tutor API**

On send message:
1. Call `api.sendTutorMessage(trackId, domainId, mode, messages, context)`
2. Display streaming response (or wait for full response)
3. If assessment returned, update domain progress (aiConfidence)
4. Save session via API

- [ ] **Step 4: Commit**

```bash
git add src/app/tutor/ src/components/TutorChat.tsx
git commit -m "feat: add AI tutor chat page with 4 modes and assessment"
```

---

## Chunk 7: Progress, Plan, Share & Polish

### Task 27: Progress & Readiness Page

**Files:**
- Create: `src/app/progress/[track]/page.tsx`
- Create: `src/components/ReadinessGauge.tsx`
- Create: `src/components/DomainProgressBar.tsx`
- Create: `src/components/OverlapMap.tsx`

- [ ] **Step 1: Create ReadinessGauge component**

Large circular gauge showing overall readiness percentage. Color based on score (red < 40, yellow 40-69, green >= 70). Exam date countdown below.

- [ ] **Step 2: Create DomainProgressBar component**

For each domain:
- Domain name + exam weight
- Progress bar (colored by score threshold)
- Overlap tags (from knowledge-map.ts) as colored pills
- Transfer indicators ("↑X% from A+") when applicable
- Click to expand: quiz score, flashcard mastery, AI confidence breakdown

- [ ] **Step 3: Create OverlapMap component**

Knowledge overlap visualization:
- 6 knowledge group cards
- Each shows which domains from which exams participate
- Motivational callout text
- Color-coded by group

- [ ] **Step 4: Create progress page**

Assembles: ReadinessGauge + all DomainProgressBars + OverlapMap. Loads domain progress from study context. Shows urgency indicator. Links to study plan.

- [ ] **Step 5: Commit**

```bash
git add src/app/progress/ src/components/ReadinessGauge.tsx src/components/DomainProgressBar.tsx src/components/OverlapMap.tsx
git commit -m "feat: add progress page with readiness gauge, domain breakdown, and overlap map"
```

### Task 28: Study Plan Calendar Page

**Files:**
- Create: `src/app/plan/[track]/page.tsx`
- Create: `src/components/StudyPlanCalendar.tsx`

- [ ] **Step 1: Create StudyPlanCalendar component**

Calendar grid (monthly view):
- Each day cell shows status: completed (green ✓), partial (yellow ½), missed (red ✗), upcoming (gray), today (accent highlight)
- Clicking a day shows that day's scheduled topics
- Urgency banner at top if not on-track

- [ ] **Step 2: Create plan page**

- Calendar view
- Selected day detail panel (scheduled topics, actual completion)
- Plan style indicator
- "Rebalance Plan" button (calls planner Lambda when urgency warrants it)
- Days to exam countdown

- [ ] **Step 3: Commit**

```bash
git add src/app/plan/ src/components/StudyPlanCalendar.tsx
git commit -m "feat: add study plan calendar page with day-level detail"
```

### Task 29: Shared Progress Page

**Files:**
- Create: `src/app/shared/[token]/page.tsx`

- [ ] **Step 1: Create shared progress page (no auth required)**

Public read-only view:
- User name + track name
- Exam date + days remaining
- Overall readiness percentage
- Streak, total hours studied, cards reviewed
- CTA: "Study at study.codyjo.com"
- No auth guard — fetches via `api.getSharedProgress(token)`

- [ ] **Step 2: Commit**

```bash
git add src/app/shared/
git commit -m "feat: add public shared progress page"
```

### Task 30: Remaining Track Data (AWS CCP, CKA, Puppet 8)

**Files:**
- Create: `src/data/aws-ccp-*.ts` (5 files)
- Create: `src/data/cka-*.ts` (5 files)
- Create: `src/data/puppet8-*.ts` (5 files)

- [ ] **Step 1: Create AWS Cloud Practitioner seed data**

4 domains: Cloud Concepts (24%), Security & Compliance (30%), Cloud Technology & Services (34%), Billing/Pricing/Support (12%).
Seed: 5 questions + 5 flashcards + 3 diagnostic questions + 1 lesson per domain.

- [ ] **Step 2: Create CKA seed data**

5 domains: Cluster Architecture (25%), Workloads & Scheduling (15%), Services & Networking (20%), Storage (10%), Troubleshooting (30%).
Seed: 5 questions + 5 flashcards + 3 diagnostic questions + 1 lesson per domain.

- [ ] **Step 3: Create Puppet 8 seed data**

6 domains: Puppet Language & Resources (25%), Node Classification & Hiera (15%), Module Development (20%), Server Administration (15%), Orchestration & Bolt (15%), Testing & CI/CD (10%).
Seed: 5 questions + 5 flashcards + 3 diagnostic questions + 1 lesson per domain.

- [ ] **Step 4: Wire tracks.ts to load domains from objectives files**

Update `tracks.ts` to import and attach domains from each `{track}-objectives.ts` file.

- [ ] **Step 5: Commit**

```bash
git add src/data/
git commit -m "feat: add seed content for AWS CCP, CKA, and Puppet 8 tracks"
```

### Task 31: Integration Testing & Build Verification

**Files:**
- Create: `src/__tests__/regression/plausible.test.tsx`
- Create: `src/__tests__/regression/seo.test.ts`

- [ ] **Step 1: Add Plausible analytics to layout**

Reference Selah's Plausible integration. Add the script tag to `layout.tsx` with a new Plausible site ID for study.codyjo.com.

- [ ] **Step 2: Create regression tests**

Copy patterns from Selah's regression suite:
- Plausible script presence test
- SEO meta tags test (title, description, og tags)

- [ ] **Step 3: Run full test suite**

```bash
npm test
```

Expected: All tests pass.

- [ ] **Step 4: Run full build**

```bash
npm run build
```

Expected: Static export to `out/` with all pages generated.

- [ ] **Step 5: Run typecheck and lint**

```bash
npm run typecheck && npm run lint
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add src/__tests__/regression/ src/app/layout.tsx
git commit -m "feat: add regression tests and verify full build"
```

### Task 32: Initial Deployment

- [ ] **Step 1: Create GitHub repository**

```bash
cd /home/merm/projects/certstudy
gh repo create certstudy --private --source=. --push
```

- [ ] **Step 2: Terraform init and plan**

```bash
cd terraform
terraform init
terraform plan
```

Review the plan — should create all AWS resources.

- [ ] **Step 3: Terraform apply**

```bash
terraform apply
```

- [ ] **Step 4: Deploy static site**

Push to main to trigger CD, or manually sync:
```bash
aws s3 sync ../out/ s3://certstudy-site/ --delete
aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/*"
```

- [ ] **Step 5: Verify study.codyjo.com loads**

Open https://study.codyjo.com and verify:
- Login page renders
- Dark theme with teal accent
- Navigation works
- PWA installable

- [ ] **Step 6: Smoke test API**

```bash
curl -X POST https://<api-url>/api/auth/register -d '{"email":"test@test.com","password":"testpassword123","name":"Test"}' -H 'Content-Type: application/json'
```

- [ ] **Step 7: Commit any deployment fixes**

```bash
git add .
git commit -m "fix: deployment configuration adjustments"
```

---

## Summary

| Chunk | Tasks | Focus |
|-------|-------|-------|
| 1 | 1-5 | Project scaffolding, types, static data, test infra |
| 2 | 6-9 | Learning engine (SRS, readiness, urgency, knowledge transfer) |
| 3 | 10-13 | Auth system & UI shell (copied from Selah) |
| 4 | 14-17 | API client & 3 backend Lambdas |
| 5 | 18-20 | Terraform, CI/CD, PWA |
| 6 | 21-26 | Frontend pages (dashboard, tracks, flashcards, lessons, quiz, tutor) |
| 7 | 27-32 | Progress page, plan calendar, shared view, remaining tracks, deploy |

**Total:** 32 tasks across 7 chunks. Chunks 2-3 can run in parallel (learning engine has no dependency on auth copying). Chunks 4-5 can run in parallel (Lambdas and Terraform are independent). Chunk 6 depends on chunks 1-3. Chunk 7 depends on everything.

**Parallelization opportunities for subagent-driven development:**
- Tasks 6-9 (learning engine) || Tasks 10-13 (auth/UI copy) — fully independent
- Tasks 14-17 (Lambdas) || Tasks 18-20 (Terraform/CI/CD) — fully independent
- Tasks 21-26 (pages) can partially parallelize — each page is mostly independent after study-context exists
- Task 30 (remaining track data) can run in parallel with any page work
