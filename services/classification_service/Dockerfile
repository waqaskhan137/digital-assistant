FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared/ /app/shared/

# Copy service source code
COPY services/classification_service/src/ /app/src/

# Create a non-root user and switch to it
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Command to run the service
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]