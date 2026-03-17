import asyncio
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image
from fastapi import HTTPException, UploadFile, status
from sqlmodel import Session, select

from cloudflare_r2 import r2_client
from configs import Configs
from database import engine
from models_v2 import Product, ProductStatus

IMEI_CHECKER_SERVICE_URL = os.getenv("IMEI_CHECKER_SERVICE_URL", "http://imei-checker-service:5002")


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

    return uploaded_urls


async def fetch_imei_data(imei: Optional[str]) -> Optional[Dict[str, Any]]:
    if not imei:
        return None

    if imei_breaker.is_open():
        return None

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{IMEI_CHECKER_SERVICE_URL}/api/check-basic",
                json={
                    "imei": str(imei),
                    "check_type": "basic",
                    "test_mode": Configs.USE_TEST_MODE,
                    "preferred_source": "imeicheck.net",
                },
            )
            response.raise_for_status()
            return response.json()
    except Exception:
        if time.monotonic() - start >= imei_breaker.threshold_seconds:
            imei_breaker.open()
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
            return

        uploaded_urls = await process_images_to_r2(file_paths, product_id)

        attributes = dict(product.attributes or {})
        imei_data = await fetch_imei_data(attributes.get("imei"))

        if imei_data:
            attributes.update(
                {
                    "model": imei_data.get("model") or attributes.get("model"),
                    "serial": imei_data.get("serial_number") or attributes.get("serial"),
                    "color": imei_data.get("color") or attributes.get("color"),
                    "memory": imei_data.get("memory") or attributes.get("memory"),
                    "simlock": imei_data.get("simlock", attributes.get("simlock")),
                    "fmi": imei_data.get("fmi", attributes.get("fmi")),
                    "icloude_status": imei_data.get("icloud_status", attributes.get("icloude_status")),
                    "data_source": {
                        "origin": imei_data.get("source", "imei_checker"),
                        "verified": True,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                }
            )
            product.status = ProductStatus.PUBLISHED.value
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

        product.attributes = attributes
        product.images_url = uploaded_urls
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
