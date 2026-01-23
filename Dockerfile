# Instagram DM Agent - Docker Configuration for Zeabur
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

# Expose port (Zeabur sets PORT env var)
EXPOSE 8080

# Run the Flask app directly - it reads PORT from env
CMD ["python", "instagram_agent.py"]
