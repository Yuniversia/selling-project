"""Базовый класс для источников данных IMEI"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging


class IMEISource(ABC):
    """Абстрактный класс для источников проверки IMEI"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def check_warranty(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Warranty Check
        
        Args:
            imei: 15-значный IMEI
        
        Returns:
            Словарь с данными устройства и гарантии или None при ошибке
        """
        pass
    
    @abstractmethod
    async def check_basic(self, imei: str) -> Optional[Dict[str, Any]]:
        """
        Apple Basic Check (iCloud, FMI, Simlock)
        
        Args:
            imei: 15-значный IMEI
        
        Returns:
            Словарь с данными устройства и статусами или None при ошибке
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Имя источника данных"""
        pass
    
    def _parse_memory(self, memory_str: str) -> Optional[int]:
        """Парсит строку памяти в число GB"""
        if not memory_str:
            return None
        
        memory_str = str(memory_str).upper().strip()
        memory_str = memory_str.replace("GB", "").replace("G", "").strip()
        
        if "TB" in memory_str or "T" in memory_str:
            memory_str = memory_str.replace("TB", "").replace("T", "").strip()
            try:
                return int(float(memory_str) * 1024)
            except ValueError:
                return None
        
        try:
            return int(memory_str)
        except ValueError:
            return None
