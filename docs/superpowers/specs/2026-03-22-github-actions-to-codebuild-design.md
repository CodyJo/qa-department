# GitHub Actions → AWS CodeBuild Migration

**Date:** 2026-03-22
**Status:** Approved
**Motivation:** GitHub Actions billing issue (credit card not updating). Migrate all CI/CD to AWS CodeBuild.

---

## Decisions

| Decision | Choice |
|----------|--------|
| Scope | CI + CD only (drop preview artifacts + nightly checks) |
| Trigger model | GitHub webhooks → CodeBuild |
| Auth model | One IAM role per project (least-privilege) |
| Old workflows | Delete (git history preserved) |
| Architecture | Shared Terraform module + per-project invocation |
| Module source | Git URL with version tag (`?ref=codebuild-module-v1`) |
| Path filters | Simplify — trigger on any push to main (no path filtering in CodeBuild webhooks) |
| Concurrency | CodeBuild CD projects set to `concurrent_build_limit = 1` |

## Projects In Scope

| # | Project | Runtime | Region | CD Deploys | Complexity |
|---|---------|---------|--------|------------|------------|
| 1 | back-office | Python 3.12 | us-west-2 | S3 sync, CF invalidation (E372ZR95FXKVT5) | Low |
| 2 | codyjo.com | Node.js 22 | us-west-2 | S3 (`www.codyjo.com`), CF (EF4U8A7W3OH5K) | Low |
| 3 | selah | Node.js 20 | us-west-2 | S3 (`bible-app-site`), 2 Lambdas (bible-app-interpret, bible-app-api), CF | Medium |
| 4 | portis-app | Node.js 20 | us-west-2 | S3 (`etheos-app-site`), 2 Lambdas via CD (etheos-app-interpret, etheos-app-api), CF | Medium |
| 5 | fuel | Node.js 20 | us-east-1 | S3 (`fuel-site`), 2 Lambdas (fuel-api, fuel-ai), CF | Medium |
| 6 | certstudy | Node.js 20 | us-west-2 | S3 (`certstudy-site`), 3 Lambdas (certstudy-api, certstudy-tutor, certstudy-planner), CF | Medium |
| 7 | analogify | Python 3.12 | us-west-2 | S3 (`codyjo-com-photos-*`) HTML uploads, 5 Lambdas via CD (admin, auth_view, auth_download, maintenance, zip), CF (EW2SF2IXBOKE5) | High |
| 8 | auth-service | Node.js 20 | us-west-2 | 1 Lambda (auth-service-api), Terraform apply | High |
| 9 | thenewbeautifulme | Node.js 20 | us-west-2 | 2 S3 buckets, 4 Lambdas (interpret, api, analytics, og) via Terraform, 2 CF distributions, 6 smoke tests | High |

### Legacy Naming

- **selah**: repo is "selah" but AWS resources use legacy prefix `bible-app-` (S3: `bible-app-site`, Lambdas: `bible-app-interpret`, `bible-app-api`)
- **portis-app**: repo is "portis-app" but AWS resources use legacy prefix `etheos-app-` (S3: `etheos-app-site`, Lambdas: `etheos-app-interpret`, `etheos-app-api`)
- **portis-app** has 4 total Lambdas in Terraform (api, interpret, builder, scheduler) but CD only deploys 2 (api, interpret). Builder and scheduler are managed by Terraform apply only.
- **analogify** has 6 Lambdas in Terraform (auth_view, auth_download, admin, optimize, maintenance, zip) but CD deploys 5 (all except optimize, which is deployed separately via Terraform)

## Projects NOT In Scope

- pe-bootstrap (GCP, no GitHub Actions CI/CD)
- plausible-aws-ce (no CI/CD)
- docs (no CI/CD)
- bible-app (no CI/CD, archived into selah)

---

## Architecture

### Shared Terraform Module

**Location:** `/home/merm/projects/codyjo.com/terraform/modules/codebuild/`

This directory does not exist yet — it will be created as part of the first migration (back-office).

**Module source strategy:** Projects reference the module via git URL with a version tag:
```hcl
source = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"
```
This ensures module changes don't accidentally affect other projects until the tag is bumped. The codyjo.com project itself uses a relative path (`./modules/codebuild`) since it's in the same repo.

