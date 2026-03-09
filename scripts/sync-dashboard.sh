#!/usr/bin/env bash
# Sync dashboard data to S3 and deploy qa.html
# Usage: ./scripts/sync-dashboard.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QA_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG="$QA_ROOT/config/qa-config.yaml"

if [ ! -f "$CONFIG" ]; then
  echo "No config at $CONFIG — copy from qa-config.example.yaml" >&2
  exit 1
fi

# ── Aggregate all results into a single dashboard payload ────────────────────

echo "Aggregating results..."
python3 "$SCRIPT_DIR/aggregate-results.py" "$QA_ROOT/results" "$QA_ROOT/dashboard/data.json"

# ── Read deployment targets from config ──────────────────────────────────────

python3 -c "
import yaml, subprocess, sys

with open('$CONFIG') as f:
    cfg = yaml.safe_load(f)

targets = cfg.get('dashboard_targets', [])
if not targets:
    print('No dashboard_targets in config', file=sys.stderr)
    sys.exit(0)

for t in targets:
    bucket = t['bucket']
    path = t.get('path', 'qa.html')
    cf_id = t.get('cloudfront_id', '')

    print(f'Deploying qa.html to s3://{bucket}/{path}')
    subprocess.run([
        'aws', 's3', 'cp', '$QA_ROOT/dashboard/qa.html',
        f's3://{bucket}/{path}',
        '--content-type', 'text/html',
        '--cache-control', 'no-cache, no-store, must-revalidate'
    ], check=True)

    # Upload data.json alongside
    data_path = path.rsplit('/', 1)
    data_key = (data_path[0] + '/' if len(data_path) > 1 else '') + 'qa-data.json'
    print(f'Deploying data to s3://{bucket}/{data_key}')
    subprocess.run([
        'aws', 's3', 'cp', '$QA_ROOT/dashboard/data.json',
        f's3://{bucket}/{data_key}',
        '--content-type', 'application/json',
        '--cache-control', 'no-cache, no-store, must-revalidate'
    ], check=True)

    if cf_id:
        print(f'Invalidating CloudFront {cf_id}')
        subprocess.run([
            'aws', 'cloudfront', 'create-invalidation',
            '--distribution-id', cf_id,
            '--paths', f'/{path}', f'/{data_key}'
        ], check=True)

print('Dashboard sync complete.')
"
