# Многоэтапный Dockerfile для развертывания бота на Ubuntu 24.04
FROM ubuntu:24.04 AS base

# Устанавливаем переменные окружения для избежания интерактивных запросов
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Europe/Moscow \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    DOCKER_CONTAINER=true

# Устанавливаем системные зависимости и базовые инструменты
RUN apt-get update && apt-get install -y \
    # Базовые инструменты
    curl \
    wget \
    git \
    ca-certificates \
    gnupg \
    lsb-release \
    # Python 3.12 и инструменты
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    python3-pip \
    # Системные библиотеки для Python пакетов
    build-essential \
    libssl-dev \
    libffi-dev \
    # Системные библиотеки для Puppeteer/Chromium
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libxshmfence1 \
    # Дополнительные библиотеки для работы с изображениями
    libjpeg-dev \
    libgif-dev \
    librsvg2-dev \
    pkg-config \
    # Утилиты для работы с процессами
    procps \
    && rm -rf /var/lib/apt/lists/*

# Создаем символическую ссылку для python
RUN ln -sf /usr/bin/python3.12 /usr/bin/python && \
    ln -sf /usr/bin/python3.12 /usr/bin/python3 && \
    python3.12 --version

# Устанавливаем Node.js 20.x LTS через NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    node --version && \
    npm --version && \
    rm -rf /var/lib/apt/lists/*

# Создаем пользователя для запуска приложений (безопасность)
RUN groupadd -r appuser && \
    useradd -r -g appuser -m -s /bin/bash appuser

# Рабочая директория
WORKDIR /app

# Копируем файлы зависимостей для кэширования слоев Docker
COPY requirements.txt .
COPY ["Player Card Design/package.json", "Player Card Design/package-lock.json", "./Player Card Design/"]

# Устанавливаем Python зависимости
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir -r requirements.txt

# Устанавливаем Node.js зависимости для генератора карточек
RUN cd "Player Card Design" && \
    npm ci --only=production --no-audit --no-fund && \
    cd ..

# Копируем весь проект
COPY --chown=appuser:appuser . .

# Создаем необходимые директории с правильными правами
RUN mkdir -p player_photos player_cards task_submissions && \
    chown -R appuser:appuser /app && \
    chmod +x start-all.sh

# Устанавливаем переменные окружения для Puppeteer
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome-stable \
    CHROME_BIN=/usr/bin/google-chrome-stable

# Устанавливаем Google Chrome для Puppeteer (вместо Chromium для лучшей совместимости)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/* && \
    google-chrome-stable --version

# Переключаемся на пользователя appuser
USER appuser

# Открываем порты
EXPOSE 3000

# Healthcheck для проверки работоспособности сервисов
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Команда запуска всех сервисов
CMD ["bash", "./start-all.sh"]
