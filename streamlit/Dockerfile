FROM python:3.11-slim

WORKDIR /app

COPY src/app.py requirements.txt favicon.jpg /app/

COPY src/utils/ /app/utils/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
