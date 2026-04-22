FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

ENV PYTHONUNBUFFERED=1

# Cloud Run requires this
EXPOSE 8080

# Start FastAPI using Cloud Run PORT
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]


