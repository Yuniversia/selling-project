# post_router.py - Posts API Routes

from fastapi import (
    APIRouter, 
    Depends, 
    status, 
    HTTPException, 
    Form, 
    UploadFile, 
    File,
    Query,
    Cookie,
    Request
)

from sqlmodel import Session, select, and_, or_
from typing import List, Optional
from jose import JWTError, jwt
import httpx
from typing import Dict, Any
from datetime import datetime, timedelta

from configs import Configs
from post_service import get_post, add_post
from database import get_session
from models import (
    Iphone, 
    IphonePostData, 
    IphonePublic, 
    PostView, 
    PostReport, 
    ReportCreate, 
    ReportResponse,
    ReportReason
)

# API Router для постов
api_router = APIRouter(prefix="/api/v1", tags=["Iphone Posts"])



CF_ACCOUNT_ID = Configs.CF_ACCOUNT_ID
CF_ACCOUNT_HASH = Configs.CF_ACCOUNT_HASH
CF_API_TOKEN = Configs.CF_API_TOKEN
CF_IMAGE_DELIVERY_URL = Configs.CF_IMAGE_DELIVERY_URL

# Базовый URL для Cloudflare API
CF_BASE_URL = Configs.CF_BASE_URL

# Инициализация HTTP клиента для асинхронных запросов
http_client = httpx.AsyncClient()

@api_router.get("/r2_link", response_model=Dict[str, Any])
async def get_direct_upload_url():
    """
    Запрашивает у Cloudflare URL для одноразовой прямой загрузки.
    Этот URL позволяет клиенту загрузить файл напрямую.
    
    Возвращает:
    - upload_url: URL куда загружать файл (с POST методом)
    - image_id: уникальный ID изображения  
    - public_url: готовый публичный URL для доступа
    
    Инструкция для фронтенда:
    1. Получить этот ответ
    2. Создать FormData и добавить туда файл с ключом 'file'
    3. POST FormData на upload_url
    4. Использовать public_url для доступа к загруженному файлу
    """
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise HTTPException(status_code=500, detail="Настройки Cloudflare API не заданы.")

    try:
        # Эндпоинт для запроса URL прямой загрузки
        api_url = f"{CF_BASE_URL}/direct_upload"
        
        headers = {
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        print(f"[DEBUG] Запрашиваем URL для загрузки у Cloudflare: {api_url}")
        
        # Отправляем запрос в Cloudflare API
        response = await http_client.post(api_url, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        print(f"[DEBUG] Полный ответ от Cloudflare: {result}")
        
        # Cloudflare возвращает uploadURL для сессии загрузки
        upload_url = result['result']['uploadURL']
        # Это НЕ финальный ID! Финальный ID будет в ответе после загрузки файла
        temp_id = result['result']['id']
        
        print(f"[DEBUG] Upload URL: {upload_url}")
        print(f"[DEBUG] Временный ID (для отладки): {temp_id}")
        
        # Возвращаем URL клиенту, а также account hash и base URL для формирования публичного URL
        return {
            "upload_url": upload_url,
            "account_hash": CF_ACCOUNT_HASH,
            "image_delivery_base": f"{CF_IMAGE_DELIVERY_URL}/{CF_ACCOUNT_HASH}",
            "message": "1) POST файл на upload_url. 2) Получите ответ с id. 3) Постройте URL: {image_delivery_base}/{id}/public"
        }
        
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] Ошибка Cloudflare API: {e.response.status_code}")
        print(f"[ERROR] Ответ: {e.response.text}")
        detail = f"Ошибка Cloudflare API: {e.response.status_code}. Ответ: {e.response.text}"
        raise HTTPException(status_code=500, detail=detail)
    except Exception as e:
        print(f"[ERROR] Непредвиденная ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")



@api_router.post(
    "/iphone", 
    status_code=status.HTTP_201_CREATED,
    response_model=IphonePublic
)
async def router_post(
    imei: str = Form(None, description="IMEI телефона (15 цифр)"),
    batery: int = Form(None, description="Уровень заряда батареи (0-100)"),
    description: Optional[str] = Form(None, description="Описание поста (необязательно)"),
    price: Optional[float] = Form(None, description="Цена iPhone"),
    condition: Optional[str] = Form(None, description="Состояние устройства"),
    has_original_box: bool = Form(False, description="Оригинальная коробка"),
    has_charger: bool = Form(False, description="Зарядный блок"),
    has_cable: bool = Form(False, description="Кабель"),
    has_receipt: bool = Form(False, description="Чек о покупке"),
    has_warranty: bool = Form(False, description="Гарантия"),
    images_url: Optional[str] = Form(None, description="URL фотографий (разделены запятыми)"),
    access_token: str = Cookie(None, description="JWT токен из cookies"),
    db: Session = Depends(get_session)
):
    """
    Обрабатывает запрос на добавление нового поста об iPhone.
    Требует JWT токен в cookies.
    """
    # Проверяем наличие токена
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    
    # Извлекаем author_id из JWT токена
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
        username = payload.get("username")
        user_id = payload.get("user_id")
        
        if not username or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректный токен - отсутствует username или user_id",
            )
        
        author_id = user_id
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен: " + str(e)
        )
    
    # Валидация Pydantic
    try:
        validated_data = IphonePostData(
            imei=imei, 
            batery=batery,
            price=price,
            condition=condition,
            has_original_box=has_original_box,
            has_charger=has_charger,
            has_cable=has_cable,
            has_receipt=has_receipt,
            has_warranty=has_warranty
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ошибка валидации данных: {e}",
        )

    # Создание объекта Iphone с author_id, active и view_count
    iphone_data_for_db = Iphone(
        author_id=author_id,
        active=True,
        view_count=0,
        imei=validated_data.imei, 
        batery=validated_data.batery,
        description=description,
        condition=validated_data.condition,
        price=validated_data.price,
        has_original_box=validated_data.has_original_box,
        has_charger=validated_data.has_charger,
        has_cable=validated_data.has_cable,
        has_receipt=validated_data.has_receipt,
        has_warranty=validated_data.has_warranty,
        images_url=images_url  # Добавляем URL фотографий
    )

    try:
        new_iphone = await add_post(db, iphone_data_for_db)
        return new_iphone
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Непредвиденная ошибка сервера: {str(e)}",
        )


