# Используем Node.js + Debian (для сборки canvas)
FROM node:20-bullseye

# Устанавливаем системные зависимости для canvas и Python
RUN apt-get update && apt-get install -y \
    python3 python3-pip build-essential \
    libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev pkg-config \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && pip install --upgrade pip \
    && apt-get clean

# Рабочая директория
WORKDIR /app

# Копируем проект
COPY . .

# Даем права на запуск start-all.sh
RUN chmod +x start-all.sh

# Устанавливаем зависимости Node.js и Python
RUN if [ -f "package.json" ]; then npm install; fi
RUN if [ -f "requirements.txt" ]; then pip install -r requirements.txt; fi

# Команда по умолчанию
CMD ["bash", "./start-all.sh"]