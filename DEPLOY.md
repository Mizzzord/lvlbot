# Инструкция по развертыванию бота на Ubuntu 24.04

## Требования

- Ubuntu 24.04 Server
- Docker 24.0+ и Docker Compose 2.20+
- Минимум 2GB RAM, 10GB свободного места на диске

## Быстрый старт

### 1. Установка Docker и Docker Compose

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y curl wget git ca-certificates gnupg lsb-release

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version
```

### 2. Клонирование проекта

```bash
# Клонирование репозитория
git clone <your-repo-url> lvlbot
cd lvlbot

# Или загрузка проекта через scp/sftp
```

### 3. Настройка переменных окружения

```bash
# Копирование примера файла окружения
cp env.example .env

# Редактирование .env файла
nano .env
```

Заполните необходимые переменные:
- `BOT_TOKEN` - токен основного бота Telegram
- `MODERATOR_BOT_TOKEN` - токен модераторского бота
- `POLZA_API_KEY` - ключ API для Polza.ai
- `WATA_TOKEN` - токен для WATA API (опционально)
- `ADMIN_TELEGRAM_IDS` - ID администраторов через запятую
- `MODERATOR_TELEGRAM_IDS` - ID модераторов через запятую

### 4. Создание директорий для данных

```bash
# Создание директорий для персистентных данных
mkdir -p data logs
mkdir -p data/player_photos data/player_cards data/task_submissions

# Установка прав доступа
chmod -R 755 data logs
```

### 5. Сборка и запуск контейнера

#### Для разработки:

```bash
# Сборка образа
docker-compose build

# Запуск контейнера
docker-compose up -d

# Просмотр логов
docker-compose logs -f
```

#### Для production:

```bash
# Сборка образа
docker-compose -f docker-compose.prod.yml build

# Запуск контейнера
docker-compose -f docker-compose.prod.yml up -d

# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f
```

### 6. Проверка работоспособности

```bash
# Проверка статуса контейнера
docker-compose ps

# Проверка healthcheck
docker-compose exec motivation-bot curl http://localhost:3000/health

# Просмотр логов
docker-compose logs -f motivation-bot
```

## Управление контейнером

### Остановка

```bash
docker-compose down
# или для production
docker-compose -f docker-compose.prod.yml down
```

### Перезапуск

```bash
docker-compose restart
# или для production
docker-compose -f docker-compose.prod.yml restart
```

### Обновление

```bash
# Получение последних изменений
git pull

# Пересборка образа
docker-compose build --no-cache

# Перезапуск с новым образом
docker-compose up -d
```

### Просмотр логов

```bash
# Все логи
docker-compose logs -f

# Последние 100 строк
docker-compose logs --tail=100

# Логи конкретного сервиса
docker-compose logs -f motivation-bot
```

## Настройка Nginx как Reverse Proxy (рекомендуется для production)

### Установка Nginx

```bash
sudo apt install -y nginx
```

### Создание конфигурации

```bash
sudo nano /etc/nginx/sites-available/motivation-bot
```

Добавьте следующую конфигурацию:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Активация конфигурации

```bash
sudo ln -s /etc/nginx/sites-available/motivation-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Настройка SSL с Let's Encrypt (опционально)

```bash
# Установка Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d your-domain.com

# Автоматическое обновление
sudo certbot renew --dry-run
```

## Мониторинг и обслуживание

### Проверка использования ресурсов

```bash
docker stats motivation-bot
```

### Резервное копирование базы данных

```bash
# Создание бэкапа
docker-compose exec motivation-bot cp /app/bot_database.db /app/backup_$(date +%Y%m%d_%H%M%S).db

# Или через volume
cp data/bot_database.db backups/bot_database_$(date +%Y%m%d_%H%M%S).db
```

### Очистка старых образов

```bash
# Удаление неиспользуемых образов
docker system prune -a

# Удаление старых логов
docker-compose logs --tail=0
```

## Решение проблем

### Контейнер не запускается

```bash
# Проверка логов
docker-compose logs motivation-bot

# Проверка конфигурации
docker-compose config

# Запуск в интерактивном режиме
docker-compose run --rm motivation-bot bash
```

### Проблемы с правами доступа

```bash
# Проверка прав на файлы
ls -la data/

# Исправление прав
sudo chown -R $USER:$USER data/
chmod -R 755 data/
```

### Проблемы с Puppeteer

```bash
# Проверка установки Chrome
docker-compose exec motivation-bot google-chrome-stable --version

# Проверка переменных окружения
docker-compose exec motivation-bot env | grep PUPPETEER
```

## Автозапуск при перезагрузке сервера

Docker Compose с `restart: always` автоматически запускает контейнеры при перезагрузке системы.

Для дополнительной надежности можно создать systemd service:

```bash
sudo nano /etc/systemd/system/motivation-bot.service
```

```ini
[Unit]
Description=Motivation Bot Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/lvlbot
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Активация:

```bash
sudo systemctl daemon-reload
sudo systemctl enable motivation-bot.service
sudo systemctl start motivation-bot.service
```

## Поддержка

При возникновении проблем проверьте:
1. Логи контейнера: `docker-compose logs -f`
2. Статус контейнера: `docker-compose ps`
3. Использование ресурсов: `docker stats`
4. Доступность портов: `netstat -tulpn | grep 3000`

