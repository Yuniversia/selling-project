import os
from dotenv import load_dotenv

load_dotenv()


class Configs:
    """Конфигурация IMEI Checker Service"""
    
    # API ключи (старый ключ оставляем для совместимости)
    api_key: str = os.getenv('IMEI_API_KEY')
    IMEI_INFO_API_KEY = os.getenv("IMEI_INFO_API_KEY", "")
    IMEI_ORG_API_KEY = os.getenv("IMEI_ORG_API_KEY", os.getenv('IMEI_API_KEY', ""))
    IMEICHECK_NET_API_KEY = os.getenv("IMEICHECK_NET_API_KEY", "FxtmaTmZi0xwulFPgcC0ocJid1Q44ARF0eiThn71880335fc")
    
    # База данных
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/sslv"
    )
    
    # Кеширование (7 дней)
    IMEI_CACHE_TTL_DAYS = int(os.getenv("IMEI_CACHE_TTL_DAYS", "7"))
    
    # Тестовый режим по умолчанию
    USE_TEST_MODE = os.getenv("USE_TEST_MODE", "true").lower() == "true"
    
    # Таймауты
    API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "10"))
    
    # JWT для интеграции
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    TOKEN_ALGORITHM = os.getenv("TOKEN_ALGORITHM", "HS256")