# --- GET List Маршрут (с фильтрацией) ---
@api_router.get(
    "/iphone/list",
    response_model=List[IphonePublic],
    responses={
        200: {"description": "Список постов"}
    }
)
def router_list(
    skip: int = Query(0, ge=0, description="Пропустить N постов (для пагинации)"),
    limit: int = Query(20, ge=1, le=100, description="Количество постов на странице"),
    model: Optional[str] = Query(None, description="Фильтр по модели (например: 16, 16pro)"),
    batery_min: Optional[int] = Query(None, ge=0, le=100, description="Минимальный процент АКБ"),
    batery_max: Optional[int] = Query(None, ge=0, le=100, description="Максимальный процент АКБ"),
    condition: Optional[str] = Query(None, description="Состояние (Новый, Как новый, Небольшие дефекты, С дефектом, На запчасти)"),
    color: Optional[str] = Query(None, description="Цвет устройства"),
    memory: Optional[str] = Query(None, description="Минимальный объем памяти в GB (64, 128, 256, 512, 1024)"),
    price_min: Optional[float] = Query(None, ge=0, description="Минимальная цена"),
    price_max: Optional[float] = Query(None, ge=0, description="Максимальная цена"),
    db: Session = Depends(get_session)
):
    """
    Получает список iPhone постов с поддержкой фильтрации и пагинации.
    Возвращает только активные посты, отсортированные по дате создания (новые первыми).
    """
    # Начинаем с базового запроса активных постов
    statement = select(Iphone).where(Iphone.active == True)
    
    # Применяем фильтры если они указаны
    filters = []
    
    if model:
        filters.append(Iphone.model == model)
    
    if batery_min is not None:
        filters.append(Iphone.batery >= batery_min)
    
    if batery_max is not None:
        filters.append(Iphone.batery <= batery_max)
    
    if condition:
        filters.append(Iphone.condition == condition)
    
    if color:
        filters.append(Iphone.color == color)
    
    # Фильтр памяти - теперь это число, фильтр "от X GB"
    if memory:
        try:
            memory_value = int(memory)
            filters.append(Iphone.memory >= memory_value)
        except (ValueError, TypeError):
            pass  # Игнорируем некорректный формат
    
    if price_min is not None:
        filters.append(Iphone.price >= price_min)
    
    if price_max is not None:
        filters.append(Iphone.price <= price_max)
    
    # Объединяем все фильтры с AND
    if filters:
        statement = statement.where(and_(*filters))
    
    # Сортируем по дате создания (новые первыми) и применяем пагинацию
    statement = statement.order_by(Iphone.created_at.desc()).offset(skip).limit(limit)
    
    try:
        posts = db.exec(statement).all()
        return posts
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении списка постов: {str(e)}",
        )


