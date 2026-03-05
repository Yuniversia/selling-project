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
        self.service_id_basic = 3  # Apple Basic Check - $0.11
        self.service_id_warranty = 4  # Apple Warranty Status Check - $0.06
        # Альтернатива: service_id=50 для Apple Advanced Check ($0.24)
        
        self.logger.info(f"✅ IMEI.org source initialized with Custom API")
    
    async def check_warranty(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Warranty Check через IMEI.org Custom API
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
            
            self.logger.info(f"IMEI.org request to: {url}")
            self.logger.info(f"IMEI.org params: service_id={self.service_id_warranty}, input={imei}, apikey=***")
            
            async with httpx.AsyncClient(timeout=60.0) as client:  # Увеличено до 60 секунд
                self.logger.info("IMEI.org: Sending request...")
                response = await client.get(url, params=params)
                self.logger.info(f"IMEI.org: Response received!")
                
                self.logger.info(f"IMEI.org response status: {response.status_code}")
                self.logger.info(f"IMEI.org response body: {response.text[:800]}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Проверка статуса
                    if data.get("status") != 1:
                        error_msg = data.get("message", "Unknown error")
                        self.logger.error(f"IMEI.org API error: {error_msg}")
                        return None
                    
                    # Custom API возвращает данные напрямую в "response"
                    result = data.get("response", {})
                    
                    if not result:
                        self.logger.error("IMEI.org: No data in response")
                        return None
                    
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
                    
        except httpx.TimeoutException as e:
            self.logger.error(f"IMEI.org: Request timeout after 60s - {str(e)}")
            return None
        except httpx.ConnectError as e:
            self.logger.error(f"IMEI.org: Connection error - {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            self.logger.error(f"IMEI.org: HTTP error - {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"IMEI.org check_warranty error: {type(e).__name__} - {str(e)}")
            return None
    
    async def check_basic(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Basic Check через IMEI.org Custom API
        
        Service ID: 3 (Apple Basic Check)
        Стоимость: $0.11 за запрос
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
            
            async with httpx.AsyncClient(timeout=60.0) as client:  # Увеличено до 60 секунд
                self.logger.info("IMEI.org: Sending request...")
                response = await client.get(url, params=params)
                self.logger.info(f"IMEI.org: Response received!")
                
                self.logger.info(f"IMEI.org response status: {response.status_code}")
                self.logger.info(f"IMEI.org response body: {response.text[:800]}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Проверка статуса
                    if data.get("status") != 1:
                        error_msg = data.get("message", "Unknown error")
                        self.logger.error(f"IMEI.org API error: {error_msg}")
                        return None
                    
                    # Custom API возвращает данные напрямую в "response"
                    result = data.get("response", {})
                    
                    if not result:
                        self.logger.error("IMEI.org: No data in response")
                        return None
                    
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
                    
        except httpx.TimeoutException as e:
            self.logger.error(f"IMEI.org: Request timeout after 60s - {str(e)}")
            return None
        except httpx.ConnectError as e:
            self.logger.error(f"IMEI.org: Connection error - {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            self.logger.error(f"IMEI.org: HTTP error - {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"IMEI.org check_basic error: {type(e).__name__} - {str(e)}")
            return None
    
    def get_source_name(self) -> str:
        return "imei.org"
    
    def _normalize_warranty_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа warranty в единый формат"""
        # API response format:
        # {"Model":"iPhone 17 Pro","IMEI":"356935400311053","IMEI2":"356935400985773",
        #  "Serial Number":"GQ5QCY4WWN","Warranty Status":"Limited Warranty",
        #  "Estimated Purchase Date":"2025-12-17","Simlock":"UNLOCKED"}
        
        return {
            "imei": data.get("IMEI"),
            "model": data.get("Model"),
            "memory": self._extract_memory(data.get("Model")),
            "color": self._extract_color(data.get("Model")),
            "serial_number": data.get("Serial Number"),
            "purchase_date": data.get("Estimated Purchase Date"),
            "warranty_status": data.get("Warranty Status"),
            "warranty_end_date": data.get("Warranty Expiration Date"),
            "find_my_iphone": None,  # Не возвращается в service_id=3
            "activation_lock": None,
            "icloud_status": None,
            "simlock": data.get("Simlock") == "UNLOCKED",
            "carrier": data.get("Carrier"),
            "country": data.get("Country"),
            "activated": None,
            "activation_date": None,
        }
    
    def _normalize_basic_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа basic в единый формат"""
        # Service ID 3 возвращает те же поля что и warranty
        
        return {
            "imei": data.get("IMEI"),
            "model": data.get("Model"),
            "memory": self._extract_memory(data.get("Model")),
            "color": self._extract_color(data.get("Model")),
            "find_my_iphone": None,
            "activation_lock": None,
            "icloud_status": None,
            "simlock": data.get("Simlock") == "UNLOCKED",
            "carrier": data.get("Carrier"),
            "country": data.get("Country"),
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
        }
        
        model_upper = model_str.upper()
        for color_key, color_name in colors.items():
            if color_key in model_upper:
                return color_name
        
        return None

 