from __future__ import annotations

import importlib.util
from pathlib import Path


def load_module():
    script_path = Path(__file__).resolve().parents[1] / 'scripts' / 'sync_shared_packages.py'
    spec = importlib.util.spec_from_file_location('sync_shared_packages', script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_default_targets_cover_expected_apps():
    module = load_module()

    assert set(module.DEFAULT_TARGETS) == {
        'fuel',
        'certstudy',
        'selah',
        'thenewbeautifulme',
        'pattern',
    }
    assert 'auth' in module.DEFAULT_TARGETS['fuel']
    assert 'storage' in module.DEFAULT_TARGETS['certstudy']
    assert 'account-sync' in module.DEFAULT_TARGETS['selah']


def test_sync_package_creates_vendor_copy(tmp_path):
    module = load_module()

    source_root = tmp_path / 'shared'
    source_pkg = source_root / 'auth'
    source_pkg.mkdir(parents=True)
    (source_pkg / 'package.json').write_text('{"name":"@codyjo/auth"}')

    target_root = tmp_path / 'fuel'

    original_shared_root = module.SHARED_ROOT
    module.SHARED_ROOT = source_root
    try:
        module.sync_package(target_root, 'auth', dry_run=False)
    finally:
        module.SHARED_ROOT = original_shared_root

    copied = target_root / 'vendor' / 'shared-packages' / 'auth' / 'package.json'
    assert copied.exists()
    assert copied.read_text() == '{"name":"@codyjo/auth"}'
