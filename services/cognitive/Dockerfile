FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Spacy model
RUN python -m spacy download en_core_web_lg

# Copy shared code
COPY shared/ /app/shared/

# Copy service code
COPY services/cognitive/ /app/

# Set Python path
ENV PYTHONPATH=/app

CMD ["python", "main.py"]
