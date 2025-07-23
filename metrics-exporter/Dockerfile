FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY metrics_exporter.py .

EXPOSE 8080

CMD ["python", "metrics_exporter.py"] 