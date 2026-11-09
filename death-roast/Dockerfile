FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY death_roast/ death_roast/

# Expose web UI port
EXPOSE 8080

# Run the sidecar
CMD ["python", "-m", "death_roast"]
