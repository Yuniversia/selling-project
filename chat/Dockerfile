FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Открываем порт
EXPOSE 4000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:4000/health || exit 1

# Запуск приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4000"]
