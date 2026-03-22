"""Provider factory."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backoffice.config import Config

from backoffice.sync.providers.base import CDNProvider, StorageProvider


def get_providers(config: "Config") -> tuple[StorageProvider, CDNProvider]:
    """Create storage and CDN providers from config."""
    provider = config.deploy.provider
    if provider == "aws":
        from backoffice.sync.providers.aws import AWSCloudFront, AWSStorage
        region = config.deploy.aws.region
        return AWSStorage(region), AWSCloudFront(region)
    raise ValueError(f"Unknown deploy provider: {provider}")
