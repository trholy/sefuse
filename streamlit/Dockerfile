FROM python:3.11-slim

WORKDIR /app

COPY src/Home.py requirements.txt favicon.jpg /app/

COPY src/utils/ /app/utils/
COPY src/pages/ /app/pages/
COPY src/ui/ /app/ui/
COPY src/auth/ /app/auth/
COPY migrations/ /app/migrations/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8501

CMD ["sh", "-c", "python -m auth.migrate && streamlit run Home.py --server.port=8501 --server.address=0.0.0.0"]
