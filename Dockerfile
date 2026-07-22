# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/usr/local -r requirements.txt

# Stage 2: Production
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Fix numpy/pandas binary incompatibility by reinstalling both
RUN pip install --no-cache-dir --upgrade --force-reinstall numpy pandas

# Copy application files
COPY app.py config.py ./
COPY core/ ./core/
COPY modules/ ./modules/
COPY templates/ ./templates/
COPY static/ ./static/
COPY .env.example .

# Copy browser extension and build package
COPY browser_extension/ ./browser_extension/
COPY bin/build-extension.sh ./bin/build-extension.sh
RUN mkdir -p static/dist && chmod +x bin/build-extension.sh && bin/build-extension.sh

# Create non-root user for security
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]