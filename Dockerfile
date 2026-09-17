FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
ENV AAI_DB_PATH=/app/data/assurance.db
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