**Inputs:**

```hcl
variable "project_name" {
  description = "Project identifier, e.g. 'selah', 'fuel'"
  type        = string
}

variable "github_repo" {
  description = "GitHub repo in Owner/Repo format, e.g. 'CodyJo/selah'"
  type        = string
}

variable "github_branch" {
  description = "Branch to trigger CD on"
  type        = string
  default     = "main"
}

variable "build_image" {
  description = "CodeBuild Docker image"
  type        = string
  default     = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
}

variable "runtime" {
  description = "Primary runtime: nodejs20, nodejs22, python312"
  type        = string
}

variable "ci_buildspec" {
  description = "Path to CI buildspec file"
  type        = string
  default     = "buildspec-ci.yml"
}

variable "cd_buildspec" {
  description = "Path to CD buildspec file"
  type        = string
  default     = "buildspec-cd.yml"
}

variable "deploy_policy_arns" {
  description = "IAM policy ARNs granting deploy permissions"
  type        = list(string)
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "compute_type" {
  description = "CodeBuild compute type"
  type        = string
  default     = "BUILD_GENERAL1_SMALL"
}

variable "concurrent_build_limit" {
  description = "Max concurrent builds for CD project (prevents parallel deploys)"
  type        = number
  default     = 1
}

variable "environment_variables" {
  description = "Additional environment variables for builds"
  type = list(object({
    name  = string
    value = string
    type  = string # PLAINTEXT, PARAMETER_STORE, SECRETS_MANAGER
  }))
  default = []
}
```

**Resources created by module:**

1. `aws_codebuild_project.ci` — `{project_name}-ci`
   - Source: GitHub repo
   - Buildspec: `buildspec-ci.yml`
   - Webhook filter: `PULL_REQUEST_CREATED`, `PULL_REQUEST_UPDATED`, `PULL_REQUEST_REOPENED`

2. `aws_codebuild_project.cd` — `{project_name}-cd`
   - Source: GitHub repo
   - Buildspec: `buildspec-cd.yml`
   - Webhook filter: `PUSH` on `refs/heads/{github_branch}`
   - `concurrent_build_limit = var.concurrent_build_limit` (default 1, prevents parallel deploys)

3. `aws_iam_role.ci` — `{project_name}-codebuild-ci`
   - Permissions: CloudWatch Logs only

4. `aws_iam_role.cd` — `{project_name}-codebuild-cd`
   - Permissions: CloudWatch Logs + passed-in `deploy_policy_arns`

5. `aws_codebuild_webhook.ci` — PR trigger
6. `aws_codebuild_webhook.cd` — push-to-main trigger
7. `aws_cloudwatch_log_group.builds` — `/codebuild/{project_name}`

**GitHub connection (defined once in codyjo.com parent Terraform):**

```hcl
resource "aws_codebuild_source_credential" "github" {
  auth_type   = "PERSONAL_ACCESS_TOKEN"
  server_type = "GITHUB"
  token       = var.github_pat
}
```

**Fuel region workaround:** The `aws_codebuild_source_credential` is region-scoped. Since fuel deploys to us-east-1, a second source credential must be created in us-east-1. This is defined in fuel's own `terraform/codebuild.tf`:
```hcl
resource "aws_codebuild_source_credential" "github" {
  provider    = aws  # us-east-1 provider
  auth_type   = "PERSONAL_ACCESS_TOKEN"
  server_type = "GITHUB"
  token       = var.github_pat
}
```

The PAT needs `repo` and `admin:repo_hook` scopes. Stored in SSM Parameter Store at `/codebuild/github-pat`.

---

### Per-Project Files

Each project gets:

**Added:**
- `buildspec-ci.yml` — project-specific CI steps (see CI Steps table below)
- `buildspec-cd.yml` — build + deploy (S3, Lambda, CloudFront)
- `terraform/codebuild.tf` — module invocation

**Deleted (per project):**

