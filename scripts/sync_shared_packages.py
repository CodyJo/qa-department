#!/usr/bin/env python3
"""Sync shared frontend packages into app-local vendor directories.

Keeps /home/merm/projects/shared/packages as the source of truth while
preserving self-contained app repos that still build from vendored copies.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PROJECTS_ROOT = Path('/home/merm/projects')
SHARED_ROOT = PROJECTS_ROOT / 'shared' / 'packages'
DEFAULT_TARGETS = {
    'fuel': ['api-client', 'app-config', 'app-shell', 'auth', 'crypto', 'theme', 'ui', 'whats-new'],
    'certstudy': ['api-client', 'app-config', 'app-shell', 'auth', 'crypto', 'storage', 'theme', 'ui', 'whats-new'],
    'selah': ['account-sync', 'app-config', 'app-shell', 'auth', 'crypto', 'storage', 'theme', 'ui', 'whats-new'],
    'thenewbeautifulme': ['api-client', 'auth', 'crypto', 'theme', 'ui', 'whats-new'],
    'pattern': ['auth'],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='*', help='Specific app targets to sync')
    parser.add_argument('--dry-run', action='store_true', help='Show planned work without copying files')
    return parser.parse_args()



def sync_package(target_root: Path, package_name: str, dry_run: bool) -> None:
    source = SHARED_ROOT / package_name
    if not source.exists():
        raise SystemExit(f'missing shared package: {source}')

    destination = target_root / 'vendor' / 'shared-packages' / package_name
    print(f'{source} -> {destination}')
    if dry_run:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)



def main() -> int:
    args = parse_args()
    targets = args.targets or list(DEFAULT_TARGETS)
    for target in targets:
        if target not in DEFAULT_TARGETS:
            raise SystemExit(f'unknown target: {target}')
        target_root = PROJECTS_ROOT / target
        for package_name in DEFAULT_TARGETS[target]:
            sync_package(target_root, package_name, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
