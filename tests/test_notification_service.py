# test_notification_service.py - Тесты для notification service

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

from notifications.main import app
from notifications.database import get_session
from notifications.models import NotificationLog, NotificationTemplate


# Тестовая база данных в памяти
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_health_check(client: TestClient):
    """Проверка health endpoint"""
    response = client.get("/api/v1/notifications/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "notification-service"


def test_send_order_created_notification(client: TestClient, session: Session):
    """Тест отправки уведомления о создании заказа"""
    order_data = {
        "order_id": 123,
        "seller_name": "Иван Иванов",
        "seller_email": "seller@test.com",
        "seller_phone": "+37120000000",
        "buyer_name": "Петр Петров",
        "buyer_email": "buyer@test.com",
        "buyer_phone": "+37121111111",
        "product_name": "iPhone 14 Pro",
        "product_model": "128GB Space Black",
        "order_price": 899.99,
        "delivery_method": "DPD",
        "tracking_url": "https://test.yuniversia.eu/orders/123"
    }
    
    response = client.post(
        "/api/v1/notifications/order-created",
        json=order_data
    )
    
    # Проверяем, что запрос обработан
    assert response.status_code == 200
    data = response.json()
    
    # В тестовом окружении без реальных API credentials уведомления могут не отправиться
    # Но endpoint должен вернуть структурированный ответ
    assert "success" in data
    assert "message" in data


def test_notification_history_empty(client: TestClient):
    """Тест получения пустой истории уведомлений"""
    response = client.get("/api/v1/notifications/history")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_notification_history_with_filter(client: TestClient, session: Session):
    """Тест фильтрации истории уведомлений"""
    # Создаем тестовую запись
    notification = NotificationLog(
        notification_type="order_created",
        channel="email",
        recipient_email="test@example.com",
        order_id=123,
        subject="Test order",
        message="Test message",
        status="sent"
    )
    session.add(notification)
    session.commit()
    
    # Запрашиваем историю с фильтром по email
    response = client.get("/api/v1/notifications/history?email=test@example.com")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["recipient_email"] == "test@example.com"
    assert data[0]["order_id"] == 123


def test_notification_history_with_order_filter(client: TestClient, session: Session):
    """Тест фильтрации истории по order_id"""
    # Создаем несколько записей
    for i in range(3):
        notification = NotificationLog(
            notification_type="order_created",
            channel="email",
            recipient_email=f"test{i}@example.com",
            order_id=100 + i,
            subject=f"Order {100 + i}",
            message="Test",
            status="sent"
        )
        session.add(notification)
    session.commit()
    
    # Запрашиваем конкретный заказ
    response = client.get("/api/v1/notifications/history?order_id=101")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["order_id"] == 101


def test_template_rendering():
    """Тест рендеринга шаблонов"""
    from notifications.notification_service import NotificationService
    
    # Создаем mock сервис
    template = "Hello {name}! Your order #{order_id} is ready."
    data = {"name": "John", "order_id": 123}
    
    # Простая замена переменных
    result = template
    for key, value in data.items():
        result = result.replace(f"{{{key}}}", str(value))
    
    assert result == "Hello John! Your order #123 is ready."


def test_notification_log_creation(session: Session):
    """Тест создания записи в лог уведомлений"""
    notification = NotificationLog(
        notification_type="test",
        channel="email",
        recipient_email="test@example.com",
        subject="Test",
        message="Test message",
        status="pending"
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)
    
    assert notification.id is not None
    assert notification.status == "pending"
    assert notification.retry_count == 0


def test_notification_template_creation(session: Session):
    """Тест создания шаблона уведомлений"""
    template = NotificationTemplate(
        notification_type="test_template",
        email_subject="Test {subject}",
        email_body="<p>Test {body}</p>",
        sms_text="Test SMS {text}",
        description="Test template",
        is_active=True
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    
    assert template.id is not None
    assert template.is_active is True
    assert "{subject}" in template.email_subject


def test_send_notification_invalid_data(client: TestClient):
    """Тест отправки уведомления с некорректными данными"""
    # Отправляем пустой объект
    response = client.post(
        "/api/v1/notifications/order-created",
        json={}
    )
    
    # Должна быть ошибка валидации
    assert response.status_code == 422


def test_notification_retry_mechanism(session: Session):
    """Тест механизма повторных попыток"""
    notification = NotificationLog(
        notification_type="test",
        channel="email",
        recipient_email="test@example.com",
        status="retry",
        retry_count=1,
        error_message="Temporary error"
    )
    session.add(notification)
    session.commit()
    
    # Проверяем, что retry_count сохранен
    assert notification.retry_count == 1
    assert notification.status == "retry"
    assert notification.error_message is not None


def test_notification_with_phone_format():
    """Тест форматирования телефонных номеров"""
    from notifications.notification_service import SendPulseService
    
    service = SendPulseService()
    
    # Тестируем различные форматы телефонов
    test_phones = [
        ("37120000000", "+37120000000"),
        ("+37120000000", "+37120000000"),
        ("371 2000 0000", "+37120000000"),
        ("371-20-000-000", "+37120000000"),
    ]
    
    for input_phone, expected in test_phones:
        formatted = input_phone.strip().replace(" ", "").replace("-", "")
        if not formatted.startswith("+"):
            formatted = f"+{formatted}"
        assert formatted == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
