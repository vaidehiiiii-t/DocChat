FROM python:3.11-slim

# System deps for chromadb, pymupdf, pymysql
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libssl-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create storage dirs
RUN mkdir -p /tmp/uploads /tmp/chroma

EXPOSE 10000

CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:10000", "--workers", "1", "--timeout", "180", "--log-level", "info"]
