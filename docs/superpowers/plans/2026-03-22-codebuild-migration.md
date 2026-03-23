# GitHub Actions → AWS CodeBuild Migration Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate CI/CD from GitHub Actions to AWS CodeBuild for 9 projects, using a shared Terraform module.

**Architecture:** Shared Terraform module in `codyjo.com/terraform/modules/codebuild/` creates CodeBuild projects + IAM roles + webhooks. Each project calls the module with project-specific config. GitHub webhooks trigger builds on PR (CI) and push-to-main (CD).

**Tech Stack:** Terraform, AWS CodeBuild, IAM, CloudWatch Logs, GitHub webhooks

**Spec:** `docs/superpowers/specs/2026-03-22-github-actions-to-codebuild-design.md`

---

## Chunk 1: Prerequisites + Shared Terraform Module

### Task 1: Store GitHub PAT in SSM Parameter Store

**Prerequisite:** User must create a GitHub PAT with `repo` + `admin:repo_hook` scopes.

- [ ] **Step 1: Store PAT in us-west-2**

```bash
aws ssm put-parameter \
  --name /codebuild/github-pat \
  --type SecureString \
  --value "<GITHUB_PAT>" \
  --region us-west-2
```

- [ ] **Step 2: Store PAT in us-east-1 (for fuel)**

```bash
aws ssm put-parameter \
  --name /codebuild/github-pat \
  --type SecureString \
  --value "<GITHUB_PAT>" \
  --region us-east-1
```

---

### Task 2: Create Shared Terraform Module

**Files:**
- Create: `codyjo.com/terraform/modules/codebuild/main.tf`
- Create: `codyjo.com/terraform/modules/codebuild/variables.tf`
- Create: `codyjo.com/terraform/modules/codebuild/outputs.tf`

- [ ] **Step 1: Create module directory**

```bash
mkdir -p /home/merm/projects/codyjo.com/terraform/modules/codebuild
```

- [ ] **Step 2: Write `variables.tf`**

Create: `/home/merm/projects/codyjo.com/terraform/modules/codebuild/variables.tf`

```hcl
variable "project_name" {
  description = "Project identifier used in resource names"
  type        = string
}

variable "github_repo" {
  description = "GitHub repo in Owner/Repo format"
  type        = string
}

variable "github_branch" {
  description = "Branch that triggers CD builds"
  type        = string
  default     = "main"
}

variable "build_image" {
  description = "CodeBuild Docker image"
  type        = string
  default     = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
}

variable "ci_buildspec" {
  description = "Path to CI buildspec file in repo"
  type        = string
  default     = "buildspec-ci.yml"
}

variable "cd_buildspec" {
  description = "Path to CD buildspec file in repo"
  type        = string
  default     = "buildspec-cd.yml"
}

variable "deploy_policy_json" {
  description = "IAM policy JSON document granting deploy permissions to the CD role"
  type        = string
}

variable "compute_type" {
  description = "CodeBuild compute type"
  type        = string
  default     = "BUILD_GENERAL1_SMALL"
}

variable "cd_timeout" {
  description = "CD build timeout in minutes"
  type        = number
  default     = 30
}

variable "concurrent_build_limit" {
  description = "Max concurrent builds for CD project"
  type        = number
  default     = 1
}

variable "cd_timeout" {
  description = "CD build timeout in minutes"
  type        = number
  default     = 30
}

variable "ci_environment_variables" {
  description = "Environment variables for CI builds"
  type = list(object({
    name  = string
    value = string
    type  = string
  }))
  default = []
}

variable "cd_environment_variables" {
  description = "Environment variables for CD builds"
  type = list(object({
    name  = string
    value = string
    type  = string
  }))
  default = []
}
```

- [ ] **Step 3: Write `main.tf`**

Create: `/home/merm/projects/codyjo.com/terraform/modules/codebuild/main.tf`

```hcl
# ---------------------------------------------------------
# IAM Roles
# ---------------------------------------------------------

data "aws_iam_policy_document" "codebuild_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }
  }
}

# CI role — CloudWatch Logs only
resource "aws_iam_role" "ci" {
  name               = "${var.project_name}-codebuild-ci"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume.json
}

resource "aws_iam_role_policy" "ci_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.ci.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = [
          "${aws_cloudwatch_log_group.builds.arn}",
          "${aws_cloudwatch_log_group.builds.arn}:*",
        ]
      }
    ]
  })
}

# CD role — logs + deploy permissions
resource "aws_iam_role" "cd" {
  name               = "${var.project_name}-codebuild-cd"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume.json
}

resource "aws_iam_role_policy" "cd_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.cd.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = [
          "${aws_cloudwatch_log_group.builds.arn}",
          "${aws_cloudwatch_log_group.builds.arn}:*",
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "cd_deploy" {
  name   = "deploy-permissions"
  role   = aws_iam_role.cd.id
  policy = var.deploy_policy_json
}

# ---------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------

resource "aws_cloudwatch_log_group" "builds" {
  name              = "/codebuild/${var.project_name}"
  retention_in_days = 30
}

# ---------------------------------------------------------
# CodeBuild Projects
# ---------------------------------------------------------

resource "aws_codebuild_project" "ci" {
  name         = "${var.project_name}-ci"
  service_role = aws_iam_role.ci.arn

  source {
    type            = "GITHUB"
    location        = "https://github.com/${var.github_repo}.git"
    buildspec       = var.ci_buildspec
    git_clone_depth = 1

    report_build_status = true
  }

  environment {
    compute_type = var.compute_type
    image        = var.build_image
    type         = "LINUX_CONTAINER"

    dynamic "environment_variable" {
      for_each = var.ci_environment_variables
      content {
        name  = environment_variable.value.name
        value = environment_variable.value.value
        type  = environment_variable.value.type
      }
    }
  }

  artifacts {
    type = "NO_ARTIFACTS"
  }

  logs_config {
    cloudwatch_logs {
      group_name = aws_cloudwatch_log_group.builds.name
    }
  }
}

resource "aws_codebuild_project" "cd" {
  name                   = "${var.project_name}-cd"
  service_role           = aws_iam_role.cd.arn
  concurrent_build_limit = var.concurrent_build_limit
  build_timeout          = var.cd_timeout
  queued_timeout         = 60

  source {
    type            = "GITHUB"
    location        = "https://github.com/${var.github_repo}.git"
    buildspec       = var.cd_buildspec
    git_clone_depth = 1

    report_build_status = true
  }

  environment {
    compute_type = var.compute_type
    image        = var.build_image
    type         = "LINUX_CONTAINER"

    dynamic "environment_variable" {
      for_each = var.cd_environment_variables
      content {
        name  = environment_variable.value.name
        value = environment_variable.value.value
        type  = environment_variable.value.type
      }
    }
  }

  artifacts {
    type = "NO_ARTIFACTS"
  }

  logs_config {
    cloudwatch_logs {
      group_name = aws_cloudwatch_log_group.builds.name
    }
  }
}

# ---------------------------------------------------------
# Webhooks
# ---------------------------------------------------------

resource "aws_codebuild_webhook" "ci" {
  project_name = aws_codebuild_project.ci.name
  build_type   = "BUILD"

  filter_group {
    filter {
      type    = "EVENT"
      pattern = "PULL_REQUEST_CREATED,PULL_REQUEST_UPDATED,PULL_REQUEST_REOPENED"
    }
  }
}

resource "aws_codebuild_webhook" "cd" {
  project_name = aws_codebuild_project.cd.name
  build_type   = "BUILD"

  filter_group {
    filter {
      type    = "EVENT"
      pattern = "PUSH"
    }

    filter {
      type    = "HEAD_REF"
      pattern = "^refs/heads/${var.github_branch}$"
    }
  }
}
```

- [ ] **Step 4: Write `outputs.tf`**

Create: `/home/merm/projects/codyjo.com/terraform/modules/codebuild/outputs.tf`

```hcl
output "ci_project_name" {
  value = aws_codebuild_project.ci.name
}

output "cd_project_name" {
  value = aws_codebuild_project.cd.name
}

output "ci_role_arn" {
  value = aws_iam_role.ci.arn
}

output "cd_role_arn" {
  value = aws_iam_role.cd.arn
}

output "ci_webhook_url" {
  value = aws_codebuild_webhook.ci.payload_url
}

output "cd_webhook_url" {
  value = aws_codebuild_webhook.cd.payload_url
}
```

- [ ] **Step 5: Commit module**

```bash
cd /home/merm/projects/codyjo.com
git add terraform/modules/codebuild/
git commit -m "feat: add shared CodeBuild Terraform module for CI/CD migration"
```

