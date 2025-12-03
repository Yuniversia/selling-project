FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей системы
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы
COPY . .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir fastapi uvicorn requests urllib3

# Переменные окружения по умолчанию
ENV PORT=5001
ENV BACKEND_HOST=0.0.0.0

# Открываем порт
EXPOSE 5001

# Запуск приложения
CMD ["sh", "-c", "uvicorn main:app --host ${BACKEND_HOST} --port ${PORT} --reload"]
