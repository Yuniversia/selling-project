"""Базовый интерфейс провайдера доставки."""

from abc import ABC, abstractmethod
from models import DeliveryCreate
from typing import Optional


class DeliveryProviderClient(ABC):
    """Абстракция интеграции с конкретной службой доставки."""

    @abstractmethod
    def create_shipment(self, delivery_data: DeliveryCreate) -> str:
        """Создать отправление во внешней/внутренней системе.

        Returns:
            str: техническая метка режима интеграции (для notes/audit)
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_tracking_status(self, provider_tracking_number: str) -> Optional[str]:
        """Запросить статус у стороннего API и вернуть ВНУТРЕННИЙ статус (DeliveryStatus)"""
        raise NotImplementedError

    @abstractmethod
    def get_provider_name(self) -> str:
        raise NotImplementedError