---

### Task 3: Add GitHub Source Credential to codyjo.com Terraform

**Files:**
- Modify: `/home/merm/projects/codyjo.com/terraform/providers.tf` (add backend state for codebuild PAT)
- Create: `/home/merm/projects/codyjo.com/terraform/codebuild-credential.tf`

- [ ] **Step 1: Write source credential resource**

Create: `/home/merm/projects/codyjo.com/terraform/codebuild-credential.tf`

```hcl
# ---------------------------------------------------------
# GitHub source credential for CodeBuild (account-wide, per-region)
# ---------------------------------------------------------

data "aws_ssm_parameter" "github_pat" {
  name = "/codebuild/github-pat"
}

resource "aws_codebuild_source_credential" "github" {
  auth_type   = "PERSONAL_ACCESS_TOKEN"
  server_type = "GITHUB"
  token       = data.aws_ssm_parameter.github_pat.value
}
```

- [ ] **Step 2: Run `terraform plan` to verify**

```bash
cd /home/merm/projects/codyjo.com/terraform
terraform init
terraform plan -target=aws_codebuild_source_credential.github
```

Expected: Plan shows 1 resource to add.

- [ ] **Step 3: Apply the source credential**

```bash
cd /home/merm/projects/codyjo.com/terraform
terraform apply -target=aws_codebuild_source_credential.github -auto-approve
```

- [ ] **Step 4: Commit**

```bash
cd /home/merm/projects/codyjo.com
git add terraform/codebuild-credential.tf
git commit -m "feat: add CodeBuild GitHub source credential"
```

- [ ] **Step 5: Push to remote and tag the module for use by other projects**

```bash
cd /home/merm/projects/codyjo.com
git push origin main
git tag codebuild-module-v1
git push origin codebuild-module-v1
```

---

## Chunk 2: back-office Migration

### Task 4: Create back-office buildspec files

**Files:**
- Create: `/home/merm/projects/back-office/buildspec-ci.yml`
- Create: `/home/merm/projects/back-office/buildspec-cd.yml`

- [ ] **Step 1: Write `buildspec-ci.yml`**

Create: `/home/merm/projects/back-office/buildspec-ci.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.12
    commands:
      - pip install pytest pytest-cov ruff pyyaml

  build:
    commands:
      # Shell syntax validation
      - bash -n scripts/run-agent.sh
      - bash -n scripts/sync-dashboard.sh
      - bash -n scripts/quick-sync.sh
      - bash -n scripts/job-status.sh
      - bash -n agents/qa-scan.sh
      - bash -n agents/seo-audit.sh
      - bash -n agents/ada-audit.sh
      - bash -n agents/compliance-audit.sh
      - bash -n agents/monetization-audit.sh
      - bash -n agents/product-audit.sh
      - bash -n agents/fix-bugs.sh
      - bash -n agents/watch.sh

      # Python syntax validation
      - python3 -m py_compile scripts/*.py
      - python3 -m compileall backoffice/ -q

      # Python linting
      - ruff check scripts/ backoffice/

      # Regression suite
      - python3 -m pytest tests/ --cov=backoffice --cov-report=term
```

- [ ] **Step 2: Write `buildspec-cd.yml`**

Create: `/home/merm/projects/back-office/buildspec-cd.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.12
    commands:
      - pip install ruff pyyaml

  pre_build:
    commands:
      # Validate before deploying
      - bash -n scripts/sync-dashboard.sh
      - bash -n scripts/quick-sync.sh
      - bash -n scripts/job-status.sh
      - bash -n agents/qa-scan.sh
      - bash -n agents/seo-audit.sh
      - bash -n agents/ada-audit.sh
      - bash -n agents/compliance-audit.sh
      - bash -n agents/monetization-audit.sh
      - bash -n agents/product-audit.sh
      - bash -n agents/fix-bugs.sh
      - bash -n agents/watch.sh
      - python3 -m py_compile scripts/*.py
      - ruff check scripts/
      - make test

  build:
    commands:
      - bash scripts/sync-dashboard.sh
```

- [ ] **Step 3: Commit buildspecs**

```bash
cd /home/merm/projects/back-office
git add buildspec-ci.yml buildspec-cd.yml
git commit -m "feat: add CodeBuild buildspec files for CI/CD migration"
```

---

### Task 5: Create back-office CodeBuild Terraform

**Files:**
- Create: `/home/merm/projects/back-office/terraform/codebuild.tf`
- Modify: `/home/merm/projects/back-office/terraform/cd.tf` (will be deleted later)

- [ ] **Step 1: Write `codebuild.tf`**

Create: `/home/merm/projects/back-office/terraform/codebuild.tf`

```hcl
# ---------------------------------------------------------
# CodeBuild CI/CD (replaces GitHub Actions)
# ---------------------------------------------------------

module "codebuild" {
  source = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"

  project_name       = "back-office"
  github_repo        = "CodyJo/back-office"
  deploy_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Deploy"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          "arn:aws:s3:::admin-thenewbeautifulme-site",
          "arn:aws:s3:::admin-thenewbeautifulme-site/*",
        ]
      },
      {
        Sid    = "CloudFront"
        Effect = "Allow"
        Action = [
          "cloudfront:CreateInvalidation",
        ]
        Resource = "arn:aws:cloudfront::*:distribution/E372ZR95FXKVT5"
      },
    ]
  })
}
```

- [ ] **Step 2: Run `terraform init` and `terraform plan`**

```bash
cd /home/merm/projects/back-office/terraform
terraform init -upgrade
terraform plan
```

Expected: Plan shows CodeBuild projects, IAM roles, webhooks, log group to create. Existing resources unchanged.

- [ ] **Step 3: Apply**

```bash
cd /home/merm/projects/back-office/terraform
terraform apply -auto-approve
```

- [ ] **Step 4: Verify CI triggers — push a test branch**

```bash
cd /home/merm/projects/back-office
git checkout -b test-codebuild
echo "# codebuild test" >> README.md
git add README.md
git commit -m "test: verify CodeBuild CI trigger"
git push origin test-codebuild
```

Then open a PR on GitHub and check that the `back-office-ci` CodeBuild project triggers:

```bash
aws codebuild list-builds-for-project --project-name back-office-ci --sort-order DESCENDING --max-items 1 --region us-west-2
```

- [ ] **Step 5: Verify CD triggers — merge to main**

Merge the PR. Verify `back-office-cd` triggers and deploys successfully:

```bash
aws codebuild list-builds-for-project --project-name back-office-cd --sort-order DESCENDING --max-items 1 --region us-west-2
```

Check the build logs:

```bash
BUILD_ID=$(aws codebuild list-builds-for-project --project-name back-office-cd --sort-order DESCENDING --max-items 1 --query 'ids[0]' --output text --region us-west-2)
aws codebuild batch-get-builds --ids "$BUILD_ID" --query 'builds[0].buildStatus' --output text --region us-west-2
```

Expected: `SUCCEEDED`

- [ ] **Step 6: Delete GitHub Actions workflows**

```bash
cd /home/merm/projects/back-office
rm .github/workflows/ci.yml
rm .github/workflows/deploy.yml
rm .github/workflows/preview.yml
rm .github/workflows/nightly-backoffice.yml
rmdir .github/workflows .github 2>/dev/null || true
```

- [ ] **Step 7: Remove OIDC deploy role from Terraform**

Delete the contents of `cd.tf` and replace with a comment. Do NOT delete the OIDC data source reference yet (other projects depend on the provider existing).

Replace `/home/merm/projects/back-office/terraform/cd.tf` with:

```hcl
# GitHub Actions deploy role removed — CI/CD now runs on AWS CodeBuild.
# See codebuild.tf for the new configuration.
```

- [ ] **Step 8: Apply to destroy old role**

```bash
cd /home/merm/projects/back-office/terraform
terraform plan
```

Expected: Plan shows destruction of `aws_iam_role.github_deploy` and `aws_iam_role_policy.github_deploy`. No other changes.

```bash
terraform apply -auto-approve
```

- [ ] **Step 9: Update CLAUDE.md**

Edit `/home/merm/projects/back-office/CLAUDE.md`. Find the section referencing CI/CD or deployment, and add after the `## Data Flow` section:

