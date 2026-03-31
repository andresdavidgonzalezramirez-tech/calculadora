FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
