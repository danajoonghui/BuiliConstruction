FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN addgroup --system buili && adduser --system --ingroup buili buili
WORKDIR /app

COPY apps/api/pyproject.toml apps/api/README.md ./
COPY apps/api/src ./src
COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic
COPY buili_spatial ./buili_spatial
RUN pip install --upgrade pip && pip install .

RUN mkdir -p /app/.data && chown -R buili:buili /app
USER buili
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"

CMD ["uvicorn", "buili_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
