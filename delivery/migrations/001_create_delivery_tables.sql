-- 001_create_delivery_tables.sql
-- Миграция для создания таблиц delivery service
-- Date: 2026-03-06
-- Description: Создание таблиц для системы доставки (delivery, deliverystatushistory)

-- Таблица доставок
CREATE TABLE IF NOT EXISTS delivery (
    id SERIAL PRIMARY KEY,
    
    -- Связь с заказом (без foreign key - микросервисная архитектура)
    order_id INTEGER NOT NULL UNIQUE,
    
    -- Провайдер доставки
    provider VARCHAR(20) NOT NULL,  -- omniva, dpd, pickup
    
    -- Трекинг номер (генерируется автоматически)
    tracking_number VARCHAR(100) NOT NULL UNIQUE,
    
    -- Код получения из пакомата (6 цифр, генерируется при статусе at_pickup_point)
    pickup_code VARCHAR(6),
    
    -- Статус доставки
    status VARCHAR(30) NOT NULL DEFAULT 'created',
    
    -- Адрес доставки
    delivery_address VARCHAR(500),
    delivery_city VARCHAR(100),
    delivery_zip VARCHAR(20),
    delivery_country VARCHAR(100) DEFAULT 'Latvia',
    
    -- Пункт выдачи (для Omniva/DPD)
    pickup_point_id VARCHAR(100),
    pickup_point_name VARCHAR(200),
    pickup_point_address VARCHAR(500),
    
    -- Получатель
    recipient_name VARCHAR(200) NOT NULL,
    recipient_phone VARCHAR(20) NOT NULL,
    recipient_email VARCHAR(255) NOT NULL,
    
    -- Отправитель
    sender_name VARCHAR(200) NOT NULL,
    sender_phone VARCHAR(20) NOT NULL,
    
    -- Временные метки
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    shipped_at TIMESTAMP,
    arrived_at_pickup_point_at TIMESTAMP,
    picked_up_at TIMESTAMP,
    
    -- Метаданные
    estimated_delivery_date TIMESTAMP,
    notes VARCHAR(1000),
    
    -- Уведомления отправлены
    notification_sent_at_pickup_point BOOLEAN NOT NULL DEFAULT FALSE,
    notification_sent_picked_up BOOLEAN NOT NULL DEFAULT FALSE
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_delivery_order_id ON delivery(order_id);
CREATE INDEX IF NOT EXISTS idx_delivery_tracking_number ON delivery(tracking_number);
CREATE INDEX IF NOT EXISTS idx_delivery_provider ON delivery(provider);
CREATE INDEX IF NOT EXISTS idx_delivery_status ON delivery(status);
CREATE INDEX IF NOT EXISTS idx_delivery_created_at ON delivery(created_at DESC);


-- Таблица истории изменения статусов доставки
CREATE TABLE IF NOT EXISTS deliverystatushistory (
    id SERIAL PRIMARY KEY,
    
    delivery_id INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL,
    notes VARCHAR(500),
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска истории
CREATE INDEX IF NOT EXISTS idx_deliverystatushistory_delivery_id ON deliverystatushistory(delivery_id);
CREATE INDEX IF NOT EXISTS idx_deliverystatushistory_status ON deliverystatushistory(status);
CREATE INDEX IF NOT EXISTS idx_deliverystatushistory_created_at ON deliverystatushistory(created_at DESC);


-- Комментарии к таблицам
COMMENT ON TABLE delivery IS 'Таблица доставок с информацией о заказах, провайдерах и статусах';
COMMENT ON TABLE deliverystatushistory IS 'История изменения статусов доставки для аудита';

COMMENT ON COLUMN delivery.order_id IS 'ID заказа из posts-service (без foreign key)';
COMMENT ON COLUMN delivery.tracking_number IS 'Уникальный трекинг-номер для отслеживания доставки';
COMMENT ON COLUMN delivery.pickup_code IS '6-значный код для получения из пакомата';
COMMENT ON COLUMN delivery.provider IS 'Провайдер доставки: omniva, dpd, pickup';
COMMENT ON COLUMN delivery.status IS 'Текущий статус: created, in_transit, at_pickup_point, picked_up, cancelled, returned';
COMMENT ON COLUMN delivery.notification_sent_at_pickup_point IS 'Отправлено ли SMS с кодом получения';
COMMENT ON COLUMN delivery.notification_sent_picked_up IS 'Отправлено ли SMS о получении заказа';


-- Просмотр: статистика доставок по провайдерам
CREATE OR REPLACE VIEW delivery_stats_by_provider AS
SELECT 
    provider,
    status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (picked_up_at - created_at))/3600) as avg_delivery_hours
FROM delivery
WHERE picked_up_at IS NOT NULL
GROUP BY provider, status
ORDER BY provider, status;

COMMENT ON VIEW delivery_stats_by_provider IS 'Статистика доставок по провайдерам со средним временем доставки';


-- Просмотр: активные доставки с полной информацией
CREATE OR REPLACE VIEW active_deliveries AS
SELECT 
    d.id,
    d.order_id,
    d.tracking_number,
    d.provider,
    d.status,
    d.recipient_name,
    d.recipient_phone,
    d.pickup_code,
    d.created_at,
    d.estimated_delivery_date,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - d.created_at))/3600 as hours_since_created
FROM delivery d
WHERE d.status NOT IN ('picked_up', 'cancelled', 'returned')
ORDER BY d.created_at DESC;

COMMENT ON VIEW active_deliveries IS 'Все активные доставки (не завершенные)';


-- Просмотр: доставки, ожидающие получения в пакомате
CREATE OR REPLACE VIEW deliveries_at_pickup_points AS
SELECT 
    d.id,
    d.order_id,
    d.tracking_number,
    d.pickup_code,
    d.provider,
    d.pickup_point_name,
    d.pickup_point_address,
    d.recipient_name,
    d.recipient_phone,
    d.arrived_at_pickup_point_at,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - d.arrived_at_pickup_point_at))/3600 as hours_waiting
FROM delivery d
WHERE d.status = 'at_pickup_point'
ORDER BY d.arrived_at_pickup_point_at DESC;

COMMENT ON VIEW deliveries_at_pickup_points IS 'Доставки, которые ожидают получения в пакоматах';


-- Триггер для автоматического добавления записи в историю при изменении статуса
CREATE OR REPLACE FUNCTION log_delivery_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status != OLD.status THEN
        INSERT INTO deliverystatushistory (delivery_id, status, notes)
        VALUES (NEW.id, NEW.status, 'Status changed from ' || OLD.status || ' to ' || NEW.status);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_log_delivery_status
AFTER UPDATE ON delivery
FOR EACH ROW
EXECUTE FUNCTION log_delivery_status_change();

COMMENT ON FUNCTION log_delivery_status_change() IS 'Автоматически логирует изменения статуса доставки';


-- Вывод информации о созданных таблицах
SELECT 'Delivery tables created successfully!' as status;
SELECT table_name, table_type 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('delivery', 'deliverystatushistory')
ORDER BY table_name;