# --- Вспомогательная функция для получения IP адреса ---
def get_client_ip(request: Request) -> str:
    """Получает IP адрес клиента с учетом прокси"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


# --- Вспомогательная функция для проверки уникального просмотра ---
def is_unique_view(db: Session, post_id: int, viewer_id: Optional[int], viewer_ip: str, user_agent: str) -> bool:
    """
    Проверяет, является ли просмотр уникальным.
    Уникальным считается просмотр если:
    1. Для авторизованных: пользователь не просматривал этот пост ранее
    2. Для неавторизованных: комбинация IP + User-Agent не просматривала за последние 24 часа
    """
    if viewer_id:
        # Авторизованный пользователь - проверяем по viewer_id
        existing_view = db.exec(
            select(PostView)
            .where(PostView.post_id == post_id)
            .where(PostView.viewer_id == viewer_id)
        ).first()
        return existing_view is None
    else:
        # Неавторизованный - проверяем по IP + User-Agent за последние 24 часа
        time_threshold = datetime.utcnow() - timedelta(hours=24)
        existing_view = db.exec(
            select(PostView)
            .where(PostView.post_id == post_id)
            .where(PostView.viewer_ip == viewer_ip)
            .where(PostView.user_agent == user_agent)
            .where(PostView.viewed_at > time_threshold)
        ).first()
        return existing_view is None


# --- GET Маршрут (получить один пост по ID) ---
@api_router.get(
    "/iphone", 
    response_model=Optional[IphonePublic],
    responses={
        404: {"description": "Пост не найден"}
    }
)
def router_get(
    request: Request,
    id: int = Query(..., description="ID поста iPhone для получения"),
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Получает информацию об iPhone по его ID.
    Автоматически увеличивает view_count только для уникальных просмотров.
    """
    iphone_post = get_post(db, id)
    
    if not iphone_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пост с ID {id} не найден",
        )
    
    # Получаем информацию о просмотре
    viewer_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")
    viewer_id = None
    
    # Пытаемся получить ID пользователя из токена
    if access_token:
        try:
            payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
            viewer_id = payload.get("user_id")
        except:
            pass  # Игнорируем ошибки токена для просмотров
    
    # Проверяем, является ли просмотр уникальным
    if is_unique_view(db, id, viewer_id, viewer_ip, user_agent):
        # Увеличиваем счетчик просмотров
        iphone_post.view_count += 1
        db.add(iphone_post)
        
        # Сохраняем запись о просмотре
        post_view = PostView(
            post_id=id,
            viewer_id=viewer_id,
            viewer_ip=viewer_ip,
            user_agent=user_agent
        )
        db.add(post_view)
        
        db.commit()
        db.refresh(iphone_post)
        
        print(f"[UNIQUE VIEW] Post #{id} | Viewer: {'User#' + str(viewer_id) if viewer_id else viewer_ip} | Total views: {iphone_post.view_count}")
    else:
        print(f"[DUPLICATE VIEW] Post #{id} | Viewer: {'User#' + str(viewer_id) if viewer_id else viewer_ip} | Not counted")
    
    return iphone_post


