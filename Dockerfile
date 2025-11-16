# Простой Dockerfile - используем образ с Python и Node.js
FROM python:3.12-slim

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    NODE_ENV=production



# Рабочая директория
WORKDIR /app

# Копируем файлы проекта
COPY . .

# Устанавливаем Python зависимости из requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Node.js зависимости
RUN cd "Player Card Design" && npm install && cd ..

# Устанавливаем Google Chrome для Puppeteer
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm -f /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

# Открываем порт
EXPOSE 3000

# Запускаем все сервисы через start-all.sh
CMD ["bash", "./start-all.sh"]
