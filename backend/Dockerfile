# Use Python 3.11 slim image as base
FROM python:3.11-slim


# System deps (image/crypto/fonts sometimes help pdf libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ghostscript fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies required for pdf2image and other packages
RUN apt-get update && apt-get install -y \
    # For pdf2image (poppler-utils)
    poppler-utils \
    # For potential image processing
    libjpeg-dev \
    libpng-dev \
    # For document format conversions
    pandoc \
    # For building Python packages
    gcc \
    g++ \
    # For downloading files
    curl \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# System deps (image/crypto/fonts sometimes help pdf libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ghostscript fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --uid 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