| Project | Workflow Files Deleted |
|---------|----------------------|
| back-office | ci.yml, deploy.yml, preview.yml, nightly-backoffice.yml |
| codyjo.com | ci.yml, cd.yml, preview.yml, terraform-admin.yml, nightly-backoffice.yml |
| selah | ci.yml, cd.yml, preview.yml, nightly-backoffice.yml |
| portis-app | ci.yml, cd.yml, preview.yml, nightly-backoffice.yml |
| fuel | ci.yml, cd.yml |
| certstudy | ci.yml, cd.yml |
| analogify | ci.yml, cd.yml, preview.yml, nightly-backoffice.yml |
| auth-service | ci.yml, cd.yml |
| thenewbeautifulme | ci.yml, cd.yml, preview.yml, nightly-backoffice.yml |

**Deleted from Terraform:**
- GitHub OIDC deploy role resources from `terraform/cd.tf`
- **IMPORTANT:** analogify's `cd.tf` **creates** the OIDC provider (`resource "aws_iam_openid_connect_provider" "github"`), while other projects only reference it via `data` source. Deleting the OIDC provider from analogify will destroy it in AWS. The OIDC provider must be preserved until ALL projects have been migrated. Remove it only as a final cleanup step after all 9 projects are on CodeBuild.

**Example module invocation (selah):**

```hcl
module "codebuild" {
  source             = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"
  project_name       = "selah"
  github_repo        = "CodyJo/selah"
  runtime            = "nodejs20"
  deploy_policy_arns = [aws_iam_policy.deploy.arn]
  aws_region         = "us-west-2"
}
```

---

### Per-Project CI Steps

Each project's `buildspec-ci.yml` must match its current CI workflow:

| Project | CI Steps |
|---------|----------|
| back-office | `bash -n` (shell syntax), `python3 -m py_compile` (Python syntax), `ruff check`, `pytest tests/ --cov` |
| codyjo.com | `npm run check` (Astro), `npm run build`, `npm run verify:dist` |
| selah | `npm run lint`, `npm run typecheck`, `npm test`, `npm audit --audit-level=high`, `npm run build` |
| portis-app | `npm run lint`, `npm run typecheck`, `npm test`, `npm run test:coverage`, `npm run check:critical-coverage`, `npm audit --audit-level=high`, `npm run build` |
| fuel | `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` |
| certstudy | `npm run lint`, `npm run typecheck`, `npm test`, `npm audit --audit-level=high`, `npm run build` |
| analogify | `ruff check`, `pytest tests/`, `cd marketing && npm run check && npm test`, `terraform validate` (with stubs) |
| auth-service | `npm run lint`, `npm test` |
| thenewbeautifulme | `npm run lint`, `npm run typecheck`, `npm test`, `npm audit --audit-level=high`, `npm run build`, `cd useradmin && npm run build` |

### Per-Project Build-Time Environment Variables

| Project | Variable | Value | Needed In |
|---------|----------|-------|-----------|
| portis-app | `NEXT_PUBLIC_API_URL` | `https://cordivent.com` | CI + CD |
| portis-app | `NEXT_PUBLIC_SITE_URL` | `https://cordivent.com` | CI + CD |
| thenewbeautifulme | `NEXT_PUBLIC_API_URL` | `https://thenewbeautifulme.com` | CI + CD |
| analogify | `AWS_REGION` | `us-west-2` | CD |
| analogify | `PHOTOS_BUCKET` | `codyjo-com-photos-7fa5a7d0` | CD |
| analogify | `CF_DISTRIBUTION` | `EW2SF2IXBOKE5` | CD |

These are set as `PLAINTEXT` environment variables in the CodeBuild project configuration via the module's `environment_variables` input.

---

### Project-Specific Variations

**back-office (simplest):**
- Python 3.12 runtime
- CD runs: validate scripts → `make test` → `bash scripts/sync-dashboard.sh`
- No Lambda updates
- CloudFront invalidation uses hardcoded distribution E372ZR95FXKVT5

**codyjo.com:**
- Node.js 22 runtime
- Gets a **third** CodeBuild project: `codyjo-com-terraform` triggered on push to main
- Since CodeBuild webhooks don't support GitHub Actions-style path filters well, this project triggers on any push to main. The buildspec can check `git diff` to skip Terraform apply if no terraform files changed.
- Defined manually in `codebuild.tf` alongside the module call
- Uses relative module path (`./modules/codebuild`) since the module lives in this repo

