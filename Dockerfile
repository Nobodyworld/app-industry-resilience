# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose default ports for Streamlit and API modes
EXPOSE 8501 9000

# Health check will dynamically target the active mode
HEALTHCHECK CMD bash -lc 'if [ "$APP_MODE" = "api" ]; then curl --fail http://localhost:${API_PORT:-9000}/health; else curl --fail http://localhost:${STREAMLIT_PORT:-8501}/_stcore/health; fi'

# Optional runtime configuration
ENV PREFETCH_ARGS="" \
    APP_MODE=streamlit \
    STREAMLIT_PORT=8501 \
    API_PORT=9000 \
    STREAMLIT_ARGS="" \
    API_ARGS=""

# Run optional cache prefetch before starting the selected interface
CMD ["bash", "-lc", "if [ -n \"$PREFETCH_ARGS\" ]; then python scripts/prefetch_data.py $PREFETCH_ARGS; fi; STREAMLIT_FLAGS=\"${STREAMLIT_ARGS:- --server.port=$STREAMLIT_PORT --server.address=0.0.0.0}\"; API_FLAGS=\"${API_ARGS:- --host 0.0.0.0 --port=$API_PORT}\"; if [ \"$APP_MODE\" = \"api\" ]; then python scripts/run_api.py $API_FLAGS; else exec streamlit run app.py $STREAMLIT_FLAGS; fi"]
