FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    nmap \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Nuclei
RUN wget -q https://github.com/projectdiscovery/nuclei/releases/latest/download/nuclei_2.9.15_linux_amd64.zip \
    && unzip nuclei_2.9.15_linux_amd64.zip \
    && mv nuclei /usr/local/bin/ \
    && rm nuclei_2.9.15_linux_amd64.zip

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 phantom && chown -R phantom:phantom /app
USER phantom

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]