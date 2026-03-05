import httpx
from typing import Optional, Dict, Any
import logging
from .base import IMEISource
import re
from datetime import datetime

class IMEIcheckSource(IMEISource):
    """
    Интеграция с IMEIcheck.net Custom API
    
    Документация: https://imeicheck.net/developer-api
    Использует GET запросы с query параметрами (не Dhru API)
    """
    
    BASE_URL = "https://api.imeicheck.net/v1/checks"
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.logger = logging.getLogger("IMEIcheckSource")
        
        if not api_key:
            raise ValueError("IMEIcheck.net API key is required")
        

        self.service_id_basic = 1  # Apple Basic Check - $0.06
        self.service_id_warranty = 2  # Apple Warranty Status Check - $0.12

        
        self.logger.info(f"✅ IMEIcheck.net source initialized with Custom API")
    
    async def check_warranty(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Warranty Check через IMEIcheck.net Custom API
        4 (Apple Warranty Status Check)
        Стоимость: $0.06Apple Advanced Check)
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
            
            self.logger.info(f"IMEIcheck.net request to: {url}")
            self.logger.info(f"IMEIcheck.net params: service_id={self.service_id_warranty}, input={imei}, apikey=***")
            
            async with httpx.AsyncClient(timeout=60.0) as client:  # Увеличено до 60 секунд
                self.logger.info("IMEIcheck.net: Sending request...")
                response = await client.get(url, params=params)
                self.logger.info(f"IMEIcheck.net: Response received!")
                
                self.logger.info(f"IMEIcheck.net response status: {response.status_code}")
                self.logger.info(f"IMEIcheck.net response body: {response.text[:800]}")
                
                if response.status_code == 200 or response.status_code == 201:
                    data = response.json()
                    
                    # Проверка статуса ответа Custom API
                    if data.get("status") != "successful":
                        error_msg = data.get("message") or data.get("error") or "Unknown error"
                        self.logger.error(f"IMEIcheck.net API error: {error_msg}")
                        return None

                    # В новом формате полезные данные находятся в "properties"
                    result = data.get("properties")
                    if not isinstance(result, dict) or not result:
                        self.logger.error("IMEIcheck.net: No properties in response")
                        return None

                    # Доп. проверка целостности ответа
                    if not result.get("imei"):
                        self.logger.error("IMEIcheck.net: IMEI is missing in properties")
                        return None
                    
                    return self._normalize_warranty_response(result)
                
                elif response.status_code == 401:
                    self.logger.error("IMEIcheck.net: Invalid API key")
                    return None
                
                elif response.status_code == 402:
                    self.logger.error("IMEIcheck.net: Insufficient credits")
                    return None
                
                elif response.status_code == 404:
                    self.logger.warning(f"IMEIcheck.net: Device not found - {imei}")
                    return None
                
                else:
                    self.logger.error(f"IMEIcheck.net API error: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException as e:
            self.logger.error(f"IMEIcheck.net: Request timeout after 60s - {str(e)}")
            return None
        except httpx.ConnectError as e:
            self.logger.error(f"IMEIcheck.net: Connection error - {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            self.logger.error(f"IMEIcheck.net: HTTP error - {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"IMEIcheck.net check_warranty error: {type(e).__name__} - {str(e)}")
            return None
    
    async def check_basic(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Basic Check через IMEIcheck.net Custom API
        
        Service ID: 1 (Apple Basic Check)
        Стоимость: $0.06 за запрос
        """
        try:
            # Custom API использует GET с query параметрами
            url = f"{self.BASE_URL}"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            body = {
                "serviceId": self.service_id_basic,
                "deviceId": imei
            }
            
            self.logger.info(f"IMEIcheck.net request to: {url}")
            self.logger.info(f"IMEIcheck.net body: serviceId={self.service_id_basic}, deviceId={imei}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                self.logger.info("IMEIcheck.net: Sending request...")
                response = await client.post(url, headers=headers, json=body)
                self.logger.info(f"IMEIcheck.net: Response received!")
                
                self.logger.info(f"IMEIcheck.net response status: {response.status_code}")
                self.logger.info(f"IMEIcheck.net response body: {response.text[:800]}")
                
                if response.status_code == 200 or response.status_code == 201:
                    data = response.json()
                    
                     # Проверка статуса ответа Custom API
                    if data.get("status") != "successful":
                        error_msg = data.get("message") or data.get("error") or "Unknown error"
                        self.logger.error(f"IMEIcheck.net API error: {error_msg}")
                        return None

                    # В новом формате полезные данные находятся в "properties"
                    result = data.get("properties")
                    if not isinstance(result, dict) or not result:
                        self.logger.error("IMEIcheck.net: No properties in response")
                        return None

                    # Доп. проверка целостности ответа
                    if not result.get("imei"):
                        self.logger.error("IMEIcheck.net: IMEI is missing in properties")
                        return None
                    
                    return self._normalize_basic_response(result)
                
                elif response.status_code == 401:
                    self.logger.error("IMEIcheck.net: Invalid API key")
                    return None
                
                elif response.status_code == 402:
                    self.logger.error("IMEIcheck.net: Insufficient credits")
                    return None
                
                elif response.status_code == 404:
                    self.logger.warning(f"IMEIcheck.net: Device not found - {imei}")
                    return None
                
                else:
                    self.logger.error(f"IMEIcheck.net API error: {response.status_code}")
                    return None
                    
        except httpx.TimeoutException as e:
            self.logger.error(f"IMEIcheck.net: Request timeout after 60s - {str(e)}")
            return None
        except httpx.ConnectError as e:
            self.logger.error(f"IMEIcheck.net: Connection error - {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            self.logger.error(f"IMEIcheck.net: HTTP error - {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"IMEIcheck.net check_basic error: {type(e).__name__} - {str(e)}")
            return None
    
    def get_source_name(self) -> str:
        return "imeicheck.net"
    
    def _normalize_warranty_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа warranty в единый формат"""
        # API response format:
        # {"id":"RzHnAiHr5-a-iCGZ","type":"api","status":"successful",
        # "orderId":null,"service":{"id":1,"title":"Apple Basic Info"},
        # 
        # "amount":"0.06","deviceId":"354630185705601",
        # "processedAt":1772200990,
        #
        # "properties":{
        #   "deviceName":"iPhone 17 A3520","imei":"354630185705601",
        #   "imei2":"354630185887888","serial":"G03JJYHQ96",
        #   "estPurchaseDate":1767916800,"simLock":false,
        #   "fmiOn":false,"replaced":false,
        #   "warrantyStatus":"Apple Limited Warranty",
        #   "repairCoverage":true,
        #   "apple\/modelName":"iPhone 17","lostMode":false,
        #   "usaBlockStatus":"Clean"}
        #}
        
        return {
            "imei": data.get("imei"),
            "model": data.get("apple/modelName"),
            "memory": self._extract_memory(data.get("deviceName")),
            "color": self._extract_color(data.get("deviceName")),
            "serial_number": data.get("serial"),
            "purchase_date": data.get("estPurchaseDate"),
            "warranty_status": data.get("warrantyStatus"),
            "warranty_end_date": data.get("Warranty Expiration Date"),
            "find_my_iphone": data.get("fmiOn"),
            "activation_lock": None,
            "icloud_status": None,
            "simlock": data.get("simLock") == "UNLOCKED",
            "carrier": data.get("Carrier"),
            "country": data.get("Country"),
            "activated": None,
            "activation_date": None,
        }
    
    def _normalize_basic_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа basic в единый формат"""
        # Service ID 3 возвращает те же поля что и warranty
        
        # Convert Unix timestamp to formatted date string
        purchase_date = None
        if data.get("estPurchaseDate"):
            try:
                purchase_date = datetime.fromtimestamp(data.get("estPurchaseDate")).strftime("%d-%m-%Y %H:%M")
            except (ValueError, TypeError):
                purchase_date = None

        simlock_status = "UNLOCKED"
        if data.get("simLock") is True:
            simlock_status = "LOCKED"
        
        return {
            "imei": data.get("imei"),
            "model": data.get("apple/modelName"),
            "memory": self._extract_memory(data.get("deviceName")),
            "color": self._extract_color(data.get("deviceName")),
            "serial_number": data.get("serial"),
            "purchase_date": purchase_date,
            "warranty_status": data.get("warrantyStatus"),
            "warranty_end_date": data.get("Warranty Expiration Date"),
            "find_my_iphone": data.get("fmiOn"),
            "activation_lock": None,
            "icloud_status": None,
            "simlock": simlock_status,
            "carrier": data.get("Carrier"),
            "country": data.get("Country"),
            "activated": None,
            "activation_date": None,
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
        """Извлечение объема памяти из строки модели"""
        if not capacity:
            return None
        
        capacity_str = str(capacity).upper().strip()
        
        # Ищем паттерны типа "128GB", "256GB", "512GB", "1TB"
        match = re.search(r'(\d+)\s*(GB|TB)', capacity_str)
        if match:
            memory = f"{match.group(1)}{match.group(2)}"

            if memory.endswith("GB"):
                return int(memory[:-2])
            elif memory.endswith("TB"):
                return int(memory[:-2]) * 1024
        
        return None

    def _extract_color(self, model_str: Optional[str]) -> Optional[str]:
        """Извлечение цвета из строки модели (примерно)"""
        if not model_str:
            return None
        
        # Примеры: "iPhone 17 Pro Silver", "IPHONE 17 PRO SILVER 256GB-GEH"
        colors = {
            'SILVER': 'Silver',
            'GOLD': 'Gold',
            'BLACK': 'Black',
            'WHITE': 'White',
            'BLUE': 'Blue',
            'RED': 'Red',
            'GREEN': 'Green',
            'PURPLE': 'Purple',
            'PINK': 'Pink',
            'TITANIUM': 'Titanium',
            'NATURAL': 'Natural Titanium',
            'GRAPHITE': 'Graphite',
            'ORANGE': 'Orange',
            'YELLOW': 'Yellow',
            'COSMIC GRAY': 'Cosmic Gray',
            'COSMIC ORANGE': 'Cosmic Orange',
        }
        
        model_upper = model_str.upper()
        for color_key, color_name in colors.items():
            if color_key in model_upper:
                return color_name
        
        return None

 