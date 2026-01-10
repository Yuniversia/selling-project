FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей системы
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код приложения
COPY . .

# Переменные окружения по умолчанию
ENV PORT=5002
ENV BACKEND_HOST=0.0.0.0

# Открываем порт
EXPOSE 5002

# Запуск приложения
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 5002 --reload"]
