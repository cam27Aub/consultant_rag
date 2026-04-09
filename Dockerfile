FROM python:3.11-slim

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Frontend dependencies
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci

# Copy all source
COPY . .

# Build frontend
RUN cd frontend && npm run build

# Expose port (Render injects PORT env var)
EXPOSE 8001

CMD ["sh", "-c", "uvicorn api_endpoint:app --host 0.0.0.0 --port ${PORT:-8001}"]
