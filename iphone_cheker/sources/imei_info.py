"""IMEI.info API Integration"""
import httpx
from typing import Optional, Dict, Any
import logging
from .base import IMEISource


class IMEIInfoSource(IMEISource):
    """
    Интеграция с IMEI.info API
    
    Документация: https://dash.imei.info
    Base URL: https://dash.imei.info/api
    Формат: /api-sync/check/{service_id}/?API_KEY={key}&imei={imei}
    """
    
    BASE_URL = "https://dash.imei.info/api"
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.logger = logging.getLogger("IMEIInfoSource")
        
        if not api_key:
            raise ValueError("IMEI.info API key is required")
        
        # Service IDs
        self.service_id_warranty = 12  # APPLE: Warranty Check - $0.04
        self.service_id_basic = 12  # Используем тот же сервис (service 11 стоит $3.90)
    
    async def check_warranty(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Warranty Check через IMEI.info
        
        Endpoint: /api-sync/check/12/
        Service ID: 12 (APPLE: Warranty Check)
        Стоимость: $0.04 за запрос
        """
        try:
            # URL с service_id в пути
            url = f"{self.BASE_URL}-sync/check/{self.service_id_warranty}/"
            params = {
                "API_KEY": self.api_key,
                "imei": imei
            }
            
            self.logger.info(f"IMEI.info request to: {url}")
            self.logger.info(f"IMEI.info params: imei={imei}, API_KEY={self.api_key[:10]}***")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                
                self.logger.info(f"IMEI.info response status: {response.status_code}")
                self.logger.info(f"IMEI.info response body: {response.text[:500]}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Проверяем статус
                    if data.get("status") != "Done":
                        self.logger.error(f"IMEI.info: Check not completed, status: {data.get('status')}")
                        return None
                    
                    # Парсим результат
                    result = data.get("result", {})
                    return self._normalize_warranty_response(result)
                
                elif response.status_code == 401:
                    self.logger.error("IMEI.info: Invalid API key")
                    return None
                
                elif response.status_code == 402:
                    self.logger.error("IMEI.info: Insufficient credits")
                    return None
                
                else:
                    self.logger.error(f"IMEI.info API error: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            self.logger.error("IMEI.info: Request timeout")
            return None
        except Exception as e:
            self.logger.error(f"IMEI.info error: {e}")
            return None
    
    async def check_basic(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Basic Check через IMEI.info
        
        Endpoint: /api-sync/check/11/
        Service ID: 11 (APPLE: Basic Check - предположительно)
        Стоимость: ~$0.03 за запрос
        """
        try:
            # URL с service_id в пути
            url = f"{self.BASE_URL}-sync/check/{self.service_id_basic}/"
            params = {
                "API_KEY": self.api_key,
                "imei": imei
            }
            
            self.logger.info(f"IMEI.info request to: {url}")
            self.logger.info(f"IMEI.info params: imei={imei}, API_KEY={self.api_key[:10]}***")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                
                self.logger.info(f"IMEI.info response status: {response.status_code}")
                self.logger.info(f"IMEI.info response body: {response.text[:500]}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Проверяем статус
                    if data.get("status") != "Done":
                        self.logger.error(f"IMEI.info: Check not completed, status: {data.get('status')}")
                        return None
                    
                    # Парсим результат
                    result = data.get("result", {})
                    return self._normalize_basic_response(result)
                
                elif response.status_code == 401:
                    self.logger.error("IMEI.info: Invalid API key")
                    return None
                
                elif response.status_code == 402:
                    self.logger.error("IMEI.info: Insufficient credits")
                    return None
                
                else:
                    self.logger.error(f"IMEI.info API error: {response.status_code}")
                    return None
                    
        except httpx.TimeoutException:
            self.logger.error("IMEI.info: Request timeout")
            return None
        except Exception as e:
            self.logger.error(f"IMEI.info error: {e}")
            return None
    
    def get_source_name(self) -> str:
        return "imei.info"
    
    def _normalize_warranty_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа IMEI.info в единый формат"""
        # Получаем сырую строку модели
        raw_model = data.get("model") or data.get("model_name") or data.get("description")
        
        # Парсим модель, цвет и память
        parsed = self._parse_model_string(raw_model)
        
        return {
            "imei": data.get("imei_number") or data.get("imei_sn"),
            "model": parsed["model"],
            "color": parsed["color"],
            "memory": parsed["memory"],
            "serial_number": data.get("serial_number"),
            "warranty_status": data.get("warranty_status"),
            "purchase_date": data.get("estimated_purchase_date") or data.get("purchase_date"),
            "activation_status": data.get("activation_status"),
            "device_is_activated": data.get("device_is_activated") == "true",
            "applecare_eligible": data.get("applecare_eligible"),
        }
    
    def _normalize_basic_response(self, data: Dict) -> Dict[str, Any]:
        """Преобразование ответа basic в единый формат"""
        return {
            "imei": data.get("imei_number") or data.get("imei_sn"),
            "model": data.get("model") or data.get("model_name") or data.get("description"),
            "activation_status": data.get("activation_status"),
            "device_is_activated": data.get("device_is_activated") == "true",
        }
    
    def _extract_memory(self, model_str: Optional[str]) -> Optional[str]:
        """Извлечение объема памяти из строки модели"""
        if not model_str:
            return None
        
        # Поиск паттернов: 64GB, 128GB, 256GB и т.д.
        import re
        match = re.search(r'(\d+)\s*(GB|TB)', model_str, re.IGNORECASE)
        if match:
            return f"{match.group(1)}{match.group(2).upper()}"
        
        return None
    
    def _parse_model_string(self, model_str: Optional[str]) -> Dict[str, Optional[str]]:
        """
        Парсинг строки модели формата: IPHONE 17 PRO SILVER 256GB-GEH
        Возвращает: {model: "iPhone 17 Pro", color: "Silver", memory: "256"}
        """
        if not model_str:
            return {"model": None, "color": None, "memory": None}
        
        import re
        
        # Приводим к верхнему регистру для унификации
        model_upper = model_str.upper().strip()
        
        # Извлекаем память (256GB, 512GB, 1TB и т.д.)
        memory = None
        memory_match = re.search(r'(\d+)\s*(GB|TB)', model_upper)
        if memory_match:
            memory = memory_match.group(1)  # Только цифры, без GB
            # Удаляем память и все после неё из строки
            model_upper = model_upper[:memory_match.start()].strip()
        
        # Список известных цветов Apple (расширяемый)
        colors = [
            'SILVER', 'GOLD', 'SPACE GRAY', 'ROSE GOLD', 'SPACE BLACK',
            'BLUE', 'RED', 'YELLOW', 'GREEN', 'PURPLE', 'PINK', 'WHITE',
            'BLACK', 'MIDNIGHT', 'STARLIGHT', 'PRODUCT RED', 'CORAL',
            'NATURAL', 'TITANIUM', 'DESERT', 'SIERRA BLUE', 'GRAPHITE',
            'ALPINE GREEN', 'DEEP PURPLE'
        ]
        
        # Ищем цвет с конца строки
        color = None
        for c in colors:
            if model_upper.endswith(' ' + c):
                color = c.title()  # Silver, Gold и т.д.
                model_upper = model_upper[:-len(c)].strip()
                break
        
        # Оставшаяся часть - это модель
        # Преобразуем "IPHONE 17 PRO" -> "iPhone 17 Pro"
        model = model_upper.replace('IPHONE', 'iPhone')
        model = ' '.join(word.capitalize() if word not in ['PRO', 'MAX', 'PLUS', 'SE'] 
                        else word.title() for word in model.split())
        
        return {
            "model": model if model else None,
            "color": color,
            "memory": memory
        }
