FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all backend code
COPY . ./backend/

# Set Python path to find backend module
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command (overridden by Cloud Run Job)
CMD ["python", "main.py"]
