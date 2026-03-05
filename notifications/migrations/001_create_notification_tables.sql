-- 001_create_notification_tables.sql
-- Миграция для создания таблиц notification service

-- Таблица для истории отправленных уведомлений
CREATE TABLE IF NOT EXISTS notificationlog (
    id SERIAL PRIMARY KEY,
    
    -- Тип уведомления
    notification_type VARCHAR(50) NOT NULL,
    channel VARCHAR(10) NOT NULL, -- email, sms, both
    
    -- Получатель
    recipient_email VARCHAR(255),
    recipient_phone VARCHAR(20),
    recipient_name VARCHAR(200),
    
    -- Связь с заказом
    order_id INTEGER,
    
    -- Содержимое
    subject VARCHAR(500),
    message TEXT,
    
    -- Статус доставки
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    error_message VARCHAR(1000),
    retry_count INTEGER DEFAULT 0,
    
    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    
    -- SendPulse response
    external_id VARCHAR(255)
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_notificationlog_type ON notificationlog(notification_type);
CREATE INDEX IF NOT EXISTS idx_notificationlog_email ON notificationlog(recipient_email);
CREATE INDEX IF NOT EXISTS idx_notificationlog_phone ON notificationlog(recipient_phone);
CREATE INDEX IF NOT EXISTS idx_notificationlog_order ON notificationlog(order_id);
CREATE INDEX IF NOT EXISTS idx_notificationlog_status ON notificationlog(status);

-- Таблица для шаблонов уведомлений
CREATE TABLE IF NOT EXISTS notificationtemplate (
    id SERIAL PRIMARY KEY,
    
    -- Тип уведомления (уникальный)
    notification_type VARCHAR(50) UNIQUE NOT NULL,
    
    -- Шаблоны для email
    email_subject VARCHAR(500),
    email_body TEXT,
    
    -- Шаблон для SMS
    sms_text VARCHAR(500),
    
    -- Метаданные
    description VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для быстрого поиска активных шаблонов
CREATE INDEX IF NOT EXISTS idx_notificationtemplate_type ON notificationtemplate(notification_type);
CREATE INDEX IF NOT EXISTS idx_notificationtemplate_active ON notificationtemplate(is_active);

-- Вставка дефолтных шаблонов
INSERT INTO notificationtemplate (notification_type, email_subject, email_body, sms_text, description, is_active)
VALUES 
(
    'order_created_seller',
    'Новый заказ #{order_id}',
    '<html><body><h2>Новый заказ!</h2><p>Здравствуйте, {seller_name}!</p><p>У вас новый заказ:</p><ul><li><strong>Товар:</strong> {product_name} {product_model}</li><li><strong>Покупатель:</strong> {buyer_name}</li><li><strong>Сумма:</strong> €{order_price}</li><li><strong>Доставка:</strong> {delivery_method}</li></ul><p><a href="{frontend_url}/orders/{order_id}">Посмотреть заказ</a></p></body></html>',
    'Новый заказ #{order_id}! {buyer_name} купил {product_name}. Сумма: €{order_price}',
    'Уведомление продавцу о новом заказе',
    TRUE
),
(
    'order_created_buyer',
    'Подтверждение заказа #{order_id}',
    '<html><body><h2>Заказ подтвержден!</h2><p>Здравствуйте, {buyer_name}!</p><p>Ваш заказ успешно создан:</p><ul><li><strong>Номер заказа:</strong> #{order_id}</li><li><strong>Товар:</strong> {product_name} {product_model}</li><li><strong>Сумма:</strong> €{order_price}</li><li><strong>Доставка:</strong> {delivery_method}</li></ul><p><a href="{tracking_url}">Отследить заказ</a></p><p>Спасибо за покупку!</p></body></html>',
    NULL,
    'Подтверждение заказа покупателю',
    TRUE
),
(
    'order_review_request',
    'Оцените продавца',
    '<html><body><h2>Оцените ваш опыт покупки</h2><p>Здравствуйте, {buyer_name}!</p><p>Вы получили заказ #{order_id} ({product_name}).</p><p>Пожалуйста, оцените продавца {seller_name} и оставьте отзыв:</p><p><a href="{review_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Оставить отзыв</a></p><p>Ваш отзыв поможет другим покупателям!</p></body></html>',
    NULL,
    'Запрос на отзыв после получения заказа',
    TRUE
)
ON CONFLICT (notification_type) DO NOTHING;

-- Комментарии к таблицам
COMMENT ON TABLE notificationlog IS 'История отправленных уведомлений (SMS и Email)';
COMMENT ON TABLE notificationtemplate IS 'Шаблоны уведомлений с поддержкой переменных';
