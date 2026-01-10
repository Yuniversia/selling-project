"""Основная логика IMEI Service с кешированием и fallback"""
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import Optional, List
import time
import logging

from models import IMEICheckResponse, IMEICache, IMEICheckLog
from sources import MockIMEISource
from sources.imei_info import IMEIInfoSource
from sources.imei_org import IMEIorgSource
from utils import validate_imei
from configs import Configs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IMEIService:
    """Сервис проверки IMEI с кешированием и fallback логикой"""
    
    def __init__(self, db: Session, test_mode: bool = None):
        self.db = db
        self.test_mode = test_mode if test_mode is not None else Configs.USE_TEST_MODE
        
        # Инициализируем источники данных
        if self.test_mode:
            self.mock_source = MockIMEISource()
            self.sources = []
            logger.info("✅ IMEI Service initialized in TEST MODE (mock data)")
        else:
            # Production источники
            self.sources: List = []
            
            # Добавляем IMEI.info если есть ключ
            if Configs.IMEI_INFO_API_KEY:
                try:
                    self.sources.append(IMEIInfoSource(Configs.IMEI_INFO_API_KEY))
                    logger.info("✅ IMEI.info source initialized")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize IMEI.info: {e}")
            
            # Добавляем IMEI.org если есть ключ
            if Configs.IMEI_ORG_API_KEY:
                try:
                    self.sources.append(IMEIorgSource(Configs.IMEI_ORG_API_KEY))
                    logger.info("✅ IMEI.org source initialized")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize IMEI.org: {e}")
            
            if not self.sources:
                logger.warning("⚠️ No production sources configured! Add API keys.")
            
            logger.info(f"✅ IMEI Service initialized in PRODUCTION MODE with {len(self.sources)} source(s)")

    
    async def check_warranty(self, imei: str, force_test: bool = False) -> IMEICheckResponse:
        """
        Проверка для imei-check.html страницы
        Приоритет: cache → источник данных
        
        Args:
            imei: 15-значный IMEI
            force_test: принудительно использовать test режим
        
        Returns:
            IMEICheckResponse с полными данными
        """
        start_time = time.time()
        
        # 1. Валидация IMEI
        if not validate_imei(imei):
            logger.error(f"❌ Invalid IMEI checksum: {imei}")
            self._log_check(imei, "validation", "warranty", False, 0, "Invalid IMEI checksum")
            raise ValueError("Invalid IMEI checksum (Luhn algorithm failed)")
        
        # 2. Проверка кеша
        cached = self._get_from_cache(imei)
        if cached and not self._is_expired(cached):
            logger.info(f"✅ Cache HIT for IMEI: {imei} (source: {cached.source})")
            response = self._cache_to_response(cached, cached=True)
            self._log_check(imei, "cache", "warranty", True, (time.time() - start_time) * 1000)
            return response
        
        # 3. Получение данных от источника
        use_test = force_test or self.test_mode
        
        if use_test:
            # Mock данные
            try:
                data = await self.mock_source.check_warranty(imei)
                response_time = (time.time() - start_time) * 1000
                
                if data:
                    logger.info(f"✅ Mock warranty check successful: {imei}")
                    self._save_to_cache(imei, data)
                    self._log_check(imei, "mock", "warranty", True, response_time)
                    return self._dict_to_response(data, cached=False)
                else:
                    raise Exception("Mock source returned no data")
                    
            except Exception as e:
                logger.error(f"❌ Mock warranty check failed: {str(e)}")
                response_time = (time.time() - start_time) * 1000
                self._log_check(imei, "mock", "warranty", False, response_time, str(e))
                raise Exception(f"IMEI check failed: {str(e)}")
        else:
            # Production режим с fallback логикой
            if not self.sources:
                raise Exception("No API sources configured. Add IMEI_INFO_API_KEY or IMEI_ORG_API_KEY")
            
            # Пытаемся все источники по очереди
            for source in self.sources:
                try:
                    logger.info(f"🔍 Trying {source.get_source_name()} for warranty check: {imei}")
                    data = await source.check_warranty(imei)
                    response_time = (time.time() - start_time) * 1000
                    
                    if data:
                        logger.info(f"✅ {source.get_source_name()} warranty check successful: {imei}")
                        self._save_to_cache(imei, data)
                        self._log_check(imei, source.get_source_name(), "warranty", True, response_time)
                        return self._dict_to_response(data, cached=False)
                    else:
                        logger.warning(f"⚠️ {source.get_source_name()} returned no data, trying next source")
                        
                except Exception as e:
                    logger.error(f"❌ {source.get_source_name()} warranty check failed: {str(e)}")
                    response_time = (time.time() - start_time) * 1000
                    self._log_check(imei, source.get_source_name(), "warranty", False, response_time, str(e))
                    # Продолжаем со следующим источником
                    continue
            
            # Если все источники не сработали
            raise Exception(f"All API sources failed for IMEI: {imei}")

    
    async def check_basic(self, imei: str, force_test: bool = False) -> IMEICheckResponse:
        """
        Проверка для создания поста
        Приоритет: cache → источник данных
        ОБЯЗАТЕЛЬНО должен вернуть данные!
        
        Args:
            imei: 15-значный IMEI
            force_test: принудительно использовать test режим
        
        Returns:
            IMEICheckResponse с базовыми данными
        """
        start_time = time.time()
        
        # 1. Валидация IMEI
        if not validate_imei(imei):
            logger.error(f"❌ Invalid IMEI checksum: {imei}")
            self._log_check(imei, "validation", "basic", False, 0, "Invalid IMEI checksum")
            raise ValueError("Invalid IMEI checksum (Luhn algorithm failed)")
        
        # 2. Проверка кеша
        cached = self._get_from_cache(imei)
        if cached and not self._is_expired(cached):
            logger.info(f"✅ Cache HIT for IMEI: {imei} (source: {cached.source})")
            response = self._cache_to_response(cached, cached=True)
            self._log_check(imei, "cache", "basic", True, (time.time() - start_time) * 1000)
            return response
        
        # 3. Получение данных от источника
        use_test = force_test or self.test_mode
        
        if use_test:
            # Mock данные
            try:
                data = await self.mock_source.check_basic(imei)
                response_time = (time.time() - start_time) * 1000
                
                if data:
                    logger.info(f"✅ Mock basic check successful: {imei}")
                    self._save_to_cache(imei, data)
                    self._log_check(imei, "mock", "basic", True, response_time)
                    return self._dict_to_response(data, cached=False)
                else:
                    raise Exception("Mock source returned no data")
                    
            except Exception as e:
                logger.error(f"❌ Mock basic check failed: {str(e)}")
                response_time = (time.time() - start_time) * 1000
                self._log_check(imei, "mock", "basic", False, response_time, str(e))
                raise Exception(f"IMEI check failed: {str(e)}")
        else:
            # Production режим с fallback логикой
            if not self.sources:
                raise Exception("No API sources configured. Add IMEI_INFO_API_KEY or IMEI_ORG_API_KEY")
            
            # Пытаемся все источники по очереди
            for source in self.sources:
                try:
                    logger.info(f"🔍 Trying {source.get_source_name()} for basic check: {imei}")
                    data = await source.check_basic(imei)
                    response_time = (time.time() - start_time) * 1000
                    
                    if data:
                        logger.info(f"✅ {source.get_source_name()} basic check successful: {imei}")
                        self._save_to_cache(imei, data)
                        self._log_check(imei, source.get_source_name(), "basic", True, response_time)
                        return self._dict_to_response(data, cached=False)
                    else:
                        logger.warning(f"⚠️ {source.get_source_name()} returned no data, trying next source")
                        
                except Exception as e:
                    logger.error(f"❌ {source.get_source_name()} basic check failed: {str(e)}")
                    response_time = (time.time() - start_time) * 1000
                    self._log_check(imei, source.get_source_name(), "basic", False, response_time, str(e))
                    # Продолжаем со следующим источником
                    continue
            
            # Если все источники не сработали
            raise Exception(f"All API sources failed for IMEI: {imei}")

    
    def _get_from_cache(self, imei: str) -> Optional[IMEICache]:
        """Получить данные из кеша"""
        statement = select(IMEICache).where(IMEICache.imei == imei)
        return self.db.exec(statement).first()
    
    def _is_expired(self, cache: IMEICache) -> bool:
        """Проверка, истек ли срок кеша (7 дней)"""
        return datetime.utcnow() > cache.expires_at
    
    def _save_to_cache(self, imei: str, data: dict):
        """Сохранить данные в кеш"""
        try:
            # Удаляем старый кеш если есть
            old_cache = self._get_from_cache(imei)
            if old_cache:
                self.db.delete(old_cache)
            
            # Создаем новую запись
            cache_entry = IMEICache(
                imei=imei,
                model=data.get("model"),
                color=data.get("color"),
                memory=data.get("memory"),
                serial_number=data.get("serial_number"),
                purchase_date=data.get("purchase_date"),
                warranty_status=data.get("warranty_status"),
                warranty_expires=data.get("warranty_expires"),
                icloud_status=data.get("icloud_status"),
                simlock=data.get("simlock"),
                fmi=data.get("fmi"),
                activation_lock=data.get("activation_lock"),
                source=data.get("source", "unknown"),
                checked_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=Configs.IMEI_CACHE_TTL_DAYS)
            )
            
            self.db.add(cache_entry)
            self.db.commit()
            logger.info(f"💾 Cached IMEI data: {imei} (TTL: {Configs.IMEI_CACHE_TTL_DAYS} days)")
            
        except Exception as e:
            logger.error(f"❌ Failed to cache IMEI data: {str(e)}")
            self.db.rollback()
    
    def _cache_to_response(self, cache: IMEICache, cached: bool = True) -> IMEICheckResponse:
        """Преобразовать кеш в response"""
        return IMEICheckResponse(
            imei=cache.imei,
            model=cache.model,
            color=cache.color,
            memory=cache.memory,
            serial_number=cache.serial_number,
            purchase_date=cache.purchase_date,
            warranty_status=cache.warranty_status,
            warranty_expires=cache.warranty_expires,
            icloud_status=cache.icloud_status,
            simlock=cache.simlock,
            fmi=cache.fmi,
            activation_lock=cache.activation_lock,
            find_my_iphone=cache.fmi,  # Алиас
            sim_lock=cache.fmi if cache.simlock and "lock" in cache.simlock.lower() else False,
            source=cache.source,
            checked_at=cache.checked_at,
            cached=cached
        )
    
    def _dict_to_response(self, data: dict, cached: bool = False) -> IMEICheckResponse:
        """Преобразовать dict в response"""
        return IMEICheckResponse(
            imei=data.get("imei"),
            model=data.get("model"),
            color=data.get("color"),
            memory=data.get("memory"),
            serial_number=data.get("serial_number"),
            purchase_date=data.get("purchase_date"),
            warranty_status=data.get("warranty_status"),
            warranty_expires=data.get("warranty_expires"),
            icloud_status=data.get("icloud_status"),
            simlock=data.get("simlock"),
            fmi=data.get("fmi"),
            activation_lock=data.get("activation_lock"),
            find_my_iphone=data.get("find_my_iphone", data.get("fmi")),
            sim_lock=data.get("sim_lock", data.get("fmi")),
            source=data.get("source", "unknown"),
            checked_at=datetime.utcnow(),
            cached=cached
        )
    
    def _log_check(self, imei: str, source: str, check_type: str, 
                   success: bool, response_time_ms: float, error_message: str = None):
        """Логирование проверки"""
        try:
            log_entry = IMEICheckLog(
                imei=imei,
                source=source,
                check_type=check_type,
                success=success,
                response_time_ms=response_time_ms,
                error_message=error_message,
                test_mode=self.test_mode,
                created_at=datetime.utcnow()
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception as e:
            logger.error(f"❌ Failed to log check: {str(e)}")
            self.db.rollback()
