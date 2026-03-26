# Compliance Controls

Last updated: March 25, 2026

## Scope

Back Office is an internal engineering operations system. It audits repositories, aggregates findings, renders a local or admin dashboard, and can queue reviewable engineering work.

It is not a consumer-facing product and is not designed to collect end-user profile data as a primary system of record. Its main compliance exposure is operational and incidental:

- repository contents may contain personal data or secrets by mistake
- audit findings may quote or summarize code/config containing sensitive material
- local and published dashboard artifacts may retain that material if not governed

## Data Categories

Back Office may process:

- target repo metadata: name, path, language, configured commands
- audit findings: severity, description, file paths, evidence snippets, fix guidance
- queue metadata: task status, actor, approval notes, PR metadata
- audit logs: timestamps, target names, department run state, summary metrics

Back Office should not be treated as a durable system of record for customer data.

## Retention Policy

Default local retention policy:

- `results/<repo>/*-findings.json`: retain only the current working audit set needed for active triage
- `dashboard/*.json`: regenerate from current results; do not treat as archival records
- `results/.jobs-history.json`: short-lived operator history only
- `results/local-audit-log.json` and `dashboard/local-audit-log.json`: operational visibility only
- `config/task-queue.yaml`: retain while work remains active; prune cancelled/done items during normal maintenance

Operational rule:

1. Do not retain audit findings longer than operationally useful.
2. If findings contain personal data, secrets, or regulated content, delete or regenerate the affected result artifacts after remediation.
3. Do not commit generated result artifacts containing sensitive evidence into Git.

## Privacy And Transparency

Back Office is an internal control-plane tool. The operator-facing transparency model is:

- findings are visible in the dashboard with provenance and evidence
- approval actions are visible in queue history
- draft PR creation is explicit and attributable
- local and published artifacts should be treated as sensitive operational material

When used inside a team or customer environment, operators should disclose:

- which repos are being scanned
- which departments are enabled
- where findings are stored
- whether any dashboard artifacts are published outside the local machine
- who can approve queued work

## Storage Controls

- S3 dashboard uploads use explicit server-side encryption (`AES256`)
- CloudFront invalidations are bounded to wildcard paths to prevent unbounded cost
- local remote-publish, auto-fix, and unattended workflows are disabled by default unless explicitly enabled

## Secrets And Credentials

- local config files under `config/*.yaml` are ignored by Git
- `config/backoffice.yaml`, `config/targets.yaml`, and `config/task-queue.yaml` are local operational files
- production or CI credentials should be sourced from AWS-managed secret stores or CI secret injection, not committed config

## Incident Handling

If sensitive data appears in findings or dashboard artifacts:

1. stop any publish path
2. remove or regenerate the affected result and dashboard files
3. rotate exposed credentials if applicable
4. review the target repo and prompt path that surfaced the sensitive material
5. document the follow-up in repo handoff or incident notes
