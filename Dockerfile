# Простой Dockerfile - используем образ с Python и Node.js
FROM python:3.12-slim

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    DOCKER_CONTAINER=true

# Устанавливаем Node.js v22.17.0 с поддержкой разных архитектур
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    xz-utils \
    && ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "arm64" ]; then NODE_ARCH="arm64"; else NODE_ARCH="x64"; fi \
    && curl -fsSL https://nodejs.org/dist/v22.17.0/node-v22.17.0-linux-${NODE_ARCH}.tar.xz -o /tmp/node.tar.xz \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm -f /tmp/node.tar.xz \
    && rm -rf /var/lib/apt/lists/* \
    && node --version \
    && npm --version

# Рабочая директория
WORKDIR /app

# Копируем файлы проекта
COPY . .

# Устанавливаем Python зависимости из requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Node.js зависимости
RUN cd "Player Card Design" && npm install && cd ..

# Устанавливаем Google Chrome для Puppeteer (только для amd64, для arm64 используем Chromium)
# TEMPORARILY DISABLED - Chromium installation takes too long on ARM64
# Uncomment this section when you need card generation functionality
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     wget \
#     gnupg \
#     && ARCH=$(dpkg --print-architecture) \
#     && if [ "$ARCH" = "amd64" ]; then \
#         curl -fsSL https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -o /tmp/chrome.deb \
#         && apt-get install -y --no-install-recommends /tmp/chrome.deb \
#         && rm -f /tmp/chrome.deb; \
#     else \
#         apt-get install -y --no-install-recommends chromium; \
#     fi \
#     && rm -rf /var/lib/apt/lists/*

# Открываем порт
EXPOSE 3000

# Запускаем все сервисы через start-all.sh
CMD ["bash", "./start-all.sh"]
