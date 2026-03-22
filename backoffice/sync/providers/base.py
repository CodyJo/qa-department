"""Abstract base classes for storage and CDN providers."""
from abc import ABC, abstractmethod


class StorageProvider(ABC):
    @abstractmethod
    def upload_file(self, bucket: str, local_path: str, remote_key: str,
                    content_type: str, cache_control: str) -> None:
        """Upload a single file to a bucket/container."""

    @abstractmethod
    def upload_files(self, file_mappings: list[dict]) -> None:
        """Upload multiple files. Each mapping has: bucket, local_path,
        remote_key, content_type, cache_control."""

    @abstractmethod
    def sync_directory(self, bucket: str, local_dir: str,
                       remote_prefix: str, delete: bool = False) -> None:
        """Sync a local directory to a remote prefix. Used for regression logs."""


class CDNProvider(ABC):
    @abstractmethod
    def invalidate(self, distribution_id: str, paths: list[str]) -> None:
        """Invalidate the given paths for a specific distribution/zone."""
