FROM python:3.11-slim

WORKDIR /app

COPY streamlit/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY streamlit/src/Home.py streamlit/favicon.jpg /app/
COPY streamlit/migrations /app/migrations/
COPY streamlit/src/auth/ /app/auth/
COPY streamlit/src/utils/ /app/utils/
COPY streamlit/src/pages/ /app/pages/
COPY streamlit/src/ui/ /app/ui/
COPY shared/ /app/shared/
COPY streamlit/.streamlit /app/.streamlit/

RUN adduser --disabled-password --no-create-home --uid 10001 appuser
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["sh", "-c", "python -m auth.migrate && exec streamlit run Home.py --server.port=8501 --server.address=0.0.0.0"]
