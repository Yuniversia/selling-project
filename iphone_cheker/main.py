from urllib import request
from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
import sys
import os
import logging
from typing import Optional

# Добавляем путь к модулю iphone_cheker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_session, create_db_and_tables
from models import IMEICheckRequest, IMEICheckResponse
from imei_service import IMEIService
from configs import Configs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="iPhone IMEI Checker Service",
    description="Сервис проверки IMEI iPhone с кешированием (7 дней) и test режимом",
    version="2.0.0"
)

logger = logging.getLogger(__name__)

# Создаем таблицы при старте
@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    mode = "TEST (mock data)" if Configs.USE_TEST_MODE else "PRODUCTION (real API)"
    logger.info(f"🚀 IMEI Checker Service started in {mode}")
    logger.info(f"📦 Cache TTL: {Configs.IMEI_CACHE_TTL_DAYS} days")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check для Docker"""
    return {
        "status": "healthy",
        "service": "imei-checker",
        "version": "2.0.0",
        "test_mode": Configs.USE_TEST_MODE
    }


@app.post("/api/check-warranty")
async def check_warranty(
    request: IMEICheckRequest,
    db: Session = Depends(get_session)
):
    """
    Проверка IMEI для imei-check.html страницы
    Возвращает полные данные с гарантией
    
    Args:
        request: IMEI и параметры проверки (включая preferred_source)
        db: Сессия базы данных
    
    Returns:
        Полная информация о устройстве с гарантией
    """
    try:
        service = IMEIService(db, test_mode=request.test_mode)
        result = await service.check_warranty(
            request.imei, 
            preferred_source=request.preferred_source
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Warranty check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"IMEI check service unavailable: {str(e)}")


@app.post("/api/check-basic", response_model=IMEICheckResponse)
async def check_basic_endpoint(
    request: IMEICheckRequest,
    db: Session = Depends(get_session)
):
    """
    Проверка IMEI для создания поста
    Возвращает базовые данные устройства
    
    Args:
        request: IMEI и параметры проверки
    
    Returns:
        Базовая информация о устройстве (обязательно должна вернуться)
    """
    try:
        service = IMEIService(db, test_mode=request.test_mode)
        result = await service.check_basic(
            request.imei, 
            force_test=request.test_mode,
            preferred_source=request.preferred_source
        )
        
        if not result:
            raise HTTPException(
                status_code=503,
                detail="Unable to retrieve IMEI data. Please try again."
            )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Basic check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"IMEI check service unavailable: {str(e)}")


@app.get("/api/check/{imei}", response_model=IMEICheckResponse)
async def check_imei_legacy(
    imei: str,
    test_mode: bool = Query(default=None, description="Force test mode"),
    db: Session = Depends(get_session)
):
    """
    Legacy endpoint для обратной совместимости
    Используйте POST /api/check-basic или /api/check-warranty
    """
    try:
        use_test = test_mode if test_mode is not None else Configs.USE_TEST_MODE
        service = IMEIService(db, test_mode=use_test)
        result = await service.check_basic(imei, force_test=use_test)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"❌ IMEI check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"IMEI check service unavailable: {str(e)}")


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_session)):
    """Статистика проверок за последние 24 часа"""
    from datetime import datetime, timedelta
    from sqlmodel import select
    from models import IMEICheckLog
    
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    statement = select(IMEICheckLog).where(IMEICheckLog.created_at >= yesterday)
    logs = db.exec(statement).all()
    
    if not logs:
        return {
            "total_checks": 0,
            "success_rate": 0,
            "avg_response_time_ms": 0,
            "by_source": {}
        }
    
    total = len(logs)
    success_count = sum(1 for log in logs if log.success)
    
    return {
        "total_checks": total,
        "success_rate": round(success_count / total * 100, 2),
        "avg_response_time_ms": round(sum(log.response_time_ms for log in logs) / total, 2),
        "by_source": {
            "mock": sum(1 for log in logs if log.source == "mock"),
            "cache": sum(1 for log in logs if log.source == "cache"),
            "imei_info": sum(1 for log in logs if log.source == "imei.info"),
            "imei_org": sum(1 for log in logs if log.source == "imei.org")
        },
        "test_mode_checks": sum(1 for log in logs if log.test_mode)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)