```markdown
## CI/CD — AWS CodeBuild

CI and CD run on AWS CodeBuild (not GitHub Actions).

- **CI** (`back-office-ci`): Triggers on pull requests. Runs shell syntax validation, Python linting (ruff), and regression suite (pytest).
  - Config: `buildspec-ci.yml`
- **CD** (`back-office-cd`): Triggers on push to main. Validates, runs tests, then deploys dashboards via `scripts/sync-dashboard.sh`.
  - Config: `buildspec-cd.yml`
- **IAM role**: `back-office-codebuild-cd` — scoped to S3 (admin-thenewbeautifulme-site) and CloudFront (E372ZR95FXKVT5).
- **Infrastructure**: CodeBuild projects defined in `terraform/codebuild.tf` using shared module from `codyjo.com/terraform/modules/codebuild/`.
- **Logs**: CloudWatch `/codebuild/back-office`

To check build status: `aws codebuild list-builds-for-project --project-name back-office-cd --sort-order DESCENDING`
```

- [ ] **Step 10: Commit all changes**

```bash
cd /home/merm/projects/back-office
git add -A
git commit -m "feat: migrate CI/CD from GitHub Actions to AWS CodeBuild

- Add buildspec-ci.yml and buildspec-cd.yml
- Add terraform/codebuild.tf with shared module
- Remove GitHub Actions workflows
- Remove OIDC deploy role
- Update CLAUDE.md with CodeBuild documentation"
```

---

## Chunk 3: codyjo.com Migration

### Task 6: Create codyjo.com buildspec files

**Files:**
- Create: `/home/merm/projects/codyjo.com/buildspec-ci.yml`
- Create: `/home/merm/projects/codyjo.com/buildspec-cd.yml`

- [ ] **Step 1: Write `buildspec-ci.yml`**

Create: `/home/merm/projects/codyjo.com/buildspec-ci.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 22
    commands:
      - npm ci

  build:
    commands:
      - npm run check
      - npm run build
      - npm run verify:dist
```

- [ ] **Step 2: Write `buildspec-cd.yml`**

Create: `/home/merm/projects/codyjo.com/buildspec-cd.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 22
    commands:
      - npm ci

  build:
    commands:
      - npm run build

  post_build:
    commands:
      # Deploy static assets (immutable cache)
      - |
        aws s3 sync dist/ s3://www.codyjo.com/ \
          --delete \
          --cache-control "public, max-age=31536000, immutable" \
          --exclude "*.html" \
          --exclude "*.xml" \
          --exclude "robots.txt"
      # Deploy HTML (no cache)
      - |
        aws s3 sync dist/ s3://www.codyjo.com/ \
          --cache-control "public, max-age=0, must-revalidate" \
          --content-type "text/html; charset=utf-8" \
          --exclude "*" \
          --include "*.html"
      # Deploy XML + robots.txt (no cache)
      - |
        aws s3 sync dist/ s3://www.codyjo.com/ \
          --cache-control "public, max-age=0, must-revalidate" \
          --exclude "*" \
          --include "*.xml" \
          --include "robots.txt"
      # Invalidate CloudFront
      - aws cloudfront create-invalidation --distribution-id EF4U8A7W3OH5K --paths "/*"
      # Smoke test
      - sleep 10
      - |
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://www.codyjo.com/)
        if [ "$STATUS" != "200" ]; then echo "Smoke test failed: HTTP $STATUS"; exit 1; fi
        echo "Smoke test passed: HTTP $STATUS"
```

- [ ] **Step 3: Commit buildspecs**

```bash
cd /home/merm/projects/codyjo.com
git add buildspec-ci.yml buildspec-cd.yml
git commit -m "feat: add CodeBuild buildspec files for CI/CD migration"
```

---

### Task 7: Create codyjo.com CodeBuild Terraform

**Files:**
- Create: `/home/merm/projects/codyjo.com/terraform/codebuild.tf`

Note: codyjo.com uses a **relative path** for the module since the module lives in this repo. Also, codyjo.com's cd.tf uses a pre-existing role (`data "aws_iam_role"`) not a resource, so we keep the existing policy document and just retarget it to the CodeBuild role.

- [ ] **Step 1: Write `codebuild.tf`**

Create: `/home/merm/projects/codyjo.com/terraform/codebuild.tf`

```hcl
# ---------------------------------------------------------
# CodeBuild CI/CD (replaces GitHub Actions)
# ---------------------------------------------------------

module "codebuild" {
  source = "./modules/codebuild"

  project_name       = "codyjo-com"
  github_repo        = "CodyJo/codyjo.com"
  deploy_policy_json = data.aws_iam_policy_document.github_deploy.json
}
```

- [ ] **Step 2: Run `terraform plan`**

```bash
cd /home/merm/projects/codyjo.com/terraform
terraform init -upgrade
terraform plan
```

Expected: CodeBuild resources to create. Existing resources unchanged.

- [ ] **Step 3: Apply**

```bash
cd /home/merm/projects/codyjo.com/terraform
terraform apply -auto-approve
```

- [ ] **Step 4: Test CI (push branch, open PR)**

```bash
cd /home/merm/projects/codyjo.com
git checkout -b test-codebuild
echo "# test" >> README.md
git add README.md
git commit -m "test: verify CodeBuild CI trigger"
git push origin test-codebuild
```

Open PR, verify `codyjo-com-ci` triggers. Check build status:

```bash
aws codebuild list-builds-for-project --project-name codyjo-com-ci --sort-order DESCENDING --max-items 1 --region us-west-2
```

- [ ] **Step 5: Test CD (merge to main)**

Merge PR. Verify `codyjo-com-cd` triggers and deploys. Check `https://www.codyjo.com/` is still live.

- [ ] **Step 6: Delete GitHub Actions workflows**

```bash
cd /home/merm/projects/codyjo.com
rm .github/workflows/ci.yml
rm .github/workflows/cd.yml
rm .github/workflows/preview.yml
rm .github/workflows/terraform-admin.yml
rm .github/workflows/nightly-backoffice.yml
rmdir .github/workflows .github 2>/dev/null || true
```

Note: The `terraform-admin.yml` workflow is dropped. Terraform changes will be applied manually or via a future CodeBuild project if needed. The CD buildspec does not run Terraform — this matches the existing CD workflow which also did not run Terraform (that was a separate workflow).

- [ ] **Step 7: Update cd.tf to remove old role attachment**

The existing `cd.tf` attaches the deploy policy to the GitHub Actions role. The `data.aws_iam_policy_document.github_deploy` references `data.aws_iam_role.github_deploy.arn` in its `DeployRolePolicy` statement (self-referential — letting the role manage its own policy). This statement is not needed for CodeBuild, so remove it along with the data source and the role policy attachment.

In `/home/merm/projects/codyjo.com/terraform/cd.tf`:

1. Delete the `data "aws_iam_role" "github_deploy"` block
2. Delete the `resource "aws_iam_role_policy" "github_deploy"` block
3. In the `data "aws_iam_policy_document" "github_deploy"` block, delete the `DeployRolePolicy` statement (the one referencing `data.aws_iam_role.github_deploy.arn`)
4. Keep `data "aws_iam_policy_document" "github_deploy"` (used by codebuild.tf) and `data "aws_caller_identity" "current"`

- [ ] **Step 8: Apply to clean up old role policy**

```bash
cd /home/merm/projects/codyjo.com/terraform
terraform plan
terraform apply -auto-approve
```

- [ ] **Step 9: Create CLAUDE.md**

Create: `/home/merm/projects/codyjo.com/CLAUDE.md`

```markdown
# codyjo.com — Personal Portfolio

## Overview
Personal portfolio and parent site at www.codyjo.com. Built with Astro 5.

## Tech Stack
- **Framework:** Astro 5
- **Hosting:** S3 + CloudFront
- **IaC:** Terraform
- **Node.js:** 22

## Commands
- `npm run dev` — Start dev server
- `npm run build` — Production build (to `dist/`)
- `npm run check` — Astro check
- `npm run verify:dist` — Verify build output

## CI/CD — AWS CodeBuild

CI and CD run on AWS CodeBuild (not GitHub Actions).

- **CI** (`codyjo-com-ci`): Triggers on pull requests. Runs `npm run check`, `npm run build`, `npm run verify:dist`.
  - Config: `buildspec-ci.yml`
- **CD** (`codyjo-com-cd`): Triggers on push to main. Builds and deploys to S3/CloudFront.
  - Config: `buildspec-cd.yml`
- **IAM role**: `codyjo-com-codebuild-cd` — scoped to S3 (www.codyjo.com), CloudFront (EF4U8A7W3OH5K), admin infrastructure.
- **Infrastructure**: CodeBuild projects defined in `terraform/codebuild.tf`. Shared module lives in `terraform/modules/codebuild/`.
- **Logs**: CloudWatch `/codebuild/codyjo-com`

To check build status: `aws codebuild list-builds-for-project --project-name codyjo-com-cd --sort-order DESCENDING`

## Shared CodeBuild Module
The reusable Terraform module at `terraform/modules/codebuild/` is used by all BreakPoint Labs projects. Tagged as `codebuild-module-v1`. Other projects reference it via git URL.
```

