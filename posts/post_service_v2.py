import asyncio
import os
import shutil
import tempfile
import time
import uuid
import logging
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image
from fastapi import HTTPException, UploadFile, status
from sqlmodel import Session, select

from cloudflare_r2 import r2_client
from configs import Configs
from database import engine
from models_v2 import Product, ProductStatus

logger = logging.getLogger("posts.post_service_v2")

IMEI_CHECKER_SERVICE_URL = (
    os.getenv("IMEI_CHECKER_SERVICE_URL")
    or os.getenv("IMEI_SERVICE_URL")
    or "http://imei-checker-service:5002"
)


def _imei_base_candidates() -> List[str]:
    configured = (IMEI_CHECKER_SERVICE_URL or "").rstrip("/")
    candidates: List[str] = []
    if configured:
        candidates.append(configured)

    try:
        parsed = urlparse(configured)
        if parsed.hostname:
            scheme = parsed.scheme or "http"
            netloc_5002 = f"{parsed.hostname}:5002"
            netloc_5001 = f"{parsed.hostname}:5001"
            url_5002 = f"{scheme}://{netloc_5002}"
            url_5001 = f"{scheme}://{netloc_5001}"
            if url_5002 not in candidates:
                candidates.append(url_5002)
            if url_5001 not in candidates:
                candidates.append(url_5001)
    except Exception:
        pass

    if "http://imei-checker-service:5002" not in candidates:
        candidates.append("http://imei-checker-service:5002")
    if "http://imei-checker-service:5001" not in candidates:
        candidates.append("http://imei-checker-service:5001")
    if "http://lais-imei-checker:5002" not in candidates:
        candidates.append("http://lais-imei-checker:5002")

    return candidates


def _imei_endpoint_candidates() -> List[str]:
    endpoints: List[str] = []
    for candidate in _imei_base_candidates():
        c = (candidate or "").rstrip("/")
        if not c:
            continue
        if c.endswith("/api/check-basic"):
            endpoints.append(c)
            base = c[: -len("/api/check-basic")]
            if base:
                endpoints.append(f"{base}/api/check-basic")
        else:
            endpoints.append(f"{c}/api/check-basic")

    deduped: List[str] = []
    for endpoint in endpoints:
        if endpoint not in deduped:
            deduped.append(endpoint)

    return deduped


class ImeiCircuitBreaker:
    def __init__(self, threshold_seconds: int = 5, open_seconds: int = 60):
        self.threshold_seconds = threshold_seconds
        self.open_seconds = open_seconds
        self.opened_until: float = 0.0

    def is_open(self) -> bool:
        return time.time() < self.opened_until

    def open(self) -> None:
        self.opened_until = time.time() + self.open_seconds


imei_breaker = ImeiCircuitBreaker()


def get_post(db: Session, post_id: int) -> Optional[Product]:
    statement = select(Product).where(Product.id == post_id)
    return db.exec(statement).first()


def save_uploads_to_temp(files: List[UploadFile], product_id: int) -> List[str]:
    base_dir = os.path.join(os.path.dirname(__file__), "uploads", "pending", str(product_id))
    os.makedirs(base_dir, exist_ok=True)

    saved_paths: List[str] = []
    for file in files:
        extension = os.path.splitext(file.filename or "")[1] or ".bin"
        tmp_name = f"{uuid.uuid4().hex}{extension}"
        temp_path = os.path.join(base_dir, tmp_name)
        with open(temp_path, "wb") as out_file:
            shutil.copyfileobj(file.file, out_file)
        saved_paths.append(temp_path)

    return saved_paths


async def process_images_to_r2(file_paths: List[str], product_id: int) -> List[str]:
    uploaded_urls: List[str] = []
    for path in file_paths:
        try:
            webp_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".webp")
            webp_temp_file.close()

            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((1920, 1080))
                image.save(webp_temp_file.name, format="WEBP", quality=80, method=6)

            object_key = f"posts/{product_id}/{uuid.uuid4().hex}.webp"
            with open(webp_temp_file.name, "rb") as stream:
                file_bytes = stream.read()

            public_url = await r2_client.upload_file_to_r2(
                file_data=file_bytes,
                object_key=object_key,
                content_type="image/webp",
            )
            uploaded_urls.append(public_url)

            try:
                os.remove(path)
                os.remove(webp_temp_file.name)
            except OSError:
                pass
        except Exception as exc:
            logger.warning("Failed to process image to webp | path=%s | error=%s", path, exc)
            continue

    return uploaded_urls





