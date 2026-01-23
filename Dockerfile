# Instagram DM Agent - Docker Configuration with Playwright
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Expose port (Zeabur uses dynamic PORT)
EXPOSE 8080

# Environment variable for port (Zeabur sets PORT automatically)
ENV PORT=8080

# Health check using PORT env var
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/status || exit 1

# Run with gunicorn for production - using shell form to expand $PORT
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 300 instagram_agent:app
