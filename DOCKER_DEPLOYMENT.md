# Инструкция по развертыванию LVLBot через Docker

Этот документ описывает процесс развертывания LVLBot на удаленном сервере с использованием Docker, основанный на [DEPLOYMENT.md](./DEPLOYMENT.md).

## Преимущества Docker развертывания

- ✅ Изолированное окружение
- ✅ Воспроизводимость развертывания
- ✅ Простое управление зависимостями
- ✅ Легкое масштабирование
- ✅ Упрощенное обновление

## Предварительные требования

На сервере должны быть установлены:
- Docker (версия 20.10+)
- Docker Compose (версия 2.0+)

## Быстрый старт

### 1. Подготовка сервера

```bash
# Подключение к серверу
ssh root@176.124.218.195

# Проверка установки Docker
docker --version
docker-compose --version

# Если Docker не установлен, установите его:
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

### 2. Клонирование репозитория

```bash
cd /root
rm -rf lvlbot 2>/dev/null
git clone -b database-lockal --single-branch https://github.com/Mizzzord/lvlbot.git
cd lvlbot
```

### 3. Копирование .env файла

```bash
# Скопируйте локальный .env файл на сервер
# С локальной машины:
scp /Users/staf/Desktop/Mycode/lvlbot/.env root@176.124.218.195:/root/lvlbot/.env

# Или создайте его вручную на сервере на основе env.example
```

### 4. Создание директорий для данных

```bash
mkdir -p data/player_photos data/player_cards data/task_submissions logs
chmod -R 755 data logs
```

### 5. Сборка и запуск контейнера

```bash
# Сборка образа
docker-compose build

# Запуск контейнера в фоновом режиме
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f
```

## Детальное описание процесса

### Шаг 1: Сборка Docker образа

**Команда:**
```bash
docker-compose build
```

**Что происходит:**
1. Docker читает `Dockerfile`
2. Использует базовый образ `python:3.12-slim`
3. Устанавливает Node.js 22.x через официальный репозиторий NodeSource
4. Устанавливает Python зависимости из `requirements.txt`
5. Устанавливает Node.js зависимости из `package.json`
6. Копирует файлы проекта в образ
7. Настраивает рабочую директорию и права доступа

**Время выполнения:** 5-10 минут (в зависимости от скорости интернета)

### Шаг 2: Запуск контейнера

**Команда:**
```bash
docker-compose up -d
```

**Что происходит:**
1. Создается контейнер из собранного образа
2. Монтируются volumes для персистентности данных
3. Загружаются переменные окружения из `.env`
4. Запускается скрипт `start-all.sh`, который запускает:
   - Node.js сервис генерации карточек (порт 3000)
   - Основной бот (`bot.py`)
   - Модераторский бот (`moderator_bot.py`)

**Проверка:**
```bash
# Статус контейнера
docker-compose ps

# Логи в реальном времени
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f lvlbot
```

### Шаг 3: Проверка работоспособности

**Проверка процессов внутри контейнера:**
```bash
docker-compose exec lvlbot ps aux | grep -E 'bot.py|moderator_bot.py|node.*server.js'
```

**Проверка портов:**
```bash
docker-compose exec lvlbot netstat -tlnp | grep 3000
# или
docker-compose exec lvlbot ss -tlnp | grep 3000
```

**Проверка логов:**
```bash
# Все логи
docker-compose logs --tail=100

# Логи модераторского бота
docker-compose exec lvlbot tail -f moderator_bot.log
```

## Управление контейнером

### Просмотр логов

```bash
# Все логи
docker-compose logs -f

# Последние 100 строк
docker-compose logs --tail=100

# Логи за последний час
docker-compose logs --since 1h
```

### Перезапуск контейнера

```bash
# Мягкий перезапуск (graceful shutdown)
docker-compose restart

# Полный перезапуск (пересоздание контейнера)
docker-compose down
docker-compose up -d
```

### Остановка контейнера

```bash
# Остановка без удаления
docker-compose stop

# Остановка и удаление контейнера
docker-compose down

# Остановка с удалением volumes (ОСТОРОЖНО: удалит данные!)
docker-compose down -v
```

### Обновление бота

```bash
# 1. Остановить контейнер
docker-compose stop

# 2. Обновить код
git pull origin database-lockal

# 3. Пересобрать образ (если изменились зависимости)
docker-compose build --no-cache

# 4. Запустить заново
docker-compose up -d

# 5. Проверить логи
docker-compose logs -f
```

### Вход в контейнер

```bash
# Интерактивная сессия
docker-compose exec lvlbot bash

# Выполнение команды
docker-compose exec lvlbot python3 bot.py --help
```

## Структура volumes

Данные сохраняются в следующих директориях на хосте:

```
/root/lvlbot/
├── data/
│   ├── bot_database.db          # SQLite база данных
│   ├── player_photos/           # Фотографии игроков
│   ├── player_cards/            # Сгенерированные карточки
│   └── task_submissions/        # Задания пользователей
└── logs/                        # Логи приложения
```

Эти директории монтируются в контейнер, поэтому данные сохраняются при перезапуске контейнера.

## Мониторинг и отладка

### Проверка использования ресурсов

```bash
# Статистика контейнера
docker stats lvlbot-prod

# Детальная информация
docker inspect lvlbot-prod
```

### Healthcheck

Dockerfile включает healthcheck, который проверяет доступность Node.js сервиса:

```bash
# Статус healthcheck
docker inspect --format='{{.State.Health.Status}}' lvlbot-prod

# История healthcheck
docker inspect --format='{{json .State.Health}}' lvlbot-prod | jq
```

### Отладка проблем

**Проблема: Контейнер не запускается**
```bash
# Проверьте логи
docker-compose logs

# Проверьте конфигурацию
docker-compose config

# Запустите в интерактивном режиме для отладки
docker-compose run --rm lvlbot bash
```

**Проблема: Боты не работают**
```bash
# Проверьте процессы внутри контейнера
docker-compose exec lvlbot ps aux

# Проверьте переменные окружения
docker-compose exec lvlbot env | grep -E 'BOT_TOKEN|MODERATOR'

# Проверьте логи
docker-compose logs -f
```

**Проблема: База данных не сохраняется**
```bash
# Проверьте монтирование volumes
docker inspect lvlbot-prod | grep -A 10 Mounts

# Проверьте права доступа
ls -la data/
```

## Оптимизация для продакшена

### Использование .env файла

Убедитесь, что `.env` файл содержит все необходимые переменные:

```env
BOT_TOKEN=your_main_bot_token
MODERATOR_BOT_TOKEN=your_moderator_bot_token
POLZA_API_KEY=your_polza_api_key
WATA_TOKEN=your_wata_token
ADMIN_TELEGRAM_IDS=123456789,987654321
USE_POSTGRES=false
DATABASE_PATH=bot_database.db
```

### Настройка reverse proxy (nginx)

Для доступа к Node.js сервису извне настройте nginx:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Автоматический перезапуск

Docker Compose автоматически перезапускает контейнер при сбоях благодаря `restart: unless-stopped`.

Для более продвинутого управления используйте systemd:

```bash
# Создайте systemd сервис
cat > /etc/systemd/system/lvlbot-docker.service << EOF
[Unit]
Description=LVLBot Docker Container
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/root/lvlbot
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Активируйте сервис
systemctl daemon-reload
systemctl enable lvlbot-docker
systemctl start lvlbot-docker
```

## Бэкапы

### Бэкап базы данных

```bash
# Создать бэкап
docker-compose exec lvlbot cp /app/bot_database.db /app/bot_database.db.backup.$(date +%Y%m%d_%H%M%S)

# Или с хоста
cp data/bot_database.db data/backups/bot_database.db.$(date +%Y%m%d_%H%M%S)
```

### Автоматический бэкап через cron

```bash
# Добавьте в crontab
0 2 * * * cd /root/lvlbot && cp data/bot_database.db data/backups/bot_database.db.$(date +\%Y\%m\%d)
```

## Сравнение с обычным развертыванием

| Аспект | Обычное развертывание | Docker развертывание |
|--------|----------------------|---------------------|
| Установка зависимостей | Вручную на сервере | Автоматически в образе |
| Изоляция | Зависит от системы | Полная изоляция |
| Воспроизводимость | Средняя | Высокая |
| Обновление | Сложное | Простое (пересборка) |
| Откат изменений | Сложный | Простой (старый образ) |
| Масштабирование | Сложное | Простое (несколько контейнеров) |

## Резюме

Docker развертывание предоставляет:
- ✅ Простоту установки и обновления
- ✅ Изолированное окружение
- ✅ Воспроизводимость на разных серверах
- ✅ Легкое управление через docker-compose
- ✅ Автоматический перезапуск при сбоях

Для начала работы выполните:
```bash
git clone -b database-lockal --single-branch https://github.com/Mizzzord/lvlbot.git
cd lvlbot
# Скопируйте .env файл
docker-compose up -d
```

Бот будет доступен и готов к работе!

