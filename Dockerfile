# Use a Python image that meets the browser-use requirement (Python 3.12-slim satisfies >=3.11)
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose ports for the Django app and the agent API
EXPOSE 8000 5000

# Default command (this can be overridden in docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]