# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder

COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /tmp/wheels -r requirements.txt -r requirements-dev.txt

FROM base AS runtime

COPY --from=builder /tmp/wheels /tmp/wheels
RUN pip install --no-cache-dir /tmp/wheels/* && rm -rf /tmp/wheels

COPY . .

RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8501 9000

HEALTHCHECK CMD bash -lc 'if [ "$APP_MODE" = "api" ]; then curl --fail http://localhost:${API_PORT:-9000}/health; else curl --fail http://localhost:${STREAMLIT_PORT:-8501}/_stcore/health; fi'

ENV PREFETCH_ARGS="" \
    APP_MODE=streamlit \
    STREAMLIT_PORT=8501 \
    API_PORT=9000 \
    STREAMLIT_ARGS="" \
    API_ARGS=""

CMD ["bash", "-lc", "if [ -n \"$PREFETCH_ARGS\" ]; then python scripts/prefetch_data.py $PREFETCH_ARGS; fi; STREAMLIT_FLAGS=\"${STREAMLIT_ARGS:- --server.port=$STREAMLIT_PORT --server.address=0.0.0.0}\"; API_FLAGS=\"${API_ARGS:- --host 0.0.0.0 --port=$API_PORT}\"; if [ \"$APP_MODE\" = \"api\" ]; then python scripts/run_api.py $API_FLAGS; else exec streamlit run app.py $STREAMLIT_FLAGS; fi"]