- [ ] **Step 10: Commit all changes and push tag**

```bash
cd /home/merm/projects/codyjo.com
git add -A
git commit -m "feat: migrate CI/CD from GitHub Actions to AWS CodeBuild

- Add buildspec-ci.yml and buildspec-cd.yml
- Add terraform/codebuild.tf using local module
- Add codebuild-credential.tf for GitHub PAT
- Remove GitHub Actions workflows
- Clean up cd.tf to remove old role attachment
- Create CLAUDE.md with CodeBuild documentation"
```

```bash
git push origin main
git tag -f codebuild-module-v1
git push origin codebuild-module-v1 --force
```

---

## Chunk 4: selah Migration

### Task 8: Create selah buildspec files

**Files:**
- Create: `/home/merm/projects/selah/buildspec-ci.yml`
- Create: `/home/merm/projects/selah/buildspec-cd.yml`

- [ ] **Step 1: Write `buildspec-ci.yml`**

Create: `/home/merm/projects/selah/buildspec-ci.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  build:
    commands:
      - npm run lint
      - npm run typecheck
      - npm test
      - npm audit --audit-level=high
      - npm run build
```

- [ ] **Step 2: Write `buildspec-cd.yml`**

Create: `/home/merm/projects/selah/buildspec-cd.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  build:
    commands:
      - npm run build
      # Package Lambdas
      - cd lambda/interpret && npm ci --omit=dev 2>/dev/null || true && zip -r ../../interpret-lambda.zip . && cd ../..
      - cd lambda/api && npm ci --omit=dev 2>/dev/null || true && zip -r ../../api-lambda.zip . && cd ../..

  post_build:
    commands:
      # Deploy static site (immutable assets)
      - |
        aws s3 sync out/ s3://bible-app-site/ \
          --delete \
          --cache-control "public, max-age=31536000, immutable" \
          --exclude "*.html" \
          --exclude "*.json"
      # Deploy HTML + JSON (no cache)
      - |
        aws s3 sync out/ s3://bible-app-site/ \
          --delete \
          --cache-control "public, max-age=0, must-revalidate" \
          --include "*.html" \
          --include "*.json"
      # Deploy Lambdas
      - aws lambda update-function-code --function-name bible-app-interpret --zip-file fileb://interpret-lambda.zip --region us-west-2
      - aws lambda update-function-code --function-name bible-app-api --zip-file fileb://api-lambda.zip --region us-west-2
      # Invalidate CloudFront
      - |
        DIST_ID=$(aws cloudfront list-distributions \
          --query "DistributionList.Items[?contains(Aliases.Items, 'www.selahscripture.com')].Id" \
          --output text)
        aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
      # Smoke test
      - sleep 10
      - |
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://www.selahscripture.com/)
        if [ "$STATUS" != "200" ]; then echo "Smoke test failed: HTTP $STATUS"; exit 1; fi
        echo "Smoke test passed: HTTP $STATUS"
```

- [ ] **Step 3: Commit**

```bash
cd /home/merm/projects/selah
git add buildspec-ci.yml buildspec-cd.yml
git commit -m "feat: add CodeBuild buildspec files"
```

---

### Task 9: Create selah CodeBuild Terraform + cleanup

**Files:**
- Create: `/home/merm/projects/selah/terraform/codebuild.tf`
- Modify: `/home/merm/projects/selah/terraform/cd.tf`
- Modify: `/home/merm/projects/selah/CLAUDE.md`

- [ ] **Step 1: Write `codebuild.tf`**

Create: `/home/merm/projects/selah/terraform/codebuild.tf`

```hcl
module "codebuild" {
  source = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"

  project_name = "selah"
  github_repo  = "CodyJo/selah"


  deploy_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Deploy"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.site.arn,
          "${aws_s3_bucket.site.arn}/*",
        ]
      },
      {
        Sid      = "CloudFront"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation", "cloudfront:ListDistributions"]
        Resource = "*"
      },
      {
        Sid    = "Lambda"
        Effect = "Allow"
        Action = ["lambda:UpdateFunctionCode"]
        Resource = [
          aws_lambda_function.api.arn,
          aws_lambda_function.interpret.arn,
        ]
      },
    ]
  })
}
```

- [ ] **Step 2: `terraform init -upgrade` and `terraform plan`**

```bash
cd /home/merm/projects/selah/terraform
terraform init -upgrade
terraform plan
```

- [ ] **Step 3: Apply**

```bash
terraform apply -auto-approve
```

- [ ] **Step 4: Test CI + CD** (same pattern as previous projects — push branch, open PR, merge)

- [ ] **Step 5: Delete workflows**

```bash
cd /home/merm/projects/selah
rm .github/workflows/ci.yml .github/workflows/cd.yml .github/workflows/preview.yml .github/workflows/nightly-backoffice.yml
rmdir .github/workflows .github 2>/dev/null || true
```

- [ ] **Step 6: Replace `cd.tf`**

Replace contents of `/home/merm/projects/selah/terraform/cd.tf` with:

```hcl
# GitHub Actions deploy role removed — CI/CD now runs on AWS CodeBuild.
# See codebuild.tf for the new configuration.
```

- [ ] **Step 7: Apply to destroy old role**

```bash
cd /home/merm/projects/selah/terraform
terraform apply -auto-approve
```

- [ ] **Step 8: Update CLAUDE.md**

In `/home/merm/projects/selah/CLAUDE.md`, replace the `## Deployment` section and any references to GitHub Actions with:

```markdown
## CI/CD — AWS CodeBuild

CI and CD run on AWS CodeBuild (not GitHub Actions).

- **CI** (`selah-ci`): Triggers on pull requests. Runs lint, typecheck, test, audit, build.
  - Config: `buildspec-ci.yml`
- **CD** (`selah-cd`): Triggers on push to main. Builds site + Lambdas, deploys to S3/CloudFront.
  - Config: `buildspec-cd.yml`
- **IAM role**: `selah-codebuild-cd` — scoped to S3 (bible-app-site), Lambda (bible-app-interpret, bible-app-api), CloudFront.
- **Infrastructure**: CodeBuild projects defined in `terraform/codebuild.tf` using shared module from `codyjo.com/terraform/modules/codebuild/`.
- **Logs**: CloudWatch `/codebuild/selah`

To check build status: `aws codebuild list-builds-for-project --project-name selah-cd --sort-order DESCENDING`
```

Also update the `## Tech Stack` section to change `CI/CD: GitHub Actions (OIDC → AWS)` to `CI/CD: AWS CodeBuild`.

- [ ] **Step 9: Commit**

```bash
cd /home/merm/projects/selah
git add -A
git commit -m "feat: migrate CI/CD from GitHub Actions to AWS CodeBuild"
```

---

## Chunk 5: portis-app, fuel, certstudy Migrations

These three follow the same pattern as selah. Each gets buildspecs + codebuild.tf + cleanup.

### Task 10: portis-app Migration

**Files:**
- Create: `/home/merm/projects/portis-app/buildspec-ci.yml`
- Create: `/home/merm/projects/portis-app/buildspec-cd.yml`
- Create: `/home/merm/projects/portis-app/terraform/codebuild.tf`
- Modify: `/home/merm/projects/portis-app/terraform/cd.tf`
- Modify: `/home/merm/projects/portis-app/CLAUDE.md`
- Delete: `/home/merm/projects/portis-app/.github/workflows/*.yml`

- [ ] **Step 1: Write `buildspec-ci.yml`**

Create: `/home/merm/projects/portis-app/buildspec-ci.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  build:
    commands:
      - npm run lint
      - npm run typecheck
      - npm test
      - npm run test:coverage
      - npm run check:critical-coverage
      - npm audit --audit-level=high
      - NEXT_PUBLIC_API_URL=https://cordivent.com NEXT_PUBLIC_SITE_URL=https://cordivent.com npm run build
```

- [ ] **Step 2: Write `buildspec-cd.yml`**

