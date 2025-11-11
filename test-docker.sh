#!/bin/bash

# Скрипт для тестирования Docker конфигурации
# Использование: ./test-docker.sh

set -e

echo "🔍 Проверка Docker конфигурации..."
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция проверки
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
        return 0
    else
        echo -e "${RED}❌ $1${NC}"
        return 1
    fi
}

# 1. Проверка наличия Docker
echo "1️⃣  Проверка Docker..."
if command -v docker &> /dev/null; then
    docker --version
    check "Docker установлен"
else
    echo -e "${RED}❌ Docker не установлен!${NC}"
    exit 1
fi

# 2. Проверка Docker Compose
echo ""
echo "2️⃣  Проверка Docker Compose..."
if command -v docker-compose &> /dev/null; then
    docker-compose --version
    check "docker-compose установлен"
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    docker compose version
    check "docker compose (plugin) установлен"
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}❌ Docker Compose не установлен!${NC}"
    exit 1
fi

# 3. Проверка файлов конфигурации
echo ""
echo "3️⃣  Проверка файлов конфигурации..."

if [ -f "Dockerfile.nodejs" ]; then
    check "Dockerfile.nodejs существует"
else
    echo -e "${RED}❌ Dockerfile.nodejs не найден!${NC}"
    exit 1
fi

if [ -f "Dockerfile.python" ]; then
    check "Dockerfile.python существует"
else
    echo -e "${RED}❌ Dockerfile.python не найден!${NC}"
    exit 1
fi

if [ -f "docker-compose.yml" ]; then
    check "docker-compose.yml существует"
else
    echo -e "${RED}❌ docker-compose.yml не найден!${NC}"
    exit 1
fi

# 4. Проверка синтаксиса docker-compose.yml
echo ""
echo "4️⃣  Проверка синтаксиса docker-compose.yml..."
$COMPOSE_CMD config > /dev/null 2>&1
check "Синтаксис docker-compose.yml корректен"

# 5. Проверка наличия необходимых файлов
echo ""
echo "5️⃣  Проверка необходимых файлов..."

FILES_TO_CHECK=(
    "package.json"
    "server.js"
    "card-generator.js"
    "requirements.txt"
    "bot.py"
    "moderator_bot.py"
    "database.py"
    "models.py"
    "config.py"
    "openrouter_config.py"
    "subscription_config.py"
    "wata_api.py"
    "moderator_config.py"
)

MISSING_FILES=()
for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${NC} $file"
    else
        echo -e "${RED}❌${NC} $file"
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Отсутствуют файлы: ${MISSING_FILES[*]}${NC}"
fi

# 6. Проверка .env файла
echo ""
echo "6️⃣  Проверка переменных окружения..."
if [ -f ".env" ]; then
    check ".env файл существует"
    
    # Проверка ключевых переменных
    if grep -q "BOT_TOKEN=" .env && ! grep -q "BOT_TOKEN=your_main_bot_token_here" .env; then
        check "BOT_TOKEN настроен"
    else
        echo -e "${YELLOW}⚠️  BOT_TOKEN не настроен${NC}"
    fi
    
    if grep -q "MODERATOR_BOT_TOKEN=" .env && ! grep -q "MODERATOR_BOT_TOKEN=your_moderator_bot_token_here" .env; then
        check "MODERATOR_BOT_TOKEN настроен"
    else
        echo -e "${YELLOW}⚠️  MODERATOR_BOT_TOKEN не настроен${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  .env файл не найден. Создайте его из env.example${NC}"
fi

# 7. Проверка портов
echo ""
echo "7️⃣  Проверка доступности портов..."
if command -v lsof &> /dev/null; then
    if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${YELLOW}⚠️  Порт 3000 уже занят${NC}"
        lsof -Pi :3000 -sTCP:LISTEN 2>/dev/null || echo "Не удалось получить детали процесса"
    else
        check "Порт 3000 свободен"
    fi
elif command -v netstat &> /dev/null; then
    if netstat -tulpn 2>/dev/null | grep ":3000 " >/dev/null; then
        echo -e "${YELLOW}⚠️  Порт 3000 уже занят${NC}"
        netstat -tulpn 2>/dev/null | grep ":3000 "
    else
        check "Порт 3000 свободен"
    fi
else
    echo -e "${YELLOW}⚠️  Невозможно проверить порты (нет lsof или netstat)${NC}"
fi

# 8. Тестовая сборка (опционально)
echo ""
echo "8️⃣  Тестовая проверка сборки..."
read -p "Запустить тестовую сборку образов? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🏗️  Сборка Node.js образа..."
    docker build -f Dockerfile.nodejs -t test-card-generator . > /dev/null 2>&1
    check "Node.js образ собирается успешно"
    
    echo "🏗️  Сборка Python образа..."
    docker build -f Dockerfile.python -t test-bots . > /dev/null 2>&1
    check "Python образ собирается успешно"
    
    # Очистка тестовых образов
    echo "🧹 Очистка тестовых образов..."
    docker rmi test-card-generator test-bots > /dev/null 2>&1 || true
fi

# Итоги
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Проверка завершена!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Следующие шаги:"
echo "1. Убедитесь, что .env файл настроен с правильными токенами"
echo "2. Запустите: $COMPOSE_CMD up -d --build"
echo "3. Проверьте логи: $COMPOSE_CMD logs -f"
echo ""
echo "📖 Подробная документация: DOCKER_DEPLOY.md"
