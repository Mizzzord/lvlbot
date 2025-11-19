# Dockerfile для LVLBot на основе DEPLOYMENT.md
# Использует Python 3.12 и Node.js 22.x

# Базовый образ с Python 3.12
FROM python:3.12-slim

# Метаданные
LABEL maintainer="LVLBot Team"
LABEL description="Telegram Motivation Bot with Node.js card generator"

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    DOCKER_CONTAINER=true \
    DEBIAN_FRONTEND=noninteractive

# Устанавливаем системные зависимости и Node.js 22.x
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    xz-utils \
    ca-certificates \
    gnupg \
    procps \
    && ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "arm64" ]; then NODE_ARCH="arm64"; else NODE_ARCH="x64"; fi \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && node --version \
    && npm --version \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей сначала (для кэширования слоев Docker)
COPY requirements.txt .
COPY "Player Card Design/package.json" "Player Card Design/package-lock.json"* ./Player Card Design/

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Устанавливаем Node.js зависимости
RUN cd "Player Card Design" && \
    npm ci --only=production && \
    cd ..

# Копируем остальные файлы проекта
COPY . .

# Создаем необходимые директории для данных
RUN mkdir -p player_photos player_cards task_submissions logs && \
    chmod -R 755 player_photos player_cards task_submissions logs

# Устанавливаем права на выполнение для скриптов
RUN chmod +x start-all.sh prepare-images.sh

# Открываем порт для Node.js сервиса генерации карточек
EXPOSE 3000

# Healthcheck для проверки работоспособности всех сервисов
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD bash -c "pgrep -f 'node.*server.js' > /dev/null && pgrep -f 'bot.py' > /dev/null && pgrep -f 'moderator_bot.py' > /dev/null && exit 0 || exit 1"

# Запускаем все сервисы через start-all.sh
# Скрипт автоматически определяет, что запущен в Docker и пропускает установку зависимостей
CMD ["bash", "./start-all.sh"]

