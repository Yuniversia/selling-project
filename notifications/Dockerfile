FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Переменные окружения по умолчанию
ENV PORT=6000
ENV BACKEND_HOST=0.0.0.0

# Запускаем приложение
CMD uvicorn main:app --host ${BACKEND_HOST} --port ${PORT}