**analogify:**
- Python 3.12 runtime
- Builds 5 Lambda zips deployed by CD: admin, auth_view, auth_download, maintenance, zip
- optimize Lambda (6th) is managed by Terraform only, not deployed by CD
- Uploads individual HTML files to S3 (not a built site directory)
- CI includes marketing sub-project checks (Astro build in `marketing/` dir)
- Runs live smoke tests post-deploy (`RUN_LIVE_SMOKE=1 pytest tests/smoke -m smoke`)
- CD also prunes stale `worktree-agent-*` git branches (preserve in buildspec)

**auth-service:**
- CD buildspec installs Terraform and runs `terraform apply`
- Secrets are in **AWS Secrets Manager** (not SSM Parameter Store) at existing paths:
  - `auth-service/jwt-secret`
  - `auth-service/resend-api-key`
  - `auth-service/admin-allowlist`
- These are passed as `TF_VAR_*` environment variables in CodeBuild using `type = "SECRETS_MANAGER"`
- No S3 or CloudFront — backend Lambda only

**thenewbeautifulme (most complex):**
- Builds 2 sites: main (out/) + admin (useradmin/out/)
- Deploys to 2 S3 buckets: `thenewbeautifulme-site`, `useradmin-thenewbeautifulme-site`
- Invalidates 2 CloudFront distributions (thenewbeautifulme.com, useradmin.thenewbeautifulme.com)
- CD installs Terraform and runs `terraform apply` targeting 7 resources: lambda_secrets, api_secrets, interpret, api, analytics, analytics_dynamodb, og
- Deploys 4 Lambdas: interpret, api, analytics, og
- Runs 6 smoke tests: home page, reading page, daily page, guest interpret API, admin dashboard, OG image generation

**fuel:**
- Same standard pattern but deploys to **us-east-1** (only project not in us-west-2)
- Needs its own `aws_codebuild_source_credential` in us-east-1 (see Fuel region workaround above)
- 2 Lambdas: fuel-api, fuel-ai

**certstudy:**
- Standard pattern but 3 Lambdas: certstudy-api, certstudy-tutor, certstudy-planner

---

### Secrets Management

| Current (GitHub) | New (AWS) | Service |
|-------------------|-----------|---------|
| `AWS_DEPLOY_ROLE_ARN` secret | Not needed — CodeBuild assumes IAM role natively | N/A |
| `JWT_SECRET` (auth-service) | `auth-service/jwt-secret` | Secrets Manager (existing) |
| `RESEND_API_KEY` (auth-service) | `auth-service/resend-api-key` | Secrets Manager (existing) |
| `admin-allowlist` (auth-service) | `auth-service/admin-allowlist` | Secrets Manager (existing) |
| GitHub PAT (new) | `/codebuild/github-pat` | SSM Parameter Store (new) |

Auth-service secrets already exist in Secrets Manager — no migration needed. CodeBuild references them directly with `type = "SECRETS_MANAGER"` in environment variable config.

---

## Migration Order

Simplest to most complex. Each project follows this process:

1. Write `buildspec-ci.yml` and `buildspec-cd.yml`
2. Add `terraform/codebuild.tf` calling the shared module
3. `terraform apply` to create CodeBuild projects + webhooks
4. Test: push a branch / open a PR → verify CI triggers and passes
5. Test: merge to main → verify CD triggers and deploys correctly
6. Delete `.github/workflows/` directory
7. Remove GitHub OIDC deploy **role** from Terraform (`cd.tf`) — but **NOT** the OIDC provider resource (see OIDC cleanup below)
8. `terraform apply` to destroy the old OIDC role in AWS
9. Update project CLAUDE.md (see below)
10. Commit all changes

**Order:**
1. back-office (also: create shared module in codyjo.com)
2. codyjo.com (also: create `aws_codebuild_source_credential`, tag module `codebuild-module-v1`)
3. selah
4. portis-app
5. fuel (also: create us-east-1 source credential)
6. certstudy
7. analogify
8. auth-service
9. thenewbeautifulme