Create: `/home/merm/projects/portis-app/buildspec-cd.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  build:
    commands:
      - NEXT_PUBLIC_API_URL=https://cordivent.com NEXT_PUBLIC_SITE_URL=https://cordivent.com npm run build
      - cd lambda/interpret && npm ci --omit=dev 2>/dev/null || true && zip -r ../../interpret-lambda.zip . && cd ../..
      - cd lambda/api && npm ci --omit=dev 2>/dev/null || true && zip -r ../../api-lambda.zip . && cd ../..

  post_build:
    commands:
      - |
        aws s3 sync out/ s3://etheos-app-site/ \
          --delete \
          --cache-control "public, max-age=31536000, immutable" \
          --exclude "*.html" --exclude "*.json"
      - |
        aws s3 sync out/ s3://etheos-app-site/ \
          --delete \
          --cache-control "public, max-age=0, must-revalidate" \
          --include "*.html" --include "*.json"
      - aws lambda update-function-code --function-name etheos-app-interpret --zip-file fileb://interpret-lambda.zip --region us-west-2
      - aws lambda update-function-code --function-name etheos-app-api --zip-file fileb://api-lambda.zip --region us-west-2
      - |
        DIST_ID=$(aws cloudfront list-distributions \
          --query "DistributionList.Items[?contains(Aliases.Items, 'cordivent.com')].Id" \
          --output text)
        aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
      - sleep 10
      - |
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cordivent.com/)
        if [ "$STATUS" != "200" ]; then echo "Smoke test failed: HTTP $STATUS"; exit 1; fi
        echo "Smoke test passed: HTTP $STATUS"
```

- [ ] **Step 3: Write `codebuild.tf`**

Create: `/home/merm/projects/portis-app/terraform/codebuild.tf`

```hcl
module "codebuild" {
  source = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"

  project_name = "portis-app"
  github_repo  = "CodyJo/portis-app"


  ci_environment_variables = [
    { name = "NEXT_PUBLIC_API_URL", value = "https://cordivent.com", type = "PLAINTEXT" },
    { name = "NEXT_PUBLIC_SITE_URL", value = "https://cordivent.com", type = "PLAINTEXT" },
  ]

  deploy_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Deploy"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.site.arn, "${aws_s3_bucket.site.arn}/*"]
      },
      {
        Sid      = "CloudFront"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation", "cloudfront:ListDistributions"]
        Resource = "*"
      },
      {
        Sid    = "Lambda"
        Effect = "Allow"
        Action = ["lambda:UpdateFunctionCode"]
        Resource = [
          aws_lambda_function.api.arn,
          aws_lambda_function.interpret.arn,
          aws_lambda_function.builder.arn,
        ]
      },
    ]
  })
}
```

- [ ] **Step 4: Apply, test CI+CD, delete workflows, replace cd.tf, update CLAUDE.md, commit**

Follow the same steps 2-9 from Task 9 (selah), adapted for portis-app:
- Project name: `portis-app`
- Workflows to delete: ci.yml, cd.yml, preview.yml, nightly-backoffice.yml
- CLAUDE.md CI/CD section: reference `portis-app-ci`, `portis-app-cd`, S3 (`etheos-app-site`), Lambdas (`etheos-app-interpret`, `etheos-app-api`)

```bash
cd /home/merm/projects/portis-app
git add -A
git commit -m "feat: migrate CI/CD from GitHub Actions to AWS CodeBuild"
```

---

### Task 11: fuel Migration

**Important:** Fuel is in **us-east-1**. Need a source credential in that region.

**Files:**
- Create: `/home/merm/projects/fuel/buildspec-ci.yml`
- Create: `/home/merm/projects/fuel/buildspec-cd.yml`
- Create: `/home/merm/projects/fuel/terraform/codebuild.tf`
- Delete: `/home/merm/projects/fuel/.github/workflows/*.yml`
- Modify: `/home/merm/projects/fuel/CLAUDE.md`

- [ ] **Step 1: Write `buildspec-ci.yml`**

Create: `/home/merm/projects/fuel/buildspec-ci.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  build:
    commands:
      - npm run lint
      - npm run typecheck
      - npm test
      - npm run build
```

- [ ] **Step 2: Write `buildspec-cd.yml`**

Create: `/home/merm/projects/fuel/buildspec-cd.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  build:
    commands:
      - npm run build
      - cd lambda/api && npm ci --omit=dev 2>/dev/null || true && zip -r ../../api-lambda.zip . && cd ../..
      - cd lambda/ai && npm ci --omit=dev && zip -r ../../ai-lambda.zip . && cd ../..

  post_build:
    commands:
      - |
        aws s3 sync out/ s3://fuel-site/ \
          --delete \
          --cache-control "public, max-age=31536000, immutable" \
          --exclude "*.html" --exclude "*.json"
      - |
        aws s3 sync out/ s3://fuel-site/ \
          --delete \
          --cache-control "public, max-age=0, must-revalidate" \
          --include "*.html" --include "*.json"
      - aws lambda update-function-code --function-name fuel-api --zip-file fileb://api-lambda.zip --region us-east-1
      - aws lambda update-function-code --function-name fuel-ai --zip-file fileb://ai-lambda.zip --region us-east-1
      - |
        DIST_ID=$(aws cloudfront list-distributions \
          --query "DistributionList.Items[?contains(Aliases.Items, 'fuel.codyjo.com')].Id" \
          --output text)
        aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
      - sleep 10
      - |
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://fuel.codyjo.com/)
        if [ "$STATUS" != "200" ]; then echo "Smoke test failed: HTTP $STATUS"; exit 1; fi
        echo "Smoke test passed: HTTP $STATUS"
```

- [ ] **Step 3: Write `codebuild.tf` (includes source credential for us-east-1)**

Create: `/home/merm/projects/fuel/terraform/codebuild.tf`

```hcl
# ---------------------------------------------------------
# CodeBuild source credential (us-east-1)
# ---------------------------------------------------------

data "aws_ssm_parameter" "github_pat" {
  name     = "/codebuild/github-pat"
  provider = aws  # us-east-1 provider
}

resource "aws_codebuild_source_credential" "github" {
  auth_type   = "PERSONAL_ACCESS_TOKEN"
  server_type = "GITHUB"
  token       = data.aws_ssm_parameter.github_pat.value
}

# ---------------------------------------------------------
# CodeBuild CI/CD
# ---------------------------------------------------------

module "codebuild" {
  source = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"

  project_name = "fuel"
  github_repo  = "CodyJo/fuel"


  deploy_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Deploy"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = ["arn:aws:s3:::fuel-site", "arn:aws:s3:::fuel-site/*"]
      },
      {
        Sid      = "CloudFront"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation", "cloudfront:ListDistributions"]
        Resource = "*"
      },
      {
        Sid    = "Lambda"
        Effect = "Allow"
        Action = ["lambda:UpdateFunctionCode"]
        Resource = [
          "arn:aws:lambda:us-east-1:*:function:fuel-api",
          "arn:aws:lambda:us-east-1:*:function:fuel-ai",
        ]
      },
    ]
  })

  depends_on = [aws_codebuild_source_credential.github]
}
```

Note: fuel had no deploy role in Terraform before. This creates everything fresh. The Lambda ARN reference assumes `aws_lambda_function.api` exists in fuel's lambda.tf. If fuel also has an `ai` Lambda function resource, add it to the policy.

- [ ] **Step 4: Apply, test, delete workflows (ci.yml, cd.yml), update CLAUDE.md, commit**

```bash
cd /home/merm/projects/fuel
# ... terraform apply, test, cleanup same pattern ...
git add -A
git commit -m "feat: migrate CI/CD from GitHub Actions to AWS CodeBuild"
```

---

### Task 12: certstudy Migration

**Files:**
- Create: `/home/merm/projects/certstudy/buildspec-ci.yml`
- Create: `/home/merm/projects/certstudy/buildspec-cd.yml`
- Create: `/home/merm/projects/certstudy/terraform/codebuild.tf`
- Modify: `/home/merm/projects/certstudy/terraform/cd.tf`
- Delete: `/home/merm/projects/certstudy/.github/workflows/*.yml`
- Modify: `/home/merm/projects/certstudy/CLAUDE.md`

- [ ] **Step 1: Write `buildspec-ci.yml`**

Create: `/home/merm/projects/certstudy/buildspec-ci.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  build:
    commands:
      - npm run lint
      - npm run typecheck
      - npm test
      - npm audit --audit-level=high
      - npm run build
```

- [ ] **Step 2: Write `buildspec-cd.yml`**

