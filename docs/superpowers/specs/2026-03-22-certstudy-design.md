# CertStudy — Certification Study Platform Design Spec

**App:** CertStudy
**URL:** study.codyjo.com
**Date:** 2026-03-22
**Status:** Approved design, pending implementation

## Overview

CertStudy is an AI-powered certification study platform that adapts to how users learn. It combines spaced repetition flashcards, guided lessons, practice quizzes, and an AI tutor into a unified study experience with adaptive planning tied to exam dates.

The app launches with 4 certification tracks: CompTIA A+, AWS Cloud Practitioner, CKA (Certified Kubernetes Administrator), and Puppet 8. Tracks share a cross-exam knowledge graph so progress in one accelerates related domains in others.

Built on the same foundation as Selah and thenewbeautifulme — approximately 70% of infrastructure, auth, UI shell, and CI/CD is copied from those apps. The learning engine, AI tutor, and content system are purpose-built.

## Approach

**New app, cherry-pick what you need.** Start a fresh Next.js 16 project. Copy specific files from Selah/TNBM (auth, crypto, Terraform, CI/CD, UI shell). Build the learning engine and study features from scratch.

This mirrors how Selah was built from TNBM — proven pattern.

## Architecture

### Three-Layer System

**Client (SPA):**
- Next.js 16, React 19, TypeScript, Tailwind CSS v4
- Static export to S3 (no SSR)
- Learning engine runs client-side: spaced repetition scheduler, session manager, readiness calculator
- Context-based state: AuthContext, ThemeContext, ToastProvider, StudyContext
- Copied from Selah/TNBM: auth, encryption, navigation, toast, settings, PWA, onboarding

**API Layer:**
- API Gateway v2 (HTTP) with CORS
- Lambda: API (CRUD) — Node 20, ARM64, 256MB, 10s timeout. Auth, users, progress, tracks, flashcard state, quiz results, plans, tutor sessions
- Lambda: AI Tutor — Node 20, ARM64, 256MB, 30s timeout. Claude Sonnet for teaching, quizzing, Socratic dialogue, assessment, content generation
- Lambda: Planner — Node 20, ARM64, 256MB, 30s timeout. Claude Sonnet for study plan generation, rebalancing, and triage

**Data Layer:**
- DynamoDB single-table (`certstudy-data`), on-demand billing
- Secrets Manager: JWT secret, Anthropic API key
- S3: `certstudy-site` (static), `admin-certstudy-site` (dashboards)

### Key Design Decisions

- **Learning engine client-side:** Spaced repetition algorithm, session scheduling, and readiness calculations run in the browser. Keeps Lambda costs low and makes the app feel instant. Progress syncs to DynamoDB for backup and cross-device access.
- **AI server-side only:** Tutor conversations, content generation, and study plan creation go through Lambda → Claude. Keeps API key secure, allows rate limiting per user.
- **Separate Planner Lambda:** Study plan generation needs more context (all progress data, exam objectives, time remaining) and may take longer than a quick tutor response.

## Data Model

### Static Data (src/data/)

Curated seed content lives in TypeScript files — free to serve, fast to load, git-versioned:

