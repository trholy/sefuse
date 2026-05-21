FROM python:3.11-slim

WORKDIR /app

COPY fastapi/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY fastapi/src/main.py /app/
COPY fastapi/src/utils/ /app/utils/
COPY data_processing/src/ /app/data_processing/
COPY shared/ /app/shared/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
