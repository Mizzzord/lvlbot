#!/bin/bash

# Скрипт для предварительной загрузки Docker образов
# Используйте на локальном компьютере с авторизацией в Docker Hub

set -e

echo "🔄 Подготовка Docker образов для Motivation Bot..."
echo "Этот скрипт нужно запускать на компьютере с авторизацией в Docker Hub"
echo ""

# Проверка авторизации
if ! docker info 2>/dev/null | grep -q "Username"; then
    echo "❌ Вы не авторизованы в Docker Hub!"
    echo "Выполните: docker login"
    exit 1
fi

echo "✅ Авторизация в Docker Hub подтверждена"

# Образы для загрузки
IMAGES=(
    "node:18-bullseye-slim"
    "python:3.11-slim"
)

# Загрузка образов
echo "📥 Загрузка образов..."
for image in "${IMAGES[@]}"; do
    echo "Загрузка $image..."
    if docker pull "$image"; then
        echo "✅ $image загружен"
    else
        echo "❌ Ошибка загрузки $image"
    fi
done

echo ""
echo "💾 Сохранение образов в архивы..."

# Сохранение образов
docker save node:18-bullseye-slim > motivation-node.tar
docker save python:3.11-slim > motivation-python.tar

echo "✅ Образы сохранены:"
echo "  - motivation-node.tar (Node.js 18)"
echo "  - motivation-python.tar (Python 3.11)"

echo ""
echo "📤 Теперь перенесите файлы .tar на сервер и выполните:"
echo "  docker load < motivation-node.tar"
echo "  docker load < motivation-python.tar"
echo ""
echo "🎉 Подготовка завершена!"
