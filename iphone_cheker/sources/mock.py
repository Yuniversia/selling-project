"""Mock источник данных для тестирования"""
from typing import Optional, Dict, Any
import random
from .base import IMEISource


class MockIMEISource(IMEISource):
    """Mock источник для тестового режима"""
    
    def __init__(self):
        super().__init__(api_key=None)
    
    async def check_warranty(self, imei: str) -> Optional[Dict[str, Any]]:
        """Возвращает моковые данные для warranty check"""
        self.logger.info(f"[MOCK] Warranty check for IMEI: {imei}")
        
        models = ["iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15", "iPhone 14 Pro Max", "iPhone 14 Pro"]
        colors = ["Natural Titanium", "Black Titanium", "White Titanium", "Blue Titanium", "Gold"]
        memories = [128, 256, 512, 1024]
        
        return {
            "imei": imei,
            "model": random.choice(models),
            "color": random.choice(colors),
            "memory": random.choice(memories),
            "serial_number": f"F{imei[3:12]}",
            "purchase_date": "2024-06-15",
            "warranty_status": "Active",
            "warranty_expires": "2025-06-15",
            "source": "mock"
        }
    
    async def check_basic(self, imei: str) -> Optional[Dict[str, Any]]:
        """Возвращает моковые данные для basic check"""
        self.logger.info(f"[MOCK] Basic check for IMEI: {imei}")
        
        models = ["iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15", "iPhone 14 Pro Max", "iPhone 14 Pro"]
        colors = ["Natural Titanium", "Black Titanium", "White Titanium", "Blue Titanium", "Gold"]
        memories = [128, 256, 512, 1024]
        
        # Для IMEI начинающихся с 00000 - проблемные устройства
        is_problem = imei.startswith("00000")
        
        return {
            "imei": imei,
            "model": random.choice(models),
            "color": random.choice(colors),
            "memory": random.choice(memories),
            "serial_number": f"F{imei[3:12]}",
            "icloud_status": "Lost/Stolen" if is_problem else "Clean",
            "simlock": "Locked" if is_problem else "Unlocked",
            "fmi": is_problem,
            "activation_lock": is_problem,
            "find_my_iphone": is_problem,
            "sim_lock": is_problem,
            "source": "mock"
        }
    
    def get_source_name(self) -> str:
        return "mock"
