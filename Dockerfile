# Dockerfile
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed for some packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose port (Render uses $PORT)
EXPOSE 8000

# Run the app
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]