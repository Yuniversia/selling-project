# Payments Service Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=9000
ENV BACKEND_HOST=0.0.0.0

CMD ["sh", "-c", "uvicorn main:app --host ${BACKEND_HOST} --port ${PORT}"]
