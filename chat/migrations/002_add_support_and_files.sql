-- Добавление поддержки тех поддержки и файлов в чат
-- Миграция 002

-- Добавляем поля для тех поддержки в таблицу chat
ALTER TABLE chat ADD COLUMN IF NOT EXISTS support_joined BOOLEAN DEFAULT FALSE;
ALTER TABLE chat ADD COLUMN IF NOT EXISTS support_user_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_chat_support_user_id ON chat(support_user_id);

-- Добавляем поля для файлов в таблицу message
ALTER TABLE message ADD COLUMN IF NOT EXISTS message_type VARCHAR(20) DEFAULT 'text';
ALTER TABLE message ADD COLUMN IF NOT EXISTS file_url VARCHAR(500);
ALTER TABLE message ADD COLUMN IF NOT EXISTS file_name VARCHAR(255);
ALTER TABLE message ADD COLUMN IF NOT EXISTS file_size INTEGER;

-- Делаем message_text nullable для файловых сообщений
ALTER TABLE message ALTER COLUMN message_text DROP NOT NULL;

-- Добавляем индекс для быстрого поиска сообщений по типу
CREATE INDEX IF NOT EXISTS idx_message_type ON message(message_type);

-- Комментарии для документации
COMMENT ON COLUMN chat.support_joined IS 'Была ли приглашена тех поддержка в чат';
COMMENT ON COLUMN chat.support_user_id IS 'ID сотрудника тех поддержки, если присоединился';
COMMENT ON COLUMN message.message_type IS 'Тип сообщения: text, image, file, system';
COMMENT ON COLUMN message.file_url IS 'URL файла в Cloudflare R2';
COMMENT ON COLUMN message.file_name IS 'Оригинальное имя файла';
COMMENT ON COLUMN message.file_size IS 'Размер файла в байтах';