| File | Contents |
|------|----------|
| `tracks.ts` | Track definitions (A+, AWS CCP, CKA, Puppet 8) — exam code, domains, weights, passing score, total questions |
| `aplus-objectives.ts` | CompTIA A+ domains and objectives with exam weights |
| `aws-ccp-objectives.ts` | AWS Cloud Practitioner domains and objectives |
| `cka-objectives.ts` | CKA domains and objectives |
| `puppet8-objectives.ts` | Puppet 8 domains and objectives |
| `{track}-diagnostic.ts` | Baseline diagnostic assessment bank (separate from practice questions to avoid repetition) |
| `{track}-questions.ts` | Curated seed question bank per domain (~50-100 per domain per track) |
| `{track}-flashcards.ts` | Curated flashcard deck per domain |
| `{track}-lessons.ts` | Guided lesson content per objective. Each lesson is structured as: title, objective reference, markdown body (supports headings, bold, code blocks, lists), key concepts array, and optional exam tips. Rendered via a Markdown component (same pattern as TNBM's interpretation renderer). |
| `knowledge-map.ts` | Cross-track concept graph mapping shared knowledge between exams |

### DynamoDB Single Table: `certstudy-data`

On-demand billing, PK/SK single-table design (same pattern as Selah/TNBM):

| Entity | PK | SK | Key Attributes |
|--------|-----|-----|----------------|
| User | `USER#{id}` | `PROFILE` | email, name, preferences, encryptionKeys |
| Track Enrollment | `USER#{id}` | `TRACK#{trackId}` | examDate, baselineType, planStyle, startedAt, status |
| Domain Progress | `USER#{id}` | `PROGRESS#{trackId}#DOM#{domainId}` | quizScore, flashcardMastery, aiConfidence, lessonsCompleted |
| Study Plan | `USER#{id}` | `PLAN#{trackId}` | activePlan JSON, urgencyLevel, lastRebalanced |
| Plan Day | `USER#{id}` | `PLANDAY#{trackId}#{date}` | scheduledTopics[], completedTopics[], minutesPlanned, minutesActual. A topic is "completed" when: lesson read to end, OR quiz taken (any score), OR all due flashcards for that domain reviewed. Multiple activity types per topic — any one satisfies completion. |
| Flashcard State | `USER#{id}` | `SRS#{cardId}` | ease, interval, nextReview, repetitions, source (curated/ai) |
| Quiz Result | `USER#{id}` | `QUIZ#{quizId}` | trackId, domainId, score, answers[], timestamp, type (baseline/practice/review) |
| Lesson Progress | `USER#{id}` | `LESSON#{trackId}#{lessonId}` | completed, completedAt, timeSpent |
| Tutor Session | `USER#{id}` | `TUTOR#{sessionId}` | trackId, domainId, messages[], aiAssessment, timestamp |
| Daily Activity | `USER#{id}` | `DAILY#{date}` | minutesStudied, cardsReviewed, quizzesTaken, lessonsCompleted |
| Streak | `USER#{id}` | `STREAK` | current, longest, lastDate |
| AI-Generated Card | `USER#{id}` | `AIGEN#CARD#{cardId}` | trackId, domainId, front, back, difficulty |
| AI-Generated Question | `USER#{id}` | `AIGEN#Q#{questionId}` | trackId, domainId, question, options, answer, explanation |
| Shared Progress | `SHARE#{token}` | `PROGRESS` | userId, trackId, expiresAt (30 days, renewable). Token is a random UUID. User can revoke from Settings. |
| Rate Limit | `RATELIMIT#{key}` | `COUNT` | count, expiresAt (TTL) |

**GSI1:** `EMAIL#{email}` → `PROFILE` (login lookup)

### Design Notes

- **Flashcard SRS state is per-user-per-card.** Curated card content lives in static files. DynamoDB only stores the user's review state (ease factor, interval, next review date). Adding new curated cards is just a code deploy.
- **Card ID namespace:** Curated cards use deterministic IDs from static data (e.g., `aplus-net-001`). AI-generated cards use UUID prefixed with `ai-` (e.g., `ai-550e8400...`). SRS state for both uses `SRS#{cardId}` — no collision because namespaces don't overlap. The `source` field on the SRS entity indicates whether the card definition is in static data or in `AIGEN#CARD#`.
- **AI-generated content gets its own prefix** (`AIGEN#`). Separates it from curated content, easy to query or clean up.
- **Domain Progress is the rollup entity.** Aggregates quiz scores, flashcard mastery, and AI confidence into a per-domain readiness picture. Updated after each study activity.
- **Cross-track knowledge transfer** works through `knowledge-map.ts`. When a user masters a concept in one track, the app applies a transfer rate to the linked domain in other enrolled tracks.

## Learning Engine

All learning engine logic runs client-side for speed and cost efficiency.

### Spaced Repetition (SM-2 Algorithm)

After each flashcard review, user rates: Again (0) | Hard (1) | Good (2) | Easy (3).

```
ease_factor = max(1.3, ease + (0.1 - (3 - rating) * (0.08 + (3 - rating) * 0.02)))

interval:
  - First correct:  1 day
  - Second correct: 6 days
  - Subsequent:     previous_interval × ease_factor
  - "Again":        reset to 1 day, ease drops

Cards due for review = nextReview <= today
```

Each card's SRS state syncs to DynamoDB (`SRS#{cardId}`) for cross-device persistence. Scheduling math runs entirely in-browser.

### Baseline Assessment

Users choose their assessment style during track onboarding:

| Style | How It Works | Output |
|-------|-------------|--------|
| Comprehensive Diagnostic | 50-100 questions across all domains, weighted by exam weight. Timed like the real exam. Draws from a dedicated `{track}-diagnostic.ts` assessment bank (separate from practice quiz pool to avoid question repetition). | Full domain-by-domain score map |
| Quick Placement | 5-10 questions per domain, unlocked progressively. Adaptive difficulty. | Per-domain score, built up over time |
| Self-Assessment + Verification | User rates confidence (1-5) per domain. Tutor Lambda (in quiz mode) generates 3-5 targeted questions per domain to verify, using domain objectives as context. Flags discrepancies between self-rating and quiz performance. | Confidence map + verified scores |

All three produce the same output: a domain proficiency map (0-100 per domain) that seeds the study plan.

### Study Plan Generation (Planner Lambda)

After baseline, the Planner Lambda receives domain proficiency scores, exam date, domain weights, and chosen plan style (strict sequential / flexible recommendations / hybrid).

It generates a day-by-day plan that:
- Front-loads weak + high-weight domains
- Spaces review sessions using the forgetting curve
- Mixes study modes (lessons for new material, quizzes for testing, flashcards for retention, tutor for deep understanding)
- Accounts for cross-track overlap

Plan styles:
- **Strict sequential:** Day-by-day plan, specific topics each day
- **Flexible recommendations:** Suggests what to study next based on weak areas and time remaining, user chooses freely
- **Hybrid:** Recommended daily plan that can be overridden; auto-adjusts when deviations occur

### Progressive Urgency

Pacing is checked client-side each time the user opens the app (no server-side scheduler needed). The client compares current progress against the plan and displays the appropriate urgency level. If a rebalance is triggered, the client calls the Planner Lambda at that point.

| State | Trigger | Response |
|-------|---------|----------|
| On Track | ≥ 80% weekly completion | Green indicator. No changes. |
| Gentle Nudge | Missed 1-2 days or < 80% weekly | Yellow indicator. Suggested catch-up plan. No structural changes. |
| Auto-Rebalance | Missed 3+ days or < 60% weekly for 2 weeks | Orange indicator. Planner Lambda re-generates remaining schedule. Daily load may increase. |
| Smart Triage | < 2 weeks to exam and < 70% covered | Red indicator. AI prioritizes highest exam-weight × lowest-mastery domains. Deprioritizes already-passing domains. |

### Readiness Calculation

Three signals combine into overall exam readiness:

```
readiness = (quiz_score × 0.4) + (srs_mastery × 0.3) + (ai_confidence × 0.3)

quiz_score:    Weighted average across domains (by exam weight), most recent practice quiz per domain (0-100)
srs_mastery:   % of flashcards with interval ≥ 21 days (mature cards), weighted by domain
ai_confidence: AI tutor's assessment per domain (0-100), updated after each tutor session
```

**Exam Ready threshold:** readiness ≥ 85% across all domains, with no single domain below 70%.

### Cross-Track Knowledge Transfer

`knowledge-map.ts` defines 6 concept groups shared across tracks:

| Concept Group | Tracks | Transfer Rate |
|---------------|--------|--------------|
| Networking | A+, AWS, CKA | 70% |
| Security | A+, AWS | 50% |
| Cloud & Virtualization | A+, AWS, CKA | 60% |
| Troubleshooting | A+, CKA | 40% |
| Infrastructure Automation | CKA, Puppet | 50% |
| Server Administration | CKA, Puppet | 45% |

When domain progress updates in one track, the app applies `transferRate × mastery` to linked domains in other enrolled tracks. The UI shows this as "↑X% from [track]" indicators, and the Knowledge Overlap Map highlights shared groups to encourage cross-track study.

## AI Tutor System

Dedicated Lambda (`certstudy-tutor`) using Claude Sonnet.

### Tutor Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Teach | User opens a lesson topic or asks "explain X" | Explains concept with examples, checks understanding with follow-up |
| Quiz | Practice quiz or scheduled assessment | Asks questions, explains right/wrong, adapts difficulty within session |
| Socratic | "I don't understand X" or tutor detects weak reasoning | Asks guiding questions instead of giving answers |
| Assess | After 3+ interactions on a domain | Silently evaluates understanding depth, returns structured JSON assessment alongside response |

### Conversation Context

Each tutor session is scoped to a track + domain. The Lambda receives:
- Current mode
- Track and domain IDs
- Conversation history
- Domain objectives (from static data)
- Current progress (quiz score, SRS maturity, lessons completed)
- Recent mistakes (last 5 wrong answers in this domain)

System prompt includes exam objectives, weak spots, mode instructions, and a mandate to assess understanding depth (not just recall).

### AI Assessment Output

In assess mode, the tutor returns structured feedback alongside the conversational response:

```json
{
  "response": "...",
  "assessment": {
    "domainId": "networking",
    "confidence": 78,
    "strengths": ["TCP/IP model layers", "subnet calculation"],
    "weaknesses": ["DNS resolution process", "VLAN concepts"],
    "misconceptions": ["Confuses hub with switch functionality"],
    "recommendedFocus": ["DNS deep dive", "Layer 2 switching"]
  }
}
```

This feeds back into Domain Progress (aiConfidence), Study Plan (focus areas), and Flashcard generation (targeting identified weaknesses).

### Content Generation

Content generation is handled by the Tutor Lambda via `POST /api/tutor/generate` (distinct from chat at `POST /api/tutor/chat`). The request body includes a `type` field (`question` or `flashcard`) to differentiate.

| What | When | Storage |
|------|------|---------|
| Practice questions | Curated bank exhausted or user wants more | `AIGEN#Q#{id}` |
| Flashcards | After identifying weak concepts in tutor sessions | `AIGEN#CARD#{id}` |
| Explanations | User gets a curated question wrong | Inline (not stored) |

### Rate Limits

All rate limits are enforced in the respective Lambda handler using DynamoDB-based counters (same pattern as Selah/TNBM).

| Limit | Threshold | Lambda | Path |
|-------|-----------|--------|------|
| Tutor chat | 30/user/hour | certstudy-tutor | `/api/tutor/chat` |
| Content generation | 20/user/hour | certstudy-tutor | `/api/tutor/generate` |
| Plan generation | 3/user/day | certstudy-planner | `/api/plan/*` |

## Frontend

### Pages & Routes

**New (purpose-built):**

| Route | Purpose |
|-------|---------|
| `/` | Dashboard — today's plan, readiness gauge, days to exam, quick actions |
| `/tracks` | Track selection & management — all 4 tracks with progress, add new |
| `/tracks/[id]/setup` | Onboarding wizard — 4 steps: exam date → baseline type → plan style → generate plan |
| `/study/[track]/[domain]` | Guided lessons — domain/objective content with "Ask Tutor" integration |
| `/flashcards` | Spaced repetition review — shows all due cards across enrolled tracks, grouped by track with track color indicators. SM-2 with Again/Hard/Good/Easy, interval previews. User can filter to a single track if desired. |
| `/quiz/[track]` | Practice quizzes + baseline assessments — timed, multiple choice, immediate feedback |
| `/tutor` | AI tutor chat — landing page shows track/domain picker. Selecting a domain opens the chat scoped to that track + domain. Can also be launched directly from a lesson page via "Ask Tutor" button (pre-scoped). |
| `/progress/[track]` | Readiness dashboard — overall %, per-domain bars (color-coded), overlap tags |
| `/plan/[track]` | Study plan calendar — daily view with completed/partial/missed/upcoming |
| `/shared/[token]` | Public progress view — read-only, no auth, stats + readiness |

**Copied from Selah/TNBM:**

| Route | Purpose |
|-------|---------|
| `/login` | Login / Register / Forgot password |
| `/reset-password` | Password reset flow |
| `/settings` | Profile, security, preferences, export, delete. Includes "Share Progress" section: generate a share link (creates `SHARE#{uuid}` via `POST /api/share`), copy link, toggle on/off, revoke existing link. |
| `/updates` | Version history (What's New) |
| `/privacy` | Privacy policy |
| `/accessibility` | WCAG compliance statement |

### Domain Breakdown View

Each track's progress page shows all domains with:
- Domain name and exam weight percentage
- Progress bar (green ≥ 70%, yellow 40-69%, red < 40%)
- Overlap tags — color-coded pills showing which knowledge group the domain belongs to and which other exams share it
- Transfer indicators — "↑X% from [track]" showing knowledge transfer gains

### Knowledge Overlap Map

Bottom of the progress page shows 6 knowledge groups with:
- Which specific domains from each exam participate
- Brief description of the shared concepts
- Motivational callout ("Your A+ networking progress gives you a head start — every concept you master counts triple")

### Navigation

Fixed top bar with:
- App logo (⚡ CertStudy)
- Main links: Dashboard, Study, Flashcards, Tutor, Progress
- Status pills: streak count, active track + readiness %
- Settings gear

## Branding & Design

Same design system as Selah/TNBM, different personality:

| Token | Value |
|-------|-------|
| Accent | `#00d4aa` (teal-green) |
| Background | `#0a0f14` (deep blue-black) |
| Card BG | `#0d1117` |
| Surface | `#1a2332` |
| Amber (urgency/streaks) | `#f39c12` |
| Error | `#e74c3c` |
| Track colors | A+: `#22c55e` (green — distinct from teal accent), AWS: `#6c5ce7`, CKA: `#3498db`, Puppet: `#e056a0` |
| Fonts | Inter (sans) + JetBrains Mono (mono) |
| Logo feel | Lightning bolt / circuit-board aesthetic |

Dark/light mode toggle via CSS variables (same mechanism as Selah/TNBM).

## What Gets Copied vs Built New

### Copied (~70%)

| Layer | Source Files | Adaptation |
|-------|-------------|------------|
| Auth system | auth-context.tsx, LoginPageClient, journal-crypto.ts, JWT Lambda | Rename localStorage keys, swap branding |
| Terraform | All 15 .tf files | Change resource names, domain, bucket names |
| CI/CD | ci.yml, cd.yml, preview.yml | Change project references |
| UI shell | Navigation, Toast, Skeleton, ErrorBoundary, Settings | New nav links, new accent color |
| Onboarding | WhatsNewModal, TutorialOverlay, OnboardingManager | New tutorial steps |
| PWA | manifest.json, sw.js, PwaInstallPrompt | New app name/icons |
| Testing | vitest.config.ts, setup.ts, regression patterns | New test content |
| Monitoring | CloudWatch alarms, Plausible | New dashboard IDs |
| Encryption | E2E encryption system | Copied but dormant at launch. No sensitive user-generated content equivalent to journals. Can be activated later for tutor conversation history if users request privacy for their study chats. |

### Built New (~30%)

| Feature | Complexity |
|---------|-----------|
| Learning engine (SM-2, scheduler, readiness calc) | High |
| AI Tutor Lambda (4 modes, assessment, content gen) | High |
| Planner Lambda (plan generation, rebalance, triage) | Medium |
| Track data model (4 tracks × objectives, questions, flashcards, lessons) | Medium |
| Curated seed content (question banks, flashcard decks, lesson content) | Medium |
| Baseline assessments (3 modes) | Medium |
| Progress/readiness views (domain breakdown, overlap map) | Medium |
| Cross-track knowledge map | Low |
| Shared progress | Low |

## Track Extensibility

Adding a new certification track requires:

1. Five new data files: `src/data/{track}-objectives.ts`, `{track}-diagnostic.ts`, `{track}-questions.ts`, `{track}-flashcards.ts`, `{track}-lessons.ts`
2. One entry in `tracks.ts`: track metadata (name, exam code, passing score, domain weights)
3. Optional entries in `knowledge-map.ts`: if concepts overlap with existing tracks

No code changes needed. The UI, learning engine, AI tutor, and planner all work off the track data generically.

## Infrastructure

| Service | Resource | Notes |
|---------|----------|-------|
| S3 | `certstudy-site` | Static site hosting |
| S3 | `admin-certstudy-site` | Back-office dashboards |
| CloudFront | Distribution | CDN + CSP headers + caching |
| Route53 | study.codyjo.com | A + AAAA records to CloudFront |
| ACM | SSL certificate | Auto-renewed |
| DynamoDB | `certstudy-data` | On-demand, single-table, GSI1 for email |
| Lambda | `certstudy-api` | CRUD, 10s timeout |
| Lambda | `certstudy-tutor` | AI tutor, 30s timeout |
| Lambda | `certstudy-planner` | Plan generation, 30s timeout |
| API Gateway | HTTP API v2 | Path-based routing: `POST /api/tutor/*` → tutor Lambda, `POST /api/plan/*` → planner Lambda, all other `/api/*` → api Lambda. CORS enabled. |
| Secrets Manager | JWT secret, Anthropic key | Cached after cold start |
| CloudWatch | Alarms | Lambda errors, DynamoDB throttling, 5xx |
| GitHub Actions | CI/CD | OIDC to AWS, lint → typecheck → test → deploy |
| Plausible | Analytics | Privacy-first, cookieless |

## User Flows

### New User Onboarding
1. Register (email + password)
2. Choose first track (e.g., CompTIA A+)
3. Set exam date
4. Choose baseline type (diagnostic / quick placement / self-assessment)
5. Complete baseline
6. Choose plan style (strict / flexible / hybrid)
7. Plan generated → redirected to dashboard with today's first tasks

### Daily Study Session
1. Open dashboard → see today's plan
2. Complete flashcard reviews (due cards from spaced repetition)
3. Work through scheduled lesson
4. Take practice quiz on scheduled domain
5. Optionally chat with AI tutor about weak areas
6. Progress auto-updates across all views

### Cross-Track Knowledge Transfer
1. User masters "networking fundamentals" in A+ (score ≥ 85%)
2. App checks knowledge-map.ts → networking maps to AWS Cloud Technology and CKA Services & Networking
3. Transfer rate applied: AWS gets 70% × mastery, CKA gets 70% × mastery
4. AWS and CKA progress views show "↑X% from A+" next to affected domains
5. Study plan for AWS/CKA adjusts — less time allocated to already-transferred concepts

### Falling Behind
1. System detects < 60% weekly completion for 2 consecutive weeks
2. Status changes to "Auto-Rebalance" (orange indicator)
3. Planner Lambda called with current progress + remaining time
4. New plan generated redistributing remaining material
5. User notified: "Your plan has been adjusted — daily study time increased by ~15 minutes to stay on track for your exam date"
6. If < 2 weeks to exam and < 70% covered → Smart Triage mode activates
