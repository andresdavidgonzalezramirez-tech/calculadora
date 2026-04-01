FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /entrypoint.sh

USER appuser

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request;port=os.getenv('PORT',os.getenv('APP_PORT','3000'));urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=3)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
