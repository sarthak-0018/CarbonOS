FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
