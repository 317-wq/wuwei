# 可选：容器化运行
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

EXPOSE 8000

# 生产环境去掉 --reload，并按需调整 workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
