FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src
ENTRYPOINT ["python", "-m", "coding_agents.cli_code_agent"]
