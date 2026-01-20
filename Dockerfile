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

# Expose port
EXPOSE 5003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5003/api/status || exit 1

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5003", "--workers", "1", "--timeout", "300", "instagram_agent:app"]
