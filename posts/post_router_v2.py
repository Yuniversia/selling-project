import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
import httpx
from jose import jwt
from sqlmodel import Session, and_, select

from api_response import ok_response
from configs import Configs
from database import get_session
from models_v2 import PostReport, PostUpdateData, PostView, Product, ProductPublic, ProductStatus, ReportCreate
from post_service_v2 import create_product_creating, enqueue_or_run, get_post, save_uploads_to_temp, update_product

api_router = APIRouter(prefix="/api/v1", tags=["Posts"])

CF_ACCOUNT_ID = Configs.CF_ACCOUNT_ID
CF_ACCOUNT_HASH = Configs.CF_ACCOUNT_HASH
CF_API_TOKEN = Configs.CF_API_TOKEN
CF_IMAGE_DELIVERY_URL = Configs.CF_IMAGE_DELIVERY_URL
CF_BASE_URL = Configs.CF_BASE_URL
http_client = httpx.AsyncClient()


def _decode_user(access_token: Optional[str]) -> Dict[str, Any]:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Недействительный токен: {exc}")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Некорректный токен")
    return payload


def _check_admin(access_token: Optional[str]) -> Dict[str, Any]:
    payload = _decode_user(access_token)
    if payload.get("user_type", "regular") not in ["admin", "support"]:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    return payload


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _attrs_query_expr(key: str, value: Any):
    return Product.attributes.op("->>")(key) == str(value)


@api_router.post("/posts", status_code=status.HTTP_202_ACCEPTED)
async def create_post(
    request: Request,
    category_id: int = Form(...),
    price: float = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    attributes: str = Form("{}"),
    images_url: Optional[str] = Form(None),
    files: List[UploadFile] = File(default_factory=list),
    access_token: str = Cookie(None),
    db: Session = Depends(get_session),
):
    user = _decode_user(access_token)

    try:
        attributes_payload = json.loads(attributes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Поле attributes должно быть валидным JSON")

    data_source = attributes_payload.get("data_source")
    if not isinstance(data_source, dict):
        data_source = {"origin": "imei_checker", "verified": False}
    data_source["updated_at"] = datetime.utcnow().isoformat()
    attributes_payload["data_source"] = data_source

    product = create_product_creating(
        db=db,
        seller_id=user["user_id"],
        category_id=category_id,
        price=price,
        title=title,
        description=description,
        attributes=attributes_payload,
    )

    if images_url:
        product.images_url = [url.strip() for url in images_url.split(",") if url.strip()]
        db.add(product)
        db.commit()

    file_paths = save_uploads_to_temp(files=files, product_id=product.id)
    await enqueue_or_run(product_id=product.id, file_paths=file_paths)

    return ok_response(
        request,
        {
            "id": product.id,
            "status": product.status,
            "message": "Post accepted for background processing",
        },
    )


@api_router.get("/posts")
def list_posts(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = Query(None),
    seller_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(ProductStatus.PUBLISHED.value),
    price_min: Optional[float] = Query(None, ge=0),
    price_max: Optional[float] = Query(None, ge=0),
    model: Optional[str] = Query(None),
    color: Optional[str] = Query(None),
    memory: Optional[int] = Query(None),
    sort_price: Optional[str] = Query(None),
    sort_date: Optional[str] = Query("desc"),
    db: Session = Depends(get_session),
):
    query = select(Product)

    filters = []
    if status_filter:
        filters.append(Product.status == status_filter)
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if seller_id is not None:
        filters.append(Product.seller_id == seller_id)
    if price_min is not None:
        filters.append(Product.price >= price_min)
    if price_max is not None:
        filters.append(Product.price <= price_max)
    if model:
        filters.append(_attrs_query_expr("model", model))
    if color:
        filters.append(_attrs_query_expr("color", color))
    if memory is not None:
        filters.append(_attrs_query_expr("memory", memory))

    if filters:
        query = query.where(and_(*filters))

    if sort_date == "asc":
        query = query.order_by(Product.created_at.asc())
    else:
        query = query.order_by(Product.created_at.desc())

    if sort_price == "asc":
        query = query.order_by(Product.price.asc())
    elif sort_price == "desc":
        query = query.order_by(Product.price.desc())

    rows = db.exec(query.offset(skip).limit(limit)).all()
    payload = [ProductPublic.model_validate(row).model_dump(mode="json") for row in rows]
    return ok_response(request, payload)


@api_router.get("/posts/{post_id}")
def get_post_by_id(
    request: Request,
    post_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session),
):
    post = get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    viewer_id = None
    if access_token:
        try:
            payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
            viewer_id = payload.get("user_id")
        except Exception:
            viewer_id = None

    ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")
    unique_window = datetime.utcnow() - timedelta(hours=24)

    q = select(PostView).where(PostView.post_id == post_id)
    if viewer_id:
        q = q.where(PostView.viewer_id == viewer_id)
    else:
        q = q.where(PostView.viewer_id.is_(None)).where(PostView.viewer_ip == ip).where(PostView.user_agent == user_agent).where(PostView.viewed_at > unique_window)

    viewed = db.exec(q).first()
    if viewed is None:
        post.view_count += 1
        db.add(post)
        db.add(PostView(post_id=post_id, viewer_id=viewer_id, viewer_ip=ip, user_agent=user_agent))
        db.commit()
        db.refresh(post)

    return ok_response(request, ProductPublic.model_validate(post).model_dump(mode="json"))


