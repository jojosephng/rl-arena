FROM python:3.9-slim

WORKDIR /app

# Install only the essentials
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run the Referee
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]