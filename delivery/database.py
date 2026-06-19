# database.py - Подключение к базе данных

from sqlmodel import SQLModel, create_engine, Session
from configs import configs
from models import PickupPoint


# Создаем движок базы данных
engine = create_engine(
    configs.get_database_url(),
    echo=False,  # Логирование SQL запросов (False в production)
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_size=10,
    max_overflow=20
)


def create_db_and_tables():
    """Создание таблиц в базе данных"""
    SQLModel.metadata.create_all(engine)
    _seed_pickup_points()
    print("✅ Database tables created successfully")


def _seed_pickup_points():
    """Первичное заполнение справочника пунктов выдачи"""
    dpd_mode = configs.get_dpd_mode()
    default_points = [
        {
            "system_point_id": "LV10193",
            "provider": "dpd",
            "locker_index": "DPD-RIX-001",
            "name": "DPD Riga Center",
            "city": "Riga",
            "address": "Brivibas iela 105",
            "postal_code": "LV-1001",
            "country_code": "LV",
        },
        {
            "system_point_id": "LV90008",
            "provider": "dpd",
            "locker_index": "DPD-RIX-002",
            "name": "DPD Akropole",
            "city": "Riga",
            "address": "Maskavas iela 257",
            "postal_code": "LV-1019",
            "country_code": "LV",
        },
        {
            "system_point_id": "LV22017",
            "provider": "dpd",
            "locker_index": "DPD-DGP-001",
            "name": "DPD Daugavpils",
            "city": "Daugavpils",
            "address": "Cietoksna iela 60",
            "postal_code": "LV-5401",
            "country_code": "LV",
        },
        {
            "system_point_id": "EE30001",
            "provider": "omniva",
            "locker_index": "OMN-TLL-001",
            "name": "Omniva Tallinn Kesklinn",
            "city": "Tallinn",
            "address": "Narva mnt 7",
            "postal_code": "10117",
            "country_code": "EE",
        },
        {
            "system_point_id": "LT40011",
            "provider": "omniva",
            "locker_index": "OMN-VNO-001",
            "name": "Omniva Vilnius Old Town",
            "city": "Vilnius",
            "address": "Gedimino pr. 9",
            "postal_code": "01103",
            "country_code": "LT",
        },
    ]

    with Session(engine) as session:
        for point in default_points:
            if point["provider"] == "dpd" and dpd_mode == "test":
                continue
            exists = session.query(PickupPoint).filter(
                PickupPoint.system_point_id == point["system_point_id"]
            ).first()
            if exists:
                continue
            session.add(PickupPoint(**point))
        session.commit()


def get_session():
    """Dependency для получения сессии базы данных"""
    with Session(engine) as session:
        yield session