@api_router.patch("/posts/{post_id}")
def patch_post(
    request: Request,
    post_id: int,
    patch: PostUpdateData,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session),
):
    user = _decode_user(access_token)
    post = get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    user_type = user.get("user_type", "regular")
    is_owner = post.seller_id == user["user_id"]
    is_admin = user_type in ["admin", "support"]
    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    updates = patch.model_dump(exclude_none=True)
    if "status" in updates:
        updates["status"] = updates["status"].value

    updated = update_product(db, post_id=post_id, updates=updates)
    return ok_response(request, ProductPublic.model_validate(updated).model_dump(mode="json"))


@api_router.get("/r2_link")
async def get_direct_upload_url(request: Request):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise HTTPException(status_code=500, detail="Настройки Cloudflare API не заданы")

    try:
        api_url = f"{CF_BASE_URL}/direct_upload"
        headers = {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}
        response = await http_client.post(api_url, headers=headers)
        response.raise_for_status()
        result = response.json()
        return ok_response(
            request,
            {
                "upload_url": result["result"]["uploadURL"],
                "account_hash": CF_ACCOUNT_HASH,
                "image_delivery_base": f"{CF_IMAGE_DELIVERY_URL}/{CF_ACCOUNT_HASH}",
            },
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=500, detail=f"Cloudflare API error: {exc.response.status_code}")


@api_router.post("/report", status_code=status.HTTP_201_CREATED)
def create_report(
    request: Request,
    report_data: ReportCreate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session),
):
    post = get_post(db, report_data.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    reporter_id = None
    if access_token:
        try:
            reporter_id = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm]).get("user_id")
        except Exception:
            reporter_id = None

    report = PostReport(
        post_id=report_data.post_id,
        reporter_id=reporter_id,
        reporter_ip=_get_client_ip(request),
        reason=report_data.reason.value,
        details=report_data.details,
        status="pending",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return ok_response(request, {
        "id": report.id,
        "post_id": report.post_id,
        "reason": report.reason,
        "status": report.status,
        "created_at": report.created_at.isoformat(),
    })


@api_router.get("/report/check/{post_id}")
def check_report(
    request: Request,
    post_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session),
):
    reporter_id = None
    if access_token:
        try:
            reporter_id = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm]).get("user_id")
        except Exception:
            reporter_id = None

    q = select(PostReport).where(PostReport.post_id == post_id)
    if reporter_id:
        q = q.where(PostReport.reporter_id == reporter_id)
    else:
        q = q.where(PostReport.reporter_ip == _get_client_ip(request))

    return ok_response(request, {"has_reported": db.exec(q).first() is not None})


@api_router.get("/admin/reports")
def list_admin_reports(
    request: Request,
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    access_token: str = Cookie(None),
    db: Session = Depends(get_session),
):
    _check_admin(access_token)
    q = select(PostReport)
    if status_filter:
        q = q.where(PostReport.status == status_filter)
    q = q.order_by(PostReport.created_at.desc()).offset(skip).limit(limit)

    reports = []
    for report in db.exec(q).all():
        post = get_post(db, report.post_id)
        attrs = post.attributes if post else {}
        reports.append({
            "id": report.id,
            "post_id": report.post_id,
            "post_model": attrs.get("model", "Удалено") if attrs else "Удалено",
            "post_active": post.active if post else False,
            "reporter_id": report.reporter_id,
            "reporter_ip": report.reporter_ip,
            "reason": report.reason,
            "details": report.details,
            "status": report.status,
            "created_at": report.created_at.isoformat(),
            "reviewed_at": report.reviewed_at.isoformat() if report.reviewed_at else None,
            "reviewed_by": report.reviewed_by,
        })

    return ok_response(request, reports)


@api_router.put("/admin/reports/{report_id}")
def update_admin_report(
    request: Request,
    report_id: int,
    new_status: str = Query(...),
    action: Optional[str] = Query(None),
    access_token: str = Cookie(None),
    db: Session = Depends(get_session),
):
    user = _check_admin(access_token)
    report = db.get(PostReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Жалоба не найдена")

    report.status = new_status
    report.reviewed_at = datetime.utcnow()
    report.reviewed_by = user["user_id"]

    if action == "deactivate_post":
        post = get_post(db, report.post_id)
        if post:
            post.active = False
            db.add(post)

    db.add(report)
    db.commit()
    return ok_response(request, {"report_id": report_id, "new_status": new_status})
