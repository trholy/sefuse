FROM python:3.11-slim

WORKDIR /app

COPY streamlit/src/Home.py streamlit/requirements.txt streamlit/favicon.jpg /app/
COPY streamlit/src/utils/ /app/utils/
COPY streamlit/src/pages/ /app/pages/
COPY streamlit/src/ui/ /app/ui/
COPY shared/ /app/shared/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