Create: `/home/merm/projects/certstudy/buildspec-cd.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  build:
    commands:
      - npm run build
      - cd lambda/api && npm ci --omit=dev 2>/dev/null || true && zip -r ../../api-lambda.zip . && cd ../..
      - cd lambda/tutor && npm ci --omit=dev 2>/dev/null || true && zip -r ../../tutor-lambda.zip . && cd ../..
      - cd lambda/planner && npm ci --omit=dev 2>/dev/null || true && zip -r ../../planner-lambda.zip . && cd ../..

  post_build:
    commands:
      - |
        aws s3 sync out/ s3://certstudy-site/ \
          --delete \
          --cache-control "public, max-age=31536000, immutable" \
          --exclude "*.html" --exclude "*.json"
      - |
        aws s3 sync out/ s3://certstudy-site/ \
          --delete \
          --cache-control "public, max-age=0, must-revalidate" \
          --include "*.html" --include "*.json"
      - aws lambda update-function-code --function-name certstudy-api --zip-file fileb://api-lambda.zip --region us-west-2
      - aws lambda update-function-code --function-name certstudy-tutor --zip-file fileb://tutor-lambda.zip --region us-west-2
      - aws lambda update-function-code --function-name certstudy-planner --zip-file fileb://planner-lambda.zip --region us-west-2
      - |
        DIST_ID=$(aws cloudfront list-distributions \
          --query "DistributionList.Items[?contains(Aliases.Items, 'study.codyjo.com')].Id" \
          --output text)
        aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
      - sleep 10
      - |
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://study.codyjo.com/)
        if [ "$STATUS" != "200" ]; then echo "Smoke test failed: HTTP $STATUS"; exit 1; fi
        echo "Smoke test passed: HTTP $STATUS"
```

- [ ] **Step 3: Write `codebuild.tf`**

Create: `/home/merm/projects/certstudy/terraform/codebuild.tf`

```hcl
module "codebuild" {
  source = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"

  project_name = "certstudy"
  github_repo  = "CodyJo/certstudy"


  deploy_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Deploy"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.site.arn, "${aws_s3_bucket.site.arn}/*"]
      },
      {
        Sid      = "CloudFront"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation", "cloudfront:ListDistributions"]
        Resource = "*"
      },
      {
        Sid    = "Lambda"
        Effect = "Allow"
        Action = ["lambda:UpdateFunctionCode"]
        Resource = [
          aws_lambda_function.api.arn,
          aws_lambda_function.tutor.arn,
          aws_lambda_function.planner.arn,
        ]
      },
    ]
  })
}
```

- [ ] **Step 4: Apply, test, delete workflows (ci.yml, cd.yml), replace cd.tf, update CLAUDE.md, commit**

Same pattern. Workflows to delete: ci.yml, cd.yml only (no preview or nightly).

```bash
cd /home/merm/projects/certstudy
git add -A
git commit -m "feat: migrate CI/CD from GitHub Actions to AWS CodeBuild"
```

---

## Chunk 6: analogify Migration

### Task 13: Create analogify buildspec files

**Files:**
- Create: `/home/merm/projects/analogify/buildspec-ci.yml`
- Create: `/home/merm/projects/analogify/buildspec-cd.yml`

- [ ] **Step 1: Write `buildspec-ci.yml`**

Create: `/home/merm/projects/analogify/buildspec-ci.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.12
      nodejs: 20
    commands:
      - pip install ruff
      - pip install -r tests/requirements.txt
      - cd marketing && npm ci && cd ..

  build:
    commands:
      # Python linting
      - ruff check .

      # Python tests
      - pytest tests/

      # Marketing site checks
      - cd marketing && npm run check && npm test && cd ..

      # Terraform validation (with stubs)
      - |
        cd terraform
        touch demo.tf
        echo 'variable "demo_secret_arn" { default = "arn:aws:secretsmanager:us-west-2:000000000000:secret:placeholder" }' > demo.tf
        echo 'resource "aws_lambda_function" "demo" { function_name = "x" role = "arn:aws:iam::000000000000:role/x" runtime = "python3.12" handler = "handler.handler" filename = "placeholder.zip" }' >> demo.tf
        terraform init -backend=false
        terraform validate
        rm demo.tf
```

- [ ] **Step 2: Write `buildspec-cd.yml`**

Create: `/home/merm/projects/analogify/buildspec-cd.yml`

```yaml
version: 0.2

env:
  variables:
    AWS_REGION: us-west-2
    PHOTOS_BUCKET: codyjo-com-photos-7fa5a7d0
    CF_DISTRIBUTION: EW2SF2IXBOKE5

phases:
  install:
    runtime-versions:
      python: 3.12
    commands:
      - pip install ruff pyyaml
      - pip install -r tests/requirements.txt

  pre_build:
    commands:
      - bash scripts/build-admin-lambda.sh "$PWD/.build/admin.zip"

      - |
        mkdir -p .build/auth_view
        pip install --platform manylinux2014_x86_64 --python-version 3.12 \
          --implementation cp --only-binary=:all: \
          -r lambda/auth_view/requirements.txt -t .build/auth_view --quiet
        cp lambda/auth_view/handler.py .build/auth_view/
        cd .build/auth_view && zip -rq ../auth_view.zip .

      - |
        mkdir -p .build/auth_download
        pip install --platform manylinux2014_x86_64 --python-version 3.12 \
          --implementation cp --only-binary=:all: \
          -r lambda/auth_download/requirements.txt -t .build/auth_download --quiet
        cp lambda/auth_download/handler.py .build/auth_download/
        cd .build/auth_download && zip -rq ../auth_download.zip .

      - |
        mkdir -p .build/maintenance
        cp lambda/maintenance/handler.py .build/maintenance/
        cd .build/maintenance && zip -rq ../maintenance.zip .

      - |
        mkdir -p .build/zip
        cp lambda/zip/handler.py .build/zip/
        cd .build/zip && zip -rq ../zip.zip .

  build:
    commands:
      # Deploy Lambdas
      - |
        for fn in admin auth_view auth_download maintenance zip; do
          lambda_name="photo-gallery-${fn//_/-}"
          echo "Deploying $lambda_name..."
          aws lambda update-function-code \
            --function-name "$lambda_name" \
            --zip-file "fileb://.build/${fn}.zip" \
            --region $AWS_REGION \
            --output text --query 'FunctionName'
        done

      # Deploy frontend HTML
      - |
        for html_file in admin.html gallery.html sample-gallery.html login.html feedback.html; do
          aws s3 cp "frontend/$html_file" "s3://$PHOTOS_BUCKET/$html_file" \
            --content-type "text/html" \
            --cache-control "no-cache, no-store"
        done

      # Invalidate CloudFront
      - |
        aws cloudfront create-invalidation \
          --distribution-id $CF_DISTRIBUTION \
          --paths "/admin.html" "/gallery.html" "/sample-gallery.html" "/login.html" "/feedback.html" "/" \
          --output text --query 'Invalidation.Id'

  post_build:
    commands:
      # Smoke test
      - |
        RUN_LIVE_SMOKE=1 \
        SMOKE_GALLERY_SLUG=joanne-garrison \
        SMOKE_GALLERY_EMAIL=smoke-test@example.com \
        SMOKE_GALLERY_URL=https://galleries.analogifystudio.com \
        SMOKE_GALLERY_API_URL=https://3pfumef32i.execute-api.us-west-2.amazonaws.com \
        python3 -m pytest tests/smoke -m smoke -v

      # Clean up stale worktree branches
      - |
        git fetch --prune
        STALE=$(git branch -r | grep 'origin/worktree-agent-' | sed 's|origin/||' | tr -d ' ')
        if [ -n "$STALE" ]; then
          for branch in $STALE; do
            echo "Deleting origin/$branch"
            git push origin --delete "$branch"
          done
        fi
```

- [ ] **Step 3: Commit**

```bash
cd /home/merm/projects/analogify
git add buildspec-ci.yml buildspec-cd.yml
git commit -m "feat: add CodeBuild buildspec files"
```

---

### Task 14: Create analogify CodeBuild Terraform + cleanup

**Files:**
- Create: `/home/merm/projects/analogify/terraform/codebuild.tf`
- Modify: `/home/merm/projects/analogify/terraform/cd.tf`
- Create: `/home/merm/projects/analogify/CLAUDE.md`
- Delete: `/home/merm/projects/analogify/.github/workflows/*.yml`

**CRITICAL:** analogify's `cd.tf` CREATES the OIDC provider. Do NOT delete the `aws_iam_openid_connect_provider.github` resource yet — other projects still reference it. Only delete the deploy role + role policy for now.

- [ ] **Step 1: Write `codebuild.tf`**

Create: `/home/merm/projects/analogify/terraform/codebuild.tf`

