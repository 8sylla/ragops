FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN useradd --create-home --uid 10001 ragops

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Sample corpus by default; mount the full archive and set RAGOPS_CORPUS to use it.
COPY data/sample ./data/sample
ENV RAGOPS_CORPUS=/app/data/sample

USER ragops
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "ragops.api:app", "--host", "0.0.0.0", "--port", "8000"]
