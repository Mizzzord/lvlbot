# Быстрый старт с Docker

## Минимальные требования

- Ubuntu 24.04 (или любая система с Docker)
- 2GB RAM минимум
- 10GB свободного места

## Установка за 5 минут

### 1. Установка Docker (если еще не установлен)

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Клонирование и настройка

```bash
# Клонирование проекта
git clone <your-repo> lvlbot
cd lvlbot

# Создание .env файла
cp env.example .env
nano .env  # Заполните необходимые токены

# Создание директорий для данных
mkdir -p data/player_photos data/player_cards data/task_submissions logs
```

### 3. Запуск

```bash
# Сборка образа (первый раз, займет 5-10 минут)
docker-compose build

# Запуск контейнера
docker-compose up -d

# Просмотр логов
docker-compose logs -f
```

### 4. Проверка

```bash
# Проверка статуса
docker-compose ps

# Проверка healthcheck
curl http://localhost:3000/health
```

## Основные команды

```bash
# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Просмотр логов
docker-compose logs -f

# Вход в контейнер
docker-compose exec motivation-bot bash

# Обновление после изменений в коде
docker-compose build --no-cache
docker-compose up -d
```

## Production развертывание

```bash
# Использование production конфигурации
docker-compose -f docker-compose.prod.yml up -d

# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f
```

## Решение проблем

### Контейнер не запускается

```bash
# Проверка логов
docker-compose logs motivation-bot

# Проверка конфигурации
docker-compose config
```

### Проблемы с правами доступа

```bash
# Исправление прав на данные
sudo chown -R $USER:$USER data/
chmod -R 755 data/
```

### Очистка Docker

```bash
# Удаление неиспользуемых образов
docker system prune -a

# Удаление всех контейнеров и образов проекта
docker-compose down -v --rmi all
```

## Структура проекта в Docker

```
/app/
├── bot.py                 # Основной бот
├── moderator_bot.py       # Модераторский бот
├── Player Card Design/    # Node.js сервис генерации карточек
│   └── server.js
├── player_photos/         # Фото пользователей
├── player_cards/          # Сгенерированные карточки
├── task_submissions/      # Задания пользователей
└── bot_database.db        # База данных SQLite
```

## Переменные окружения

Основные переменные в `.env`:

- `BOT_TOKEN` - токен Telegram бота (обязательно)
- `MODERATOR_BOT_TOKEN` - токен модераторского бота (обязательно)
- `POLZA_API_KEY` - ключ API для ИИ функций
- `ADMIN_TELEGRAM_IDS` - ID администраторов через запятую
- `MODERATOR_TELEGRAM_IDS` - ID модераторов через запятую

Полный список смотрите в `env.example`.

