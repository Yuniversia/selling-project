-- Обновление старых сообщений, которые были созданы до миграции 002
-- Устанавливаем значения по умолчанию для новых полей

UPDATE message 
SET message_type = 'text' 
WHERE message_type IS NULL;

-- Если message_text NULL у текстового сообщения, ставим пустую строку
UPDATE message 
SET message_text = '' 
WHERE message_text IS NULL AND message_type = 'text';

-- Для файловых и образных сообщений message_text может быть NULL

SELECT 'Old messages updated successfully!' as status;
