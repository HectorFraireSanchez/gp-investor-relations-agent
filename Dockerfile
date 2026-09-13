FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Allow the existing vector-store setup to write /app/.env when needed.
RUN useradd --create-home --uid 10001 app && chown app:app /app

# backend/ includes the synthetic SQLite database at backend/data/northstar.db.
COPY --chown=app:app backend/ ./backend/
COPY --chown=app:app documents/ ./documents/

USER app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
