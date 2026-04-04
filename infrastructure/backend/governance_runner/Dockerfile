# Build from repository root:
#   docker build -f infrastructure/backend/governance_runner/Dockerfile -t governance-runner:latest .
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastapi>=0.115,<1" \
    "uvicorn[standard]>=0.30,<1" \
    "httpx>=0.27,<1" \
    "pydantic>=2,<3"

COPY governance_engine /app/governance_engine
COPY runtime /app/runtime
COPY infrastructure/backend/governance_runner/app /app/app

ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
