FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY fastapi/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY fastapi/src/main.py /app/
COPY fastapi/src/utils/ /app/utils/
COPY shared/ /app/shared/

RUN adduser --disabled-password --uid 10001 appuser
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