```hcl
module "codebuild" {
  source = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"

  project_name = "analogify"
  github_repo  = "CodyJo/analogify"
  runtime      = "python312"

  cd_environment_variables = [
    { name = "AWS_REGION", value = "us-west-2", type = "PLAINTEXT" },
    { name = "PHOTOS_BUCKET", value = "codyjo-com-photos-7fa5a7d0", type = "PLAINTEXT" },
    { name = "CF_DISTRIBUTION", value = "EW2SF2IXBOKE5", type = "PLAINTEXT" },
  ]

  deploy_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "LambdaDeploy"
        Effect   = "Allow"
        Action   = ["lambda:UpdateFunctionCode", "lambda:GetFunction"]
        Resource = "arn:aws:lambda:us-west-2:${data.aws_caller_identity.current.account_id}:function:photo-gallery-*"
      },
      {
        Sid    = "S3Frontend"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject"]
        Resource = "${aws_s3_bucket.photos.arn}/*.html"
      },
      {
        Sid      = "CloudFrontInvalidate"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation"]
        Resource = aws_cloudfront_distribution.gallery.arn
      },
    ]
  })
}
```

- [ ] **Step 2: Modify `cd.tf` — remove deploy role but KEEP OIDC provider**

In `/home/merm/projects/analogify/terraform/cd.tf`, delete:
- `resource "aws_iam_role" "github_deploy"` block
- `resource "aws_iam_role_policy" "github_deploy"` block
- `output "github_deploy_role_arn"` block

Keep:
- `resource "aws_iam_openid_connect_provider" "github"` block (will be removed in Chunk 9)

- [ ] **Step 3: Apply, test, delete workflows (ci.yml, cd.yml, preview.yml, nightly-backoffice.yml)**

- [ ] **Step 4: Create CLAUDE.md**

Create `/home/merm/projects/analogify/CLAUDE.md` with project overview and CodeBuild CI/CD section. Reference `analogify-ci`, `analogify-cd`, S3 (`codyjo-com-photos-7fa5a7d0`), CloudFront (EW2SF2IXBOKE5), 5 Lambdas.

- [ ] **Step 5: Commit**

```bash
cd /home/merm/projects/analogify
git add -A
git commit -m "feat: migrate CI/CD from GitHub Actions to AWS CodeBuild"
```

---

## Chunk 7: auth-service Migration

### Task 15: auth-service Migration

This is the most different from the pattern — it runs `terraform apply` during CD and needs secrets from Secrets Manager.

**Files:**
- Create: `/home/merm/projects/auth-service/buildspec-ci.yml`
- Create: `/home/merm/projects/auth-service/buildspec-cd.yml`
- Create: `/home/merm/projects/auth-service/terraform/codebuild.tf`
- Create: `/home/merm/projects/auth-service/CLAUDE.md`
- Delete: `/home/merm/projects/auth-service/.github/workflows/*.yml`

- [ ] **Step 1: Write `buildspec-ci.yml`**

Create: `/home/merm/projects/auth-service/buildspec-ci.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  build:
    commands:
      - npm run lint
      - npm test
```

- [ ] **Step 2: Write `buildspec-cd.yml`**

Create: `/home/merm/projects/auth-service/buildspec-cd.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci
      # Install Terraform
      - |
        curl -sL https://releases.hashicorp.com/terraform/1.11.4/terraform_1.11.4_linux_amd64.zip -o terraform.zip
        unzip -o terraform.zip -d /usr/local/bin/
        terraform --version

  pre_build:
    commands:
      - npm test
      - npm run zip

  build:
    commands:
      - cd terraform && terraform init -input=false
      - cd terraform && terraform apply -auto-approve -input=false

  post_build:
    commands:
      - aws lambda update-function-code --function-name auth-service-api --zip-file fileb://terraform/.build/api.zip
      - |
        API_URL=$(cd terraform && terraform output -raw api_url)
        STATUS=$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/api/health")
        if [ "$STATUS" != "200" ]; then echo "Health check failed: $STATUS"; exit 1; fi
        echo "Health check passed: $STATUS"
```

- [ ] **Step 3: Write `codebuild.tf`**

Create: `/home/merm/projects/auth-service/terraform/codebuild.tf`

The CD role needs broader permissions since it runs `terraform apply`:

```hcl
module "codebuild" {
  source = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"

  project_name = "auth-service"
  github_repo  = "CodyJo/auth-service"


  cd_environment_variables = [
    { name = "TF_VAR_jwt_secret", value = "auth-service/jwt-secret", type = "SECRETS_MANAGER" },
    { name = "TF_VAR_resend_api_key", value = "auth-service/resend-api-key", type = "SECRETS_MANAGER" },
  ]

  deploy_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Lambda"
        Effect = "Allow"
        Action = [
          "lambda:*",
        ]
        Resource = "arn:aws:lambda:us-west-2:*:function:auth-service-*"
      },
      {
        Sid    = "IAM"
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:GetRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:ListInstanceProfilesForRole",
          "iam:PassRole",
          "iam:TagRole",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
        ]
        Resource = "*"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:*",
        ]
        Resource = "arn:aws:dynamodb:us-west-2:*:table/auth-service-*"
      },
      {
        Sid    = "SecretsManager"
        Effect = "Allow"
        Action = [
          "secretsmanager:*",
        ]
        Resource = "arn:aws:secretsmanager:us-west-2:*:secret:auth-service/*"
      },
      {
        Sid    = "APIGateway"
        Effect = "Allow"
        Action = [
          "apigateway:*",
        ]
        Resource = "*"
      },
      {
        Sid    = "TerraformState"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::photo-gallery-tfstate-229678440188",
          "arn:aws:s3:::photo-gallery-tfstate-229678440188/auth-service/*",
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:DeleteLogGroup",
          "logs:DescribeLogGroups",
          "logs:PutRetentionPolicy",
          "logs:ListTagsForResource",
          "logs:TagResource",
        ]
        Resource = "*"
      },
    ]
  })
}
```

- [ ] **Step 4: Apply, test, delete workflows (ci.yml, cd.yml), create CLAUDE.md, commit**

```bash
cd /home/merm/projects/auth-service
git add -A
git commit -m "feat: migrate CI/CD from GitHub Actions to AWS CodeBuild"
```

---

## Chunk 8: thenewbeautifulme Migration

### Task 16: thenewbeautifulme Migration (most complex)

**Files:**
- Create: `/home/merm/projects/thenewbeautifulme/buildspec-ci.yml`
- Create: `/home/merm/projects/thenewbeautifulme/buildspec-cd.yml`
- Create: `/home/merm/projects/thenewbeautifulme/terraform/codebuild.tf`
- Modify: `/home/merm/projects/thenewbeautifulme/terraform/cd.tf`
- Modify: `/home/merm/projects/thenewbeautifulme/CLAUDE.md`
- Delete: `/home/merm/projects/thenewbeautifulme/.github/workflows/*.yml`

- [ ] **Step 1: Write `buildspec-ci.yml`**

Create: `/home/merm/projects/thenewbeautifulme/buildspec-ci.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci
      - cd useradmin && npm ci && cd ..

  build:
    commands:
      - npm run lint
      - npm run typecheck
      - npm test
      - npm audit --audit-level=high
      - NEXT_PUBLIC_API_URL=https://thenewbeautifulme.com npm run build
      - cd useradmin && NEXT_PUBLIC_API_URL=https://useradmin.thenewbeautifulme.com npm run build
```

- [ ] **Step 2: Write `buildspec-cd.yml`**

