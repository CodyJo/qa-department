"""Tests for backoffice.sync.providers."""
from __future__ import annotations

import subprocess

import pytest

from backoffice.sync.providers.aws import AWSStorage, _normalize_invalidation_paths
from backoffice.sync.providers.base import CDNProvider, StorageProvider


def test_storage_provider_is_abstract():
    with pytest.raises(TypeError):
        StorageProvider()


def test_cdn_provider_is_abstract():
    with pytest.raises(TypeError):
        CDNProvider()


class FakeStorage(StorageProvider):
    def __init__(self):
        self.uploads = []

    def upload_file(self, bucket, local_path, remote_key, content_type, cache_control):
        self.uploads.append((bucket, local_path, remote_key, content_type))

    def upload_files(self, file_mappings):
        for m in file_mappings:
            self.upload_file(m["bucket"], m["local_path"], m["remote_key"],
                           m["content_type"], m["cache_control"])

    def sync_directory(self, bucket, local_dir, remote_prefix, delete=False):
        pass


class FakeCDN(CDNProvider):
    def __init__(self):
        self.invalidations = []

    def invalidate(self, distribution_id, paths):
        self.invalidations.append({"dist": distribution_id, "paths": paths})


def test_fake_storage_satisfies_interface():
    s = FakeStorage()
    s.upload_file("my-bucket", "/tmp/a.html", "a.html", "text/html", "no-cache")
    assert len(s.uploads) == 1


def test_fake_cdn_satisfies_interface():
    c = FakeCDN()
    c.invalidate("EXXXXX", ["/index.html"])
    assert len(c.invalidations) == 1


def test_normalize_invalidation_paths_keeps_single_path():
    assert _normalize_invalidation_paths(["/back-office/dashboard/*"]) == [
        "/back-office/dashboard/*"
    ]


def test_normalize_invalidation_paths_collapses_root_file_batch():
    assert _normalize_invalidation_paths([
        "/index.html",
        "/qa-data.json",
        "/org-data.json",
    ]) == ["/*"]


def test_normalize_invalidation_paths_collapses_prefixed_file_batch():
    assert _normalize_invalidation_paths([
        "/back-office/dashboard/index.html",
        "/back-office/dashboard/qa-data.json",
        "/back-office/dashboard/backlog.json",
    ]) == ["/back-office/dashboard/*"]


def test_aws_upload_file_sets_sse(monkeypatch, tmp_path):
    uploads = []

    class FakeS3:
        def upload_file(self, local_path, bucket, remote_key, ExtraArgs):
            uploads.append({
                "local_path": local_path,
                "bucket": bucket,
                "remote_key": remote_key,
                "extra": ExtraArgs,
            })

    import boto3

    monkeypatch.setattr(boto3, "client", lambda service, region_name=None: FakeS3())
    local_file = tmp_path / "index.html"
    local_file.write_text("<html></html>")

    storage = AWSStorage(region="us-west-2")
    storage.upload_file("bucket", str(local_file), "index.html", "text/html", "no-cache")

    assert uploads[0]["extra"]["ServerSideEncryption"] == "AES256"


def test_aws_sync_directory_sets_sse(monkeypatch):
    captured = {}

    def fake_run(cmd, check):
        captured["cmd"] = cmd
        captured["check"] = check
        return 0

    monkeypatch.setattr(subprocess, "run", fake_run)

    class FakeS3:
        pass

    import boto3

    monkeypatch.setattr(boto3, "client", lambda service, region_name=None: FakeS3())

    storage = AWSStorage(region="us-west-2")
    storage.sync_directory("bucket", "/tmp/local", "prefix", delete=True)

    assert "--sse" in captured["cmd"]
    assert "AES256" in captured["cmd"]