The shared module is built during project #1 (back-office) and refined through #2-3.

### OIDC Provider Cleanup (Final Step)

After ALL 9 projects are migrated and confirmed working:
- Remove the `aws_iam_openid_connect_provider "github"` resource from analogify's Terraform (it's the only project that creates it; others reference it via `data`)
- Run `terraform apply` in analogify to destroy the OIDC provider
- This is safe only after no project uses GitHub Actions OIDC anymore

### Rollback Plan

If a CodeBuild migration fails for a project mid-migration:
- The old GitHub Actions workflow files still exist in git history
- `git checkout HEAD~1 -- .github/workflows/` restores them
- The OIDC deploy role is not removed until step 7 (after CodeBuild is confirmed working)
- If step 7 has already been run, re-add the OIDC role to `cd.tf` and `terraform apply`

The key safety net: steps 6-8 (delete workflows + remove OIDC role) only happen AFTER steps 4-5 confirm CodeBuild works.

---

## Documentation Updates

### CLAUDE.md Updates

Each project's `CLAUDE.md` must be updated to reflect the new CI/CD. Remove any references to GitHub Actions and replace with CodeBuild.

**Projects that need CLAUDE.md created (doesn't exist yet):**
- codyjo.com
- analogify (no CLAUDE.md exists at project root)
- auth-service

**All other projects:** Update existing CLAUDE.md.

**Remove from CLAUDE.md:**
- References to `.github/workflows/` files
- Instructions about GitHub Actions secrets
- References to GitHub OIDC roles
- Any "CI runs on PR" or "CD runs on push to main" text that mentions GitHub Actions

**Add to each project's CLAUDE.md:**

```markdown
## CI/CD — AWS CodeBuild

CI and CD run on AWS CodeBuild (not GitHub Actions).

- **CI** (`{project}-ci`): Triggers on pull requests. Runs lint, typecheck, test, build.
  - Config: `buildspec-ci.yml`
- **CD** (`{project}-cd`): Triggers on push to main. Builds and deploys to AWS.
  - Config: `buildspec-cd.yml`
- **IAM role**: `{project}-codebuild-cd` — scoped to this project's S3, Lambda, CloudFront only.
- **Infrastructure**: CodeBuild projects defined in `terraform/codebuild.tf` using shared module from `codyjo.com/terraform/modules/codebuild/`.
- **Webhook trigger**: GitHub push/PR events trigger CodeBuild via webhook (no GitHub Actions involved).
- **Logs**: CloudWatch `/codebuild/{project}`

To check build status: `aws codebuild list-builds-for-project --project-name {project}-cd --sort-order DESCENDING`
```

### Memory Update

Update the project memory at `/home/merm/.claude/projects/-home-merm-projects/memory/MEMORY.md` to replace:
```
- Uses GitHub Actions for CI/CD
```
with:
```
- Uses AWS CodeBuild for CI/CD (migrated from GitHub Actions 2026-03-22)
```

### README Updates

If any project has a README with CI/CD badges or GitHub Actions references, update those to reference CodeBuild or remove the badges.

---

## What We're NOT Doing

- Not moving repos off GitHub — it stays as the git remote
- Not migrating nightly checks or preview artifacts
- Not touching Terraform state backends
- Not modifying application code
- Not changing deploy targets (same S3, Lambda, CloudFront)
- Not touching pe-bootstrap, plausible-aws-ce, docs, or bible-app
- Not setting up CodePipeline — CodeBuild alone is sufficient

---

## Prerequisites (Before Starting)

1. **GitHub PAT:** Create a GitHub Personal Access Token with `repo` and `admin:repo_hook` scopes
2. **Store PAT in SSM:** `aws ssm put-parameter --name /codebuild/github-pat --type SecureString --value <TOKEN> --region us-west-2`
3. **Store PAT in us-east-1 too (for fuel):** `aws ssm put-parameter --name /codebuild/github-pat --type SecureString --value <TOKEN> --region us-east-1`
4. **Verify repo admin access:** Confirm the GitHub account has admin access to all 9 repos (needed for webhook creation)
