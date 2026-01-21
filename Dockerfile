FROM python:3.11-slim

WORKDIR /app

# Copy requirements from backend directory
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY backend/ .

# Force port 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
