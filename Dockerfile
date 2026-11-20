# GigPilot backend — Hugging Face Spaces (Docker) deployment
# Builds from the backend/ subdirectory; push the full repo to HF as-is.
FROM python:3.13-slim

WORKDIR /app

# cryptography / bcrypt / cffi need gcc + libffi
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install from pinned lock — matches the dev venv exactly
COPY backend/requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# Copy backend source (alembic.ini, migrations/, app/, mcp/, Procfile, start.sh)
COPY backend/ .

RUN chmod +x start.sh

# HF Spaces injects PORT=7860; start.sh exports it before honcho reads Procfile
EXPOSE 7860

CMD ["sh", "start.sh"]
