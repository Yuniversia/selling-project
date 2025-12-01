# Main (Frontend) Service Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV BACKEND_HOST=0.0.0.0

# Healthcheck (используем wget вместо requests)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:${PORT}/health || exit 1

# Запуск приложения
CMD ["sh", "-c", "uvicorn main:app --host ${BACKEND_HOST} --port ${PORT}"]
