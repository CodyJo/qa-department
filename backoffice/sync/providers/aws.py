"""AWS S3 + CloudFront provider implementation."""
from __future__ import annotations

import logging
import time
from pathlib import Path, PurePosixPath

from backoffice.sync.providers.base import CDNProvider, StorageProvider

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 1


def _retry(fn, *args, **kwargs):
    """Retry fn up to MAX_RETRIES times with exponential backoff."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                wait = BACKOFF_BASE * (2 ** attempt)
                logger.warning("Retry %d/%d after %.1fs: %s",
                             attempt + 1, MAX_RETRIES, wait, exc)
                time.sleep(wait)
    raise last_exc


class AWSStorage(StorageProvider):
    def __init__(self, region: str):
        import boto3
        self._s3 = boto3.client("s3", region_name=region)

    def upload_file(self, bucket: str, local_path: str, remote_key: str,
                    content_type: str, cache_control: str) -> None:
        def _do_upload():
            self._s3.upload_file(
                local_path, bucket, remote_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "CacheControl": cache_control,
                    "ServerSideEncryption": "AES256",
                },
            )
        _retry(_do_upload)
        logger.info("Uploaded %s -> s3://%s/%s", Path(local_path).name, bucket, remote_key)

    def upload_files(self, file_mappings: list[dict]) -> None:
        for m in file_mappings:
            self.upload_file(
                m["bucket"], m["local_path"], m["remote_key"],
                m["content_type"], m["cache_control"],
            )

    def sync_directory(self, bucket: str, local_dir: str,
                       remote_prefix: str, delete: bool = False) -> None:
        import subprocess
        s3_uri = f"s3://{bucket}/{remote_prefix}" if remote_prefix else f"s3://{bucket}"
        cmd = ["aws", "s3", "sync", local_dir, s3_uri]
        if delete:
            cmd.append("--delete")
        cmd.extend(["--cache-control", "no-cache, no-store, must-revalidate", "--sse", "AES256"])
        logger.info("Syncing %s -> %s", local_dir, s3_uri)
        subprocess.run(cmd, check=True)


class AWSCloudFront(CDNProvider):
    def __init__(self, region: str):
        import boto3
        self._cf = boto3.client("cloudfront", region_name=region)

    def invalidate(self, distribution_id: str, paths: list[str]) -> None:
        if not distribution_id or not paths:
            return
        normalized_paths = _normalize_invalidation_paths(paths)
        import time as _time
        caller_ref = str(int(_time.time() * 1000))
        try:
            self._cf.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    "Paths": {
                        "Quantity": len(normalized_paths),
                        "Items": normalized_paths,
                    },
                    "CallerReference": caller_ref,
                },
            )
            logger.info("Invalidated %d paths on %s", len(normalized_paths), distribution_id)
        except Exception as exc:
            logger.warning("CloudFront invalidation failed for %s: %s",
                         distribution_id, exc)


def _normalize_invalidation_paths(paths: list[str]) -> list[str]:
    """Collapse expensive multi-path invalidations to a single wildcard.

    CloudFront charges per invalidated path. Back Office only needs a
    namespace-level refresh, so any multi-path batch should be reduced to one
    wildcard before it reaches AWS.
    """
    cleaned = []
    for path in paths:
        if not path:
            continue
        normalized = path if path.startswith("/") else f"/{path}"
        cleaned.append(normalized)

    if not cleaned:
        return []

    unique_paths = sorted(set(cleaned))
    if len(unique_paths) == 1:
        return unique_paths

    directory_parts = []
    for path in unique_paths:
        if path == "/*":
            continue
        parts = PurePosixPath(path).parts[1:-1]
        directory_parts.append(parts)

    if not directory_parts:
        return ["/*"]

    shared_parts = list(directory_parts[0])
    for parts in directory_parts[1:]:
        limit = min(len(shared_parts), len(parts))
        index = 0
        while index < limit and shared_parts[index] == parts[index]:
            index += 1
        shared_parts = shared_parts[:index]
        if not shared_parts:
            break

    if not shared_parts:
        collapsed = "/*"
    else:
        collapsed = f"/{'/'.join(shared_parts)}/*"

    logger.warning(
        "Collapsing %d CloudFront invalidation paths to %s to avoid per-path charges",
        len(unique_paths),
        collapsed,
    )
    return [collapsed]
