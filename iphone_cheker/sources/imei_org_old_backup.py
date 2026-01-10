"""IMEI.org API Integration"""
import httpx
from typing import Optional, Dict, Any
import logging
from .base import IMEISource


class IMEIorgSource(IMEISource):
    """
    Интеграция с IMEI.org Custom API
    
    Документация: https://www.imei.org/api-connect/
    Использует GET запросы с query параметрами (не Dhru API)
    """
    
    BASE_URL = "https://api-client.imei.org/api"
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.logger = logging.getLogger("IMEIorgSource")
        
        if not api_key:
            raise ValueError("IMEI.org API key is required")
        
        # Service IDs - получить актуальные можно через /api/services
        # Могут отличаться в зависимости от аккаунта
        self.service_id_basic = 30  # Apple Carrier + GSMA Blacklist Check
        self.service_id_warranty = 171  # Apple Advanced Check
        
        self.logger.info(f"✅ IMEI.org source initialized with Custom API")
    
    async def check_warranty(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Warranty Check через IMEI.org Custom API
        
        Service ID: 171 (Apple Advanced Check)
        Стоимость: ~$0.15 за запрос
        """
        try:
            # Custom API использует GET с query параметрами
            url = f"{self.BASE_URL}/submit"
            params = {
                "apikey": self.api_key,
                "service_id": self.service_id_warranty,
                "input": imei
            }
            
            self.logger.info(f"IMEI.org request to: {url}")
            self.logger.info(f"IMEI.org params: service_id={self.service_id_warranty}, input={imei}, apikey=***")
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                
                self.logger.info(f"IMEI.org response status: {response.status_code}")
                self.logger.info(f"IMEI.org response body: {response.text[:500]}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Проверка статуса
                    if data.get("status") != 1:
                        error_msg = data.get("message", "Unknown error")
                        self.logger.error(f"IMEI.org API error: {error_msg}")
                        return None
                    
                    # Custom API возвращает данные в поле "response"
                    result = data.get("response", {})
                    return self._normalize_warranty_response(result)
                
                elif response.status_code == 401:
                    self.logger.error("IMEI.org: Invalid API key")
                    return None
                
                elif response.status_code == 402:
                    self.logger.error("IMEI.org: Insufficient credits")
                    return None
                
                elif response.status_code == 404:
                    self.logger.warning(f"IMEI.org: Device not found - {imei}")
                    return None
                
                else:
                    self.logger.error(f"IMEI.org API error: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            self.logger.error("IMEI.org: Request timeout")
            return None
        except Exception as e:
            self.logger.error(f"IMEI.org error: {e}")
            return None
    
    async def check_basic(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Basic Check через IMEI.org Custom API
        
        Service ID: 30 (Apple Carrier + GSMA Blacklist Check)
        Стоимость: ~$0.05 за запрос
        """
        try:
            # Custom API использует GET с query параметрами
            url = f"{self.BASE_URL}/submit"
            params = {
                "apikey": self.api_key,
                "service_id": self.service_id_basic,
                "input": imei
            }
            
            self.logger.info(f"IMEI.org request to: {url}")
            self.logger.info(f"IMEI.org params: service_id={self.service_id_basic}, input={imei}, apikey=***")
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                
                self.logger.info(f"IMEI.org response status: {response.status_code}")
                self.logger.info(f"IMEI.org response body: {response.text[:500]}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Проверка статуса
                    if data.get("status") != 1:
                        error_msg = data.get("message", "Unknown error")
                        self.logger.error(f"IMEI.org API error: {error_msg}")
                        return None
                    
                    # Custom API возвращает данные в поле "response"
                    result = data.get("response", {})
                    return self._normalize_basic_response(result)
                
                elif response.status_code == 401:
                    self.logger.error("IMEI.org: Invalid API key")
                    return None
                
                elif response.status_code == 402:
                    self.logger.error("IMEI.org: Insufficient credits")
                    return None
                
                elif response.status_code == 404:
                    self.logger.warning(f"IMEI.org: Device not found - {imei}")
                    return None
                
                else:
                    self.logger.error(f"IMEI.org API error: {response.status_code}")
                    return None
                    
        except httpx.TimeoutException:
            self.logger.error("IMEI.org: Request timeout")
            return None
        except Exception as e:
            self.logger.error(f"IMEI.org error: {e}")
            return None
    
    def get_source_name(self) -> str:
        return "imei.org"
    
    def _normalize_warranty_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа warranty в единый формат"""
        # Dhru API может возвращать разные структуры в зависимости от сервиса
        # Адаптируем под наиболее распространенный формат
        
        return {
            "imei": data.get("imei", data.get("IMEI")),
            "model": data.get("model", data.get("Model", data.get("Description"))),
            "memory": self._extract_memory(data.get("capacity", data.get("Capacity", data.get("memory")))),
            "color": data.get("color", data.get("Color")),
            "serial_number": data.get("serial", data.get("Serial", data.get("serialNumber"))),
            "purchase_date": data.get("purchaseDate", data.get("Purchase Date")),
            "warranty_status": data.get("warrantyStatus", data.get("Warranty Status")),
            "warranty_end_date": data.get("warrantyExpiration", data.get("Warranty Expiration")),
            "find_my_iphone": self._parse_bool(data.get("findMyIphone", data.get("Find My iPhone", data.get("fmi")))),
            "activation_lock": self._parse_bool(data.get("activationLock", data.get("Activation Lock", data.get("icloud")))),
            "icloud_status": data.get("icloudStatus", data.get("iCloud Status")),
            "simlock": self._parse_bool(data.get("simlock", data.get("Simlock", data.get("locked")))),
            "carrier": data.get("carrier", data.get("Carrier", data.get("initialCarrier"))),
            "country": data.get("country", data.get("Country")),
            "activated": self._parse_bool(data.get("activated", data.get("Activated"))),
            "activation_date": data.get("activationDate", data.get("Activation Date")),
        }
    
    def _normalize_basic_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа basic в единый формат"""
        
        return {
            "imei": data.get("imei", data.get("IMEI")),
            "model": data.get("model", data.get("Model", data.get("Description"))),
            "memory": self._extract_memory(data.get("capacity", data.get("Capacity", data.get("memory")))),
            "color": data.get("color", data.get("Color")),
            "find_my_iphone": self._parse_bool(data.get("findMyIphone", data.get("Find My iPhone", data.get("fmi")))),
            "activation_lock": self._parse_bool(data.get("activationLock", data.get("Activation Lock", data.get("icloud")))),
            "icloud_status": data.get("icloudStatus", data.get("iCloud Status")),
            "simlock": self._parse_bool(data.get("simlock", data.get("Simlock", data.get("locked")))),
            "carrier": data.get("carrier", data.get("Carrier")),
            "country": data.get("country", data.get("Country")),
        }
    
    def _parse_bool(self, value: Any) -> bool:
        """Парсинг булевых значений из разных форматов"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('yes', 'true', '1', 'on', 'enabled')
        if isinstance(value, int):
            return value == 1
        return False
    
    def _extract_memory(self, capacity: Optional[str]) -> Optional[str]:
        """Извлечение объема памяти"""
        if not capacity:
            return None
        
        capacity_str = str(capacity).strip()
        
        # Если уже в формате "128GB"
        if "GB" in capacity_str.upper() or "TB" in capacity_str.upper():
            return capacity_str.upper()
        
        # Если только число (предполагаем GB)
        import re
        match = re.search(r'(\d+)', capacity_str)
        if match:
            return f"{match.group(1)}GB"
        
        return None

    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.logger = logging.getLogger("IMEIorgSource")
        
        if not api_key:
            raise ValueError("IMEI.org (NumberingPlans) API key is required")
    
    async def check_warranty(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Warranty Check через NumberingPlans API
        
        Endpoint: /v1/apple/warranty
        Стоимость: ~$0.08 за запрос
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/v1/apple/warranty",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={"imei": imei}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Проверка успешности
                    if not data.get("success", False):
                        error_msg = data.get("error", {}).get("message", "Unknown error")
                        self.logger.error(f"IMEI.org API error: {error_msg}")
                        return None
                    
                    result = data.get("data", {})
                    return self._normalize_warranty_response(result)
                
                elif response.status_code == 401:
                    self.logger.error("IMEI.org: Invalid API key")
                    return None
                
                elif response.status_code == 402:
                    self.logger.error("IMEI.org: Payment required (insufficient credits)")
                    return None
                
                elif response.status_code == 404:
                    self.logger.warning(f"IMEI.org: Device not found - {imei}")
                    return None
                
                elif response.status_code == 429:
                    self.logger.error("IMEI.org: Rate limit exceeded")
                    return None
                
                else:
                    self.logger.error(f"IMEI.org API error: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            self.logger.error("IMEI.org: Request timeout")
            return None
        except Exception as e:
            self.logger.error(f"IMEI.org error: {e}")
            return None
    
    async def check_basic(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Basic Check через NumberingPlans API
        
        Endpoint: /v1/apple/basic
        Стоимость: ~$0.04 за запрос
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/v1/apple/basic",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={"imei": imei}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if not data.get("success", False):
                        error_msg = data.get("error", {}).get("message", "Unknown error")
                        self.logger.error(f"IMEI.org API error: {error_msg}")
                        return None
                    
                    result = data.get("data", {})
                    return self._normalize_basic_response(result)
                
                elif response.status_code == 401:
                    self.logger.error("IMEI.org: Invalid API key")
                    return None
                
                elif response.status_code == 402:
                    self.logger.error("IMEI.org: Payment required (insufficient credits)")
                    return None
                
                elif response.status_code == 404:
                    self.logger.warning(f"IMEI.org: Device not found - {imei}")
                    return None
                
                elif response.status_code == 429:
                    self.logger.error("IMEI.org: Rate limit exceeded")
                    return None
                
                else:
                    self.logger.error(f"IMEI.org API error: {response.status_code}")
                    return None
                    
        except httpx.TimeoutException:
            self.logger.error("IMEI.org: Request timeout")
            return None
        except Exception as e:
            self.logger.error(f"IMEI.org error: {e}")
            return None
    
    def get_source_name(self) -> str:
        return "imei.org"
    
    def _normalize_warranty_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа warranty в единый формат"""
        device = data.get("device", {})
        warranty = data.get("warranty", {})
        status = data.get("status", {})
        
        return {
            "imei": data.get("imei"),
            "model": device.get("name", device.get("model")),
            "memory": self._extract_memory(device.get("capacity")),
            "color": device.get("color"),
            "serial_number": data.get("serialNumber"),
            "purchase_date": warranty.get("purchaseDate"),
            "warranty_status": warranty.get("status"),
            "warranty_end_date": warranty.get("expirationDate"),
            "find_my_iphone": status.get("findMyIphone", status.get("fmi", False)),
            "activation_lock": status.get("activationLock", status.get("icloud", False)),
            "icloud_status": status.get("icloudStatus"),
            "simlock": status.get("simlock", status.get("locked", False)),
            "carrier": status.get("carrier", status.get("initialCarrier")),
            "country": status.get("country", data.get("countryCode")),
            "activated": status.get("activated", False),
            "activation_date": status.get("activationDate"),
        }
    
    def _normalize_basic_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа basic в единый формат"""
        device = data.get("device", {})
        status = data.get("status", {})
        
        return {
            "imei": data.get("imei"),
            "model": device.get("name", device.get("model")),
            "memory": self._extract_memory(device.get("capacity")),
            "color": device.get("color"),
            "find_my_iphone": status.get("findMyIphone", status.get("fmi", False)),
            "activation_lock": status.get("activationLock", status.get("icloud", False)),
            "icloud_status": status.get("icloudStatus"),
            "simlock": status.get("simlock", status.get("locked", False)),
            "carrier": status.get("carrier", status.get("initialCarrier")),
            "country": status.get("country", data.get("countryCode")),
        }
    
    def _extract_memory(self, capacity: Optional[str]) -> Optional[str]:
        """Извлечение объема памяти"""
        if not capacity:
            return None
        
        capacity_str = str(capacity).strip()
        
        # Если уже в формате "128GB"
        if "GB" in capacity_str.upper() or "TB" in capacity_str.upper():
            return capacity_str.upper()
        
        # Если только число (предполагаем GB)
        import re
        match = re.search(r'(\d+)', capacity_str)
        if match:
            return f"{match.group(1)}GB"
        
        return None