# --- POST Жалоба на объявление ---
@api_router.post(
    "/report",
    status_code=status.HTTP_201_CREATED,
    response_model=ReportResponse
)
async def create_report(
    request: Request,
    report_data: ReportCreate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Создает жалобу на объявление.
    Может быть отправлена как авторизованным, так и анонимным пользователем.
    """
    # Проверяем существование поста
    post = get_post(db, report_data.post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Объявление с ID {report_data.post_id} не найдено"
        )
    
    # Получаем информацию о пользователе
    reporter_id = None
    reporter_ip = get_client_ip(request)
    
    if access_token:
        try:
            payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
            reporter_id = payload.get("user_id")
        except:
            pass  # Разрешаем анонимные жалобы
    
    # Проверяем, не отправлял ли пользователь уже жалобу на этот пост
    existing_report_query = select(PostReport).where(PostReport.post_id == report_data.post_id)
    
    if reporter_id:
        # Для авторизованных - проверяем по ID
        existing_report_query = existing_report_query.where(PostReport.reporter_id == reporter_id)
    else:
        # Для анонимных - проверяем по IP за последние 24 часа
        time_threshold = datetime.utcnow() - timedelta(hours=24)
        existing_report_query = existing_report_query.where(
            and_(
                PostReport.reporter_ip == reporter_ip,
                PostReport.created_at > time_threshold
            )
        )
    
    existing_report = db.exec(existing_report_query).first()
    
    if existing_report:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже отправили жалобу на это объявление"
        )
    
    # Создаем жалобу
    new_report = PostReport(
        post_id=report_data.post_id,
        reporter_id=reporter_id,
        reporter_ip=reporter_ip,
        reason=report_data.reason.value,  # Используем значение enum
        details=report_data.details,
        status="pending"
    )
    
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    
    print(f"[REPORT] Post #{report_data.post_id} | Reporter: {'User#' + str(reporter_id) if reporter_id else reporter_ip} | Reason: {report_data.reason.value}")
    
    return ReportResponse(
        id=new_report.id,
        post_id=new_report.post_id,
        reason=new_report.reason,
        status=new_report.status,
        created_at=new_report.created_at
    )


# --- GET Проверка наличия жалобы от пользователя ---
@api_router.get(
    "/report/check/{post_id}",
    response_model=Dict[str, bool]
)
async def check_user_report(
    request: Request,
    post_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Проверяет, отправлял ли пользователь жалобу на данное объявление.
    Возвращает {"has_reported": true/false}
    """
    reporter_id = None
    reporter_ip = get_client_ip(request)
    
    if access_token:
        try:
            payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
            reporter_id = payload.get("user_id")
        except:
            pass
    
    # Проверяем наличие жалобы
    query = select(PostReport).where(PostReport.post_id == post_id)
    
    if reporter_id:
        query = query.where(PostReport.reporter_id == reporter_id)
    else:
        time_threshold = datetime.utcnow() - timedelta(hours=24)
        query = query.where(
            and_(
                PostReport.reporter_ip == reporter_ip,
                PostReport.created_at > time_threshold
            )
        )
    
    existing_report = db.exec(query).first()
    
    return {"has_reported": existing_report is not None}


# === ADMIN ENDPOINTS ===

# Вспомогательная функция для проверки прав администратора
def check_admin_access(access_token: str) -> Dict[str, Any]:
    """Проверяет JWT токен и извлекает данные пользователя, включая роль"""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация"
        )
    
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
        user_id = payload.get("user_id")
        username = payload.get("username")
        user_type = payload.get("user_type", "regular")
        
        if not user_id or not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректный токен"
            )
        
        # Проверяем, что пользователь - админ или поддержка
        if user_type not in ["admin", "support"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен. Требуются права администратора."
            )
        
        return {"user_id": user_id, "username": username, "user_type": user_type}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен истек"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен"
        )


