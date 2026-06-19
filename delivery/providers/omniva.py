"""Omniva провайдер (заготовка для расширения)."""

from typing import Any, Dict

from models import DeliveryCreate
from providers.base import DeliveryProviderClient


class OmnivaProviderClient(DeliveryProviderClient):
    def get_provider_name(self) -> str:
        return "omniva"

    def create_shipment(self, delivery_data: DeliveryCreate) -> str:
        # Текущая интеграция Omniva реализуется внутренней логикой доставки.
        # Модуль выделен, чтобы проще добавить real/test API без правок DeliveryService.
        return "omniva_internal"
    
    def get_tracking_status(self, parcel_number: str) -> Dict[str, Any]:
        pass