async def fetch_imei_data(imei: Optional[str]) -> Optional[Dict[str, Any]]:
    if not imei:
        return None

    if imei_breaker.is_open():
        logger.warning("IMEI breaker open, skip check for imei=%s", imei)
        return None

    start = time.monotonic()
    last_exc: Optional[Exception] = None
    for endpoint_url in _imei_endpoint_candidates():
        try:
            logger.info("IMEI check start | imei=%s | url=%s", imei, endpoint_url)
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    endpoint_url,
                    json={
                        "imei": str(imei),
                        "check_type": "basic",
                        "test_mode": Configs.USE_TEST_MODE,
                        "preferred_source": "imeicheck.net",
                    },
                )
                response.raise_for_status()
                raw_payload = response.json()

                if isinstance(raw_payload, dict) and isinstance(raw_payload.get("data"), dict):
                    imei_payload = raw_payload.get("data")
                else:
                    imei_payload = raw_payload

                if not isinstance(imei_payload, dict) or not imei_payload.get("imei"):
                    logger.warning("IMEI check returned unexpected payload | imei=%s | payload=%s", imei, raw_payload)
                    continue

                logger.info(
                    "IMEI check OK | imei=%s | source=%s | model=%s",
                    imei,
                    imei_payload.get("source", "unknown"),
                    imei_payload.get("model"),
                )
                return imei_payload
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "IMEI check failed | imei=%s | url=%s | error_type=%s | error=%r",
                imei,
                endpoint_url,
                type(exc).__name__,
                exc,
            )

    if time.monotonic() - start >= imei_breaker.threshold_seconds:
        imei_breaker.open()
        logger.warning("IMEI breaker opened for %s seconds", imei_breaker.open_seconds)

    if last_exc:
        logger.warning("IMEI check exhausted all endpoints | imei=%s | last_error=%r", imei, last_exc)
    return None


def create_product_creating(
    db: Session,
    seller_id: int,
    category_id: int,
    price: float,
    title: Optional[str],
    description: Optional[str],
    attributes: Dict[str, Any],
) -> Product:
    payload = dict(attributes or {})
    payload.setdefault(
        "data_source",
        {
            "origin": "imei_checker",
            "verified": False,
            "updated_at": datetime.utcnow().isoformat(),
        },
    )

    product = Product(
        seller_id=seller_id,
        category_id=category_id,
        price=price,
        title=title,
        description=description,
        status=ProductStatus.CREATING.value,
        active=True,
        attributes=payload,
        images_url=[],
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


async def process_product_task(product_id: int, file_paths: List[str]) -> None:
    with Session(engine) as db:
        product = get_post(db, product_id)
        if not product:
            logger.warning("process_product_task: post not found | product_id=%s", product_id)
            return

        existing_images = list(product.images_url or [])

        logger.info(
            "process_product_task start | product_id=%s | files=%s | current_images=%s",
            product_id,
            len(file_paths),
            len(product.images_url or []),
        )

        # Обрабатываем серверные файлы с сжатием в webp
        uploaded_urls = await process_images_to_r2(file_paths, product_id)
        if uploaded_urls:
            logger.info("R2 upload result | product_id=%s | uploaded=%s | compressed_to_webp=true", product_id, len(uploaded_urls))
        else:
            logger.info("R2 upload skipped/empty | product_id=%s | file_paths=%s", product_id, len(file_paths))

        attributes = dict(product.attributes or {})
        imei_data = await fetch_imei_data(attributes.get("imei"))

        if imei_data:
            # Обновляем атрибуты с данными от IMEI сервиса
            attributes.update(
                {
                    "model": imei_data.get("model") or attributes.get("model"),
                    "serial": imei_data.get("serial_number") or attributes.get("serial"),
                    "color": imei_data.get("color") or attributes.get("color"),
                    "memory": imei_data.get("memory") or attributes.get("memory"),
                    "simlock": imei_data.get("simlock"),
                    "fmi": imei_data.get("fmi", imei_data.get("find_my_iphone")),
                    "icloud_status": imei_data.get("icloud_status"),
                    "warranty_status": imei_data.get("warranty_status"),
                    "network": imei_data.get("network"),
                    "replaced": imei_data.get("replaced"),
                    "tts": imei_data.get("technical_support"),
                    "activation_lock": imei_data.get("activation_lock"),
                    "data_source": {
                        "origin": imei_data.get("source", "imei_checker"),
                        "verified": True,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                }
            )
            product.status = ProductStatus.PUBLISHED.value
            logger.info("post published after IMEI check | product_id=%s | model=%s | warranty=%s", product_id, imei_data.get("model"), imei_data.get("warranty_status"))
        else:
            data_source = dict(attributes.get("data_source") or {})
            data_source.update(
                {
                    "origin": data_source.get("origin", "imei_checker"),
                    "verified": False,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            attributes["data_source"] = data_source
            product.status = ProductStatus.PENDING_VERIFICATION.value
            logger.info("post moved to pending_verification | product_id=%s", product_id)

        product.attributes = attributes
        if uploaded_urls:
            product.images_url = uploaded_urls
        elif existing_images:
            product.images_url = existing_images
        logger.info("post images persisted | product_id=%s | images_count=%s", product_id, len(product.images_url or []))
        product.updated_at = datetime.utcnow()

        db.add(product)
        db.commit()
        db.refresh(product)


async def enqueue_or_run(product_id: int, file_paths: List[str]) -> None:
    try:
        from tasks import process_product_background

        await process_product_background.kiq(product_id=product_id, file_paths=file_paths)
    except Exception:
        asyncio.create_task(process_product_task(product_id, file_paths))


def update_product(db: Session, post_id: int, updates: Dict[str, Any]) -> Product:
    existing = get_post(db, post_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    for key, value in updates.items():
        setattr(existing, key, value)
    existing.updated_at = datetime.utcnow()

    db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing
