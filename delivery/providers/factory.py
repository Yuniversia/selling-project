"""Фабрика провайдеров доставки."""

from typing import Dict, Optional

from providers.base import DeliveryProviderClient
from providers.dpd import DPDProviderClient
from providers.omniva import OmnivaProviderClient


class DeliveryProviderFactory:
    def __init__(self):
        self._providers: Dict[str, DeliveryProviderClient] = {
            "dpd": DPDProviderClient(),
            "omniva": OmnivaProviderClient(),
        }

    def get(self, provider_name: str) -> Optional[DeliveryProviderClient]:
        if not provider_name:
            return None
        return self._providers.get(provider_name.strip().lower())
