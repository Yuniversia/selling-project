from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Добавляем путь к модулю iphone_cheker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checker import iphone_check, get_balance

# Режим работы: TEST или PRODUCTION
# Установить через переменную окружения: USE_TEST_MODE=true
USE_TEST_MODE = os.getenv("USE_TEST_MODE", "true").lower() == "true"

app = FastAPI(
    title="iPhone IMEI Checker Service",
    description="Сервис проверки IMEI iPhone",
    version="1.0.0"
)

print(f"[IMEI Checker] Режим работы: {'TEST (заглушка)' if USE_TEST_MODE else 'PRODUCTION (реальный API)'}")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check для Docker"""
    return {"status": "healthy", "service": "imei-checker"}

@app.get("/balance")
async def check_balance():
    """Проверка баланса API ключа"""
    try:
        balance = await get_balance()
        return balance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check/{imei}")
async def check_imei_endpoint(imei: str):
    """Проверка IMEI номера"""
    try:
        # Валидация IMEI (должен быть 15 цифр)
        if not imei.isdigit() or len(imei) != 15:
            raise HTTPException(status_code=400, detail="IMEI должен состоять из 15 цифр")
        
        # Выбор режима работы
        if USE_TEST_MODE:
            # ============ TEST MODE: Заглушка ============
            print(f"[TEST MODE] Возвращаем заглушку для IMEI: {imei}")
            response = {
                "imei": imei,
                "model": "iPhone 12 Pro Max",
                "memory": "256GB",
                "color": "Graphite",
                "find_my_iphone": False,
                "activation_lock": False,
                "simlock": False,
                "activated": True,
                "serial_number": "DX3XK0YQG5K7",
                "purchase_date": "15.03.2021",
                "warranty_status": "Истекла"
            }
        else:
            # ============ PRODUCTION MODE: Реальный API ============
            print(f"[PRODUCTION MODE] Проверяем IMEI через API: {imei}")
            result = await iphone_check(int(imei))
            
            if "error" in result:
                raise HTTPException(status_code=404, detail=result["error"])
            
            # Преобразуем в формат для фронтенда
            response = {
                "imei": imei,
                "model": result.get("model", "Неизвестно"),
                "memory": result.get("memory", "N/A"),
                "color": result.get("color", "N/A"),
                "find_my_iphone": result.get("fmi", False),
                "activation_lock": result.get("icloud", False),
                "simlock": result.get("simlock", False),
                "activated": result.get("activated", False),
                "serial_number": result.get("sn", "—"),
                "purchase_date": "—",
                "warranty_status": "—"
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Ошибка проверки IMEI: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
