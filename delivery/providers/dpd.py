"""DPD провайдер доставки: simulation / omniva-test-proxy / real."""

import logging
import httpx

from configs import configs
from models import DeliveryCreate
from providers.base import DeliveryProviderClient


logger = logging.getLogger(__name__)


class DPDProviderClient(DeliveryProviderClient):
    def get_provider_name(self) -> str:
        return "dpd"

    def create_shipment(self, delivery_data: DeliveryCreate) -> str:
        mode = configs.get_dpd_mode()
        if mode == "simulation":
            return self._simulate(delivery_data)
        if mode == "omniva_test_proxy":
            return self._proxy_to_omniva_test(delivery_data)
        return self._create_real(delivery_data)

    def _simulate(self, delivery_data: DeliveryCreate) -> str:
        logger.info(
            f"DPD simulation mode | order_id={delivery_data.order_id} | pickup_point={delivery_data.pickup_point_id}"
        )
        return "dpd_simulation"

    def _proxy_to_omniva_test(self, delivery_data: DeliveryCreate) -> str:
        endpoint = f"{configs.OMNIVA_TEST_API_BASE_URL}/shipments/business-to-client"
        payload = {
            "customerCode": "DPD-INNER-SIM",
            "fileId": f"ORDER-{delivery_data.order_id}",
            "shipments": [
                {
                    "partnerShipmentId": str(delivery_data.order_id),
                    "mainService": "PARCEL",
                    "deliveryChannel": "PARCEL_MACHINE",
                    "receiverAddressee": {
                        "personName": delivery_data.recipient_name,
                        "contactMobile": delivery_data.recipient_phone,
                        "contactEmail": delivery_data.recipient_email,
                        "address": {
                            "country": (delivery_data.delivery_country or "LV")[:2].upper(),
                            "deliverypoint": delivery_data.delivery_city or "Riga",
                            "postcode": delivery_data.delivery_zip or "LV-1001",
                            "street": delivery_data.delivery_address or "Pickup point",
                        },
                    },
                    "senderAddressee": {
                        "personName": delivery_data.sender_name,
                        "contactMobile": delivery_data.sender_phone,
                        "address": {
                            "country": "LV",
                            "deliverypoint": "Riga",
                            "postcode": "LV-1001",
                        },
                    },
                }
            ],
        }

        with httpx.Client(timeout=8.0) as client:
            response = client.post(endpoint, json=payload)
            logger.info(
                f"DPD->Omniva test proxy call | order_id={delivery_data.order_id} | status={response.status_code}"
            )

        return "omniva_test_proxy"

    def _create_real(self, delivery_data: DeliveryCreate) -> str:
        if not configs.DPD_API_KEY or not configs.DPD_API_SECRET:
            raise ValueError("DPD credentials are not configured for real mode")

        endpoint = f"{configs.DPD_REAL_API_BASE_URL}/shipments"
        payload = {
            "senderAddress": {
                "name": delivery_data.sender_name,
                "phone": delivery_data.sender_phone,
                "email": delivery_data.recipient_email,
                "pudoId": delivery_data.pickup_point_id,
            },
            "receiverAddress": {
                "name": delivery_data.recipient_name,
                "phone": delivery_data.recipient_phone,
                "email": delivery_data.recipient_email,
                "pudoId": delivery_data.pickup_point_id,
            },
            "service": {"serviceAlias": "DPD Pickup"},
            "parcels": [{"weight": 1.0}],
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                endpoint,
                json=payload,
                auth=(configs.DPD_API_KEY, configs.DPD_API_SECRET),
            )
            if response.status_code not in (200, 201):
                raise ValueError(f"DPD real API failed with status {response.status_code}")
            logger.info(f"DPD real API call success | order_id={delivery_data.order_id}")

        return "dpd_real"
