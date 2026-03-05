FROM python:3.11-slim

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем приложение
COPY . .

# Создаем непривилегированного пользователя
RUN useradd -m -u 1000 delivery && chown -R delivery:delivery /app
USER delivery

# Открываем порт
EXPOSE 7000

# Запуск приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7000"]
