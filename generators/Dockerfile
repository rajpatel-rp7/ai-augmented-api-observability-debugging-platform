FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml generate_telemetry.py ./
RUN pip install --upgrade pip && pip install .

ENTRYPOINT ["python", "generate_telemetry.py"]
CMD ["--api-url", "http://api:8000", "--loop", "--interval", "45", "--burst", "6"]
