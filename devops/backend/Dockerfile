FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir "uv>=0.8"

WORKDIR /workspace/backend

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./
COPY devops/backend/docker-entrypoint.sh /usr/local/bin/pai-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/pai-entrypoint \
    && chmod +x /usr/local/bin/pai-entrypoint

ENTRYPOINT ["/usr/local/bin/pai-entrypoint"]
CMD ["api"]
