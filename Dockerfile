FROM node:20-bookworm-slim

# Python + dependências básicas
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv tzdata ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Node deps
COPY api/package*.json ./api/
RUN npm ci --prefix ./api

# Python deps (se existir requirements.txt)
COPY worker/requirements.txt ./worker/requirements.txt
RUN if [ -f "./worker/requirements.txt" ]; then pip3 install --no-cache-dir -r ./worker/requirements.txt; fi

# Código todo
COPY . .

# Ambiente padrão (pode sobrescrever no DigitalOcean)
ENV PORT=8080
ENV DATA_DIR=/app/data
ENV SITE_DIR=/app/site

EXPOSE 8080

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
