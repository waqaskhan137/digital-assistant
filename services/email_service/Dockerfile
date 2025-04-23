FROM python:3.11-slim

WORKDIR /app

COPY services/email_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the email service code
COPY services/email_service/src ./src

# Copy the shared module
COPY shared ./shared

# Make the shared module importable
ENV PYTHONPATH "${PYTHONPATH}:/app"

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]