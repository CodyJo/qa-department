"""AWS S3 + CloudFront provider implementation."""
from __future__ import annotations

import logging
import time
from pathlib import Path

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
        cmd.extend(["--cache-control", "no-cache, no-store, must-revalidate"])
        logger.info("Syncing %s -> %s", local_dir, s3_uri)
        subprocess.run(cmd, check=True)


class AWSCloudFront(CDNProvider):
    def __init__(self, region: str):
        import boto3
        self._cf = boto3.client("cloudfront", region_name=region)

    def invalidate(self, distribution_id: str, paths: list[str]) -> None:
        if not distribution_id or not paths:
            return
        import time as _time
        caller_ref = str(int(_time.time() * 1000))
        try:
            self._cf.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    "Paths": {"Quantity": len(paths), "Items": paths},
                    "CallerReference": caller_ref,
                },
            )
            logger.info("Invalidated %d paths on %s", len(paths), distribution_id)
        except Exception as exc:
            logger.warning("CloudFront invalidation failed for %s: %s",
                         distribution_id, exc)