# --- GET Все жалобы (только для админов) ---
@api_router.get(
    "/admin/reports",
    response_model=List[Dict[str, Any]]
)
async def get_all_reports(
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу: pending, reviewed, resolved, rejected"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Получить все жалобы (только для админов и поддержки).
    Возвращает жалобы с информацией о посте.
    """
    # Проверка прав доступа (внутри уже есть проверка на admin/support)
    user_data = check_admin_access(access_token)
    
    # Строим запрос
    query = select(PostReport)
    
    if status_filter:
        query = query.where(PostReport.status == status_filter)
    
    query = query.order_by(PostReport.created_at.desc()).offset(skip).limit(limit)
    
    reports = db.exec(query).all()
    
    # Обогащаем данные информацией о постах
    result = []
    for report in reports:
        post = get_post(db, report.post_id)
        result.append({
            "id": report.id,
            "post_id": report.post_id,
            "post_model": post.model if post else "Удалено",
            "post_active": post.active if post else False,
            "reporter_id": report.reporter_id,
            "reporter_ip": report.reporter_ip,
            "reason": report.reason,
            "details": report.details,
            "status": report.status,
            "created_at": report.created_at.isoformat(),
            "reviewed_at": report.reviewed_at.isoformat() if report.reviewed_at else None,
            "reviewed_by": report.reviewed_by
        })
    
    return result


# --- PUT Обновить статус жалобы (только для админов) ---
@api_router.put(
    "/admin/reports/{report_id}",
    response_model=Dict[str, str]
)
async def update_report_status(
    report_id: int,
    new_status: str = Query(..., description="Новый статус: reviewed, resolved, rejected"),
    action: Optional[str] = Query(None, description="Действие: deactivate_post, none"),
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Обновить статус жалобы и опционально деактивировать пост.
    Только для админов и поддержки.
    """
    # Проверка прав доступа (внутри уже есть проверка на admin/support)
    user_data = check_admin_access(access_token)
    
    # Проверяем валидность статуса
    valid_statuses = ["pending", "reviewed", "resolved", "rejected"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Некорректный статус. Допустимые: {', '.join(valid_statuses)}"
        )
    
    # Получаем жалобу
    report = db.get(PostReport, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Жалоба не найдена"
        )
    
    # Обновляем статус
    report.status = new_status
    report.reviewed_at = datetime.utcnow()
    report.reviewed_by = user_data["user_id"]
    
    # Выполняем действие если указано
    if action == "deactivate_post":
        post = get_post(db, report.post_id)
        if post:
            post.active = False
            db.add(post)
    
    db.add(report)
    db.commit()
    
    print(f"[ADMIN] Report #{report_id} updated by User#{user_data['user_id']} | Status: {new_status} | Action: {action}")
    
    return {
        "status": "success",
        "message": f"Жалоба #{report_id} обновлена",
        "new_status": new_status
    }


# --- PUT Деактивировать пост (только для админов) ---
@api_router.put(
    "/admin/posts/{post_id}/deactivate",
    response_model=Dict[str, str]
)
async def deactivate_post(
    post_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Деактивировать объявление (скрыть из публичного доступа).
    Только для админов и поддержки.
    """
    # Проверка прав доступа (внутри уже есть проверка на admin/support)
    user_data = check_admin_access(access_token)
    
    # Получаем пост
    post = get_post(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Объявление не найдено"
        )
    
    # Деактивируем
    post.active = False
    db.add(post)
    db.commit()
    
    print(f"[ADMIN] Post #{post_id} deactivated by User#{user_data['user_id']}")
    
    return {
        "status": "success",
        "message": f"Объявление #{post_id} деактивировано"
    }


# --- PUT Активировать пост (только для админов) ---
@api_router.put(
    "/admin/posts/{post_id}/activate",
    response_model=Dict[str, str]
)
async def activate_post(
    post_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Активировать объявление (вернуть в публичный доступ).
    Только для админов и поддержки.
    """
    # Проверка прав доступа (внутри уже есть проверка на admin/support)
    user_data = check_admin_access(access_token)
    
    # Получаем пост
    post = get_post(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Объявление не найдено"
        )
    
    # Активируем
    post.active = True
    db.add(post)
    db.commit()
    
    print(f"[ADMIN] Post #{post_id} activated by User#{user_data['user_id']}")
    
    return {
        "status": "success",
        "message": f"Объявление #{post_id} активировано"
    }