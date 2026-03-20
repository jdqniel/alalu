FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv --quiet

# Install dependencies (layer cached independently of source code)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY alalu_bot/ ./alalu_bot/

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "alalu_bot/engine.py"]
