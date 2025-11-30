-- Migration: Create chat tables
-- Date: 2025-11-30
-- Description: Создание таблиц для системы чатов (chat, message)

-- Таблица чатов (комнаты чата между покупателем и продавцом)
CREATE TABLE IF NOT EXISTS chat (
    id SERIAL PRIMARY KEY,
    iphone_id INTEGER NOT NULL REFERENCES iphone(id) ON DELETE CASCADE,
    seller_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    buyer_id VARCHAR(255) NOT NULL,  -- ID пользователя или UUID анонима
    buyer_is_registered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Индексы для быстрого поиска
    CONSTRAINT unique_chat_per_buyer UNIQUE (iphone_id, buyer_id)
);

CREATE INDEX idx_chat_seller_id ON chat(seller_id);
CREATE INDEX idx_chat_buyer_id ON chat(buyer_id);
CREATE INDEX idx_chat_iphone_id ON chat(iphone_id);
CREATE INDEX idx_chat_updated_at ON chat(updated_at DESC);


-- Таблица сообщений
CREATE TABLE IF NOT EXISTS message (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chat(id) ON DELETE CASCADE,
    sender_id VARCHAR(255) NOT NULL,  -- ID пользователя или UUID анонима
    sender_is_registered BOOLEAN DEFAULT FALSE,
    message_text TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Проверка: сообщение не может быть пустым
    CONSTRAINT message_text_not_empty CHECK (LENGTH(TRIM(message_text)) > 0)
);

CREATE INDEX idx_message_chat_id ON message(chat_id);
CREATE INDEX idx_message_sender_id ON message(sender_id);
CREATE INDEX idx_message_created_at ON message(created_at DESC);
CREATE INDEX idx_message_is_read ON message(is_read) WHERE is_read = FALSE;


-- Триггер для автоматического обновления updated_at в чате
CREATE OR REPLACE FUNCTION update_chat_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chat SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.chat_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_chat_timestamp
AFTER INSERT ON message
FOR EACH ROW
EXECUTE FUNCTION update_chat_updated_at();


-- Комментарии к таблицам
COMMENT ON TABLE chat IS 'Комнаты чатов между покупателями и продавцами по конкретным объявлениям';
COMMENT ON TABLE message IS 'Сообщения в чатах';

COMMENT ON COLUMN chat.buyer_id IS 'ID зарегистрированного пользователя или UUID анонимного покупателя';
COMMENT ON COLUMN chat.buyer_is_registered IS 'Является ли покупатель зарегистрированным пользователем';
COMMENT ON COLUMN message.sender_id IS 'ID отправителя (пользователь или анонимный UUID)';
COMMENT ON COLUMN message.is_read IS 'Прочитано ли сообщение получателем';


-- Просмотр: статистика чатов по продавцам
CREATE OR REPLACE VIEW seller_chat_stats AS
SELECT 
    seller_id,
    COUNT(DISTINCT id) as total_chats,
    COUNT(DISTINCT CASE WHEN buyer_is_registered THEN buyer_id END) as registered_buyers,
    COUNT(DISTINCT CASE WHEN NOT buyer_is_registered THEN buyer_id END) as anonymous_buyers,
    MAX(updated_at) as last_activity
FROM chat
GROUP BY seller_id;

COMMENT ON VIEW seller_chat_stats IS 'Статистика чатов по продавцам';


-- Просмотр: непрочитанные сообщения по чатам
CREATE OR REPLACE VIEW unread_messages_per_chat AS
SELECT 
    chat_id,
    COUNT(*) as unread_count,
    MAX(created_at) as last_unread_at
FROM message
WHERE is_read = FALSE
GROUP BY chat_id;

COMMENT ON VIEW unread_messages_per_chat IS 'Количество непрочитанных сообщений в каждом чате';


-- Вывод информации о созданных таблицах
SELECT 'Chat tables created successfully!' as status;
SELECT table_name, table_type 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('chat', 'message')
ORDER BY table_name;
