FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y \
  python3 python3-pip \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Node deps
COPY package*.json ./
RUN npm ci --omit=dev || npm install --omit=dev

# App code
COPY . .

# Python deps
RUN pip3 install --no-cache-dir -r worker/requirements.txt

# Data dir (compartilhado entre API e Worker porque é o mesmo container)
RUN mkdir -p /app/data

ENV PORT=80
ENV DATA_DIR=/app/data
ENV SITE_DIR=/app/site

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
