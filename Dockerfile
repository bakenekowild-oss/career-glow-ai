FROM python:3.11-slim
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app.py paywall.py ./
EXPOSE 8501
CMD ["python3", "app.py"]
