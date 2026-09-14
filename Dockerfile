# ============================================================
# Underground Mine Safety & Rescue System - Dockerfile
# ============================================================

FROM python:3.10-slim

# Set environment variables for Python & application defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5000 \
    SERIAL_PORT=/dev/ttyUSB0 \
    BAUD_RATE=115200

# Set work directory
WORKDIR /app

# Install system dependencies (build-essential for C extensions if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for caching layers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app.py sih_model.py ./
COPY templates/ ./templates/
COPY insights/ ./insights/
COPY data/ ./data/

# Create non-root user with dialout/tty permissions for serial access
RUN useradd -m -u 1000 appuser && \
    usermod -a -G dialout,tty appuser 2>/dev/null || true && \
    chown -R appuser:appuser /app

USER appuser

# Expose web dashboard port
EXPOSE 5000

# Health check to ensure the Flask API is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/data')" || exit 1

# Default command starts the control room web server
CMD ["python", "app.py"]
