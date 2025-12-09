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

# Переменные окружения по умолчанию
ENV PORT=4000
ENV BACKEND_HOST=0.0.0.0

# Открываем порт
EXPOSE 4000

# Запуск приложения
CMD ["sh", "-c", "uvicorn main:app --host ${BACKEND_HOST} --port ${PORT}"]