Create: `/home/merm/projects/thenewbeautifulme/buildspec-cd.yml`

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci
      - cd useradmin && npm ci && cd ..
      # Install Terraform
      - |
        curl -sL https://releases.hashicorp.com/terraform/1.11.4/terraform_1.11.4_linux_amd64.zip -o terraform.zip
        unzip -o terraform.zip -d /usr/local/bin/
        terraform --version
      # Install Lambda dependencies
      - cd lambda/interpret && npm ci --omit=dev && cd ../..
      - cd lambda/og && npm ci --omit=dev --cpu=arm64 --os=linux && cd ../..

  build:
    commands:
      # Build main site
      - NEXT_PUBLIC_API_URL=https://thenewbeautifulme.com npm run build
      # Build admin site
      - cd useradmin && NEXT_PUBLIC_API_URL=https://useradmin.thenewbeautifulme.com npm run build && cd ..
      # Terraform apply (Lambda infrastructure)
      - |
        cd terraform
        terraform init -input=false -no-color
        terraform plan -out=lambda-infra.tfplan -input=false -no-color \
          -target=aws_iam_role_policy.lambda_secrets \
          -target=aws_iam_role_policy.api_secrets \
          -target=aws_lambda_function.interpret \
          -target=aws_lambda_function.api \
          -target=aws_lambda_function.analytics \
          -target=aws_iam_role_policy.analytics_dynamodb \
          -target=aws_lambda_function.og
        terraform apply -auto-approve -input=false -no-color lambda-infra.tfplan
        cd ..

  post_build:
    commands:
      # Deploy main site to S3
      - |
        aws s3 sync out/ s3://thenewbeautifulme-site/ \
          --delete \
          --cache-control "public, max-age=31536000, immutable" \
          --exclude "*.html" --exclude "*.json" \
          --exclude "backoffice.html" --exclude "*-data.json"
      - |
        aws s3 sync out/ s3://thenewbeautifulme-site/ \
          --delete \
          --cache-control "public, max-age=0, must-revalidate" \
          --include "*.html" --include "*.json" \
          --exclude "backoffice.html" --exclude "*-data.json"
      # Deploy admin site to S3
      - |
        aws s3 sync useradmin/out/ s3://useradmin-thenewbeautifulme-site/ \
          --delete \
          --cache-control "public, max-age=31536000, immutable" \
          --exclude "*.html" --exclude "*.json"
      - |
        aws s3 sync useradmin/out/ s3://useradmin-thenewbeautifulme-site/ \
          --delete \
          --cache-control "public, max-age=0, must-revalidate" \
          --include "*.html" --include "*.json"
      # Invalidate main CloudFront
      - |
        DIST_ID=$(aws cloudfront list-distributions \
          --query "DistributionList.Items[?contains(Aliases.Items, 'thenewbeautifulme.com')].Id" \
          --output text)
        aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
      # Invalidate admin CloudFront
      - |
        DIST_ID=$(aws cloudfront list-distributions \
          --query "DistributionList.Items[?contains(Aliases.Items, 'useradmin.thenewbeautifulme.com')].Id" \
          --output text)
        aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
      # Smoke tests
      - sleep 10
      - |
        HOME_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://thenewbeautifulme.com/)
        READING_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://thenewbeautifulme.com/reading)
        DAILY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://thenewbeautifulme.com/daily)
        GUEST_INTERPRET_STATUS=$(curl -s -o /tmp/interpret-guest-smoke.json -w "%{http_code}" -X POST https://thenewbeautifulme.com/api/interpret \
          -H 'content-type: application/json' \
          --data '{"cards":[{"name":"The Star","position":"Focus","isReversed":false,"uprightMeaning":"Hope","reversedMeaning":"Doubt","keywords":["hope"],"description":"A bright light."}],"spreadType":"single","question":"What should I know?","style":"spiritual"}')
        ADMIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://useradmin.thenewbeautifulme.com/)
        OG_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://thenewbeautifulme.com/api/og?type=card&name=The+Fool")

        if [ "$HOME_STATUS" != "200" ]; then echo "FAIL: home $HOME_STATUS"; exit 1; fi
        if [ "$READING_STATUS" != "200" ]; then echo "FAIL: reading $READING_STATUS"; exit 1; fi
        if [ "$DAILY_STATUS" != "200" ]; then echo "FAIL: daily $DAILY_STATUS"; exit 1; fi
        if [ "$GUEST_INTERPRET_STATUS" != "401" ]; then echo "FAIL: guest interpret $GUEST_INTERPRET_STATUS"; exit 1; fi
        if [ "$ADMIN_STATUS" != "200" ]; then echo "FAIL: admin $ADMIN_STATUS"; exit 1; fi
        if [ "$OG_STATUS" != "200" ]; then echo "FAIL: og $OG_STATUS"; exit 1; fi
        echo "All smoke tests passed"
```

- [ ] **Step 3: Write `codebuild.tf`**

Create: `/home/merm/projects/thenewbeautifulme/terraform/codebuild.tf`

```hcl
module "codebuild" {
  source = "git::https://github.com/CodyJo/codyjo.com.git//terraform/modules/codebuild?ref=codebuild-module-v1"

  project_name = "thenewbeautifulme"
  github_repo  = "CodyJo/thenewbeautifulme"

  cd_timeout   = 30

  ci_environment_variables = [
    { name = "NEXT_PUBLIC_API_URL", value = "https://thenewbeautifulme.com", type = "PLAINTEXT" },
  ]

  deploy_policy_json = data.aws_iam_policy_document.github_deploy.json
}
```

This reuses the existing `data.aws_iam_policy_document.github_deploy` from `cd.tf` which already has all the required permissions.

- [ ] **Step 4: Modify `cd.tf`**

Remove `data "aws_iam_role" "github_deploy"` and `resource "aws_iam_role_policy" "github_deploy"` from cd.tf. Keep `data "aws_iam_policy_document" "github_deploy"`, `data "aws_caller_identity" "current"`, and the `locals` block.

- [ ] **Step 5: Apply, test CI + CD, verify all 6 smoke tests pass**

- [ ] **Step 6: Delete workflows**

```bash
cd /home/merm/projects/thenewbeautifulme
rm .github/workflows/ci.yml .github/workflows/cd.yml .github/workflows/preview.yml .github/workflows/nightly-backoffice.yml
rmdir .github/workflows .github 2>/dev/null || true
```

- [ ] **Step 7: Update CLAUDE.md**

Update CI/CD section to reference `thenewbeautifulme-ci`, `thenewbeautifulme-cd`, and document the Terraform apply + 2-site deploy + 6 smoke tests.

- [ ] **Step 8: Commit**

```bash
cd /home/merm/projects/thenewbeautifulme
git add -A
git commit -m "feat: migrate CI/CD from GitHub Actions to AWS CodeBuild"
```

---

## Chunk 9: Final Cleanup

### Task 17: Remove OIDC Provider from analogify

Only run this after ALL 9 projects are confirmed working on CodeBuild.

- [ ] **Step 1: Verify no project still uses GitHub Actions OIDC**

```bash
for project in back-office codyjo.com selah portis-app fuel certstudy analogify auth-service thenewbeautifulme; do
  if [ -d "/home/merm/projects/$project/.github/workflows" ]; then
    echo "WARNING: $project still has .github/workflows/"
  fi
done
```

Expected: No warnings.

- [ ] **Step 2: Remove OIDC provider from analogify Terraform**

In `/home/merm/projects/analogify/terraform/cd.tf`, delete the remaining `resource "aws_iam_openid_connect_provider" "github"` block.

- [ ] **Step 3: Check for other projects referencing the OIDC provider**

```bash
grep -r "aws_iam_openid_connect_provider" /home/merm/projects/*/terraform/ 2>/dev/null | grep -v node_modules | grep -v .terraform
```

If any project still references it via `data`, those references must also be removed.

- [ ] **Step 4: Apply to destroy OIDC provider**

```bash
cd /home/merm/projects/analogify/terraform
terraform plan
terraform apply -auto-approve
```

- [ ] **Step 5: Commit**

```bash
cd /home/merm/projects/analogify
git add terraform/cd.tf
git commit -m "chore: remove GitHub Actions OIDC provider (all projects migrated to CodeBuild)"
```

---

### Task 18: Update Project Memory

- [ ] **Step 1: Update MEMORY.md**

In `/home/merm/.claude/projects/-home-merm-projects/memory/MEMORY.md`, change:
```
- Uses GitHub Actions for CI/CD
```
to:
```
- Uses AWS CodeBuild for CI/CD (migrated from GitHub Actions 2026-03-22)
```

- [ ] **Step 2: Save migration memory**

Create a project memory file documenting the migration for future context.

---

### Task 19: Final Verification

- [ ] **Step 1: Verify all CodeBuild projects exist**

```bash
for project in back-office codyjo-com selah portis-app fuel certstudy analogify auth-service thenewbeautifulme; do
  echo "=== $project ==="
  aws codebuild batch-get-projects --names "${project}-ci" "${project}-cd" --query 'projects[].name' --output text --region us-west-2 2>/dev/null
done
# Check fuel separately in us-east-1
aws codebuild batch-get-projects --names fuel-ci fuel-cd --query 'projects[].name' --output text --region us-east-1
```

- [ ] **Step 2: Verify no GitHub Actions workflows remain**

```bash
for project in back-office codyjo.com selah portis-app fuel certstudy analogify auth-service thenewbeautifulme; do
  if [ -d "/home/merm/projects/$project/.github/workflows" ]; then
    echo "FAIL: $project still has workflows"
    ls "/home/merm/projects/$project/.github/workflows/"
  else
    echo "OK: $project clean"
  fi
done
```

- [ ] **Step 3: Verify all sites are live**

```bash
for url in \
  https://www.codyjo.com/ \
  https://www.selahscripture.com/ \
  https://thenewbeautifulme.com/ \
  https://cordivent.com/ \
  https://fuel.codyjo.com/ \
  https://study.codyjo.com/ \
  https://galleries.analogifystudio.com/; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  echo "$url → $STATUS"
done
```

Expected: All return 200.
