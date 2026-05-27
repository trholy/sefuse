FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY fastapi/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY fastapi/src/main.py /app/
COPY fastapi/src/utils/ /app/utils/
COPY data_processing/src/ /app/data_processing/
COPY shared/ /app/shared/

RUN adduser --disabled-password --uid 10001 appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
