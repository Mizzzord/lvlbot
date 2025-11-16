# Инструкция по исправлению ошибки сборки

## Проблема
Ошибка: `E: Package 'libasound2' has no installation candidate`

## Решение

### 1. Обновите Dockerfile на сервере

Убедитесь, что в Dockerfile используется `libasound2t64` вместо `libasound2` (строка 43).

### 2. Очистите кэш Docker и пересоберите

```bash
# Остановите все контейнеры
docker-compose down

# Очистите кэш сборки Docker
docker builder prune -af

# Удалите старые образы (опционально)
docker image prune -af

# Пересоберите образ БЕЗ кэша
docker-compose build --no-cache

# Или с очисткой всего
docker system prune -af
docker-compose build --no-cache
```

### 3. Если проблема сохраняется

Проверьте версию Dockerfile на сервере:

```bash
# Проверьте строку 43 в Dockerfile
grep -n "libasound" Dockerfile

# Должно быть:
# 43:    libasound2t64 \
```

Если там все еще `libasound2`, обновите файл:

```bash
# Отредактируйте файл
nano Dockerfile

# Найдите строку с libasound2 и замените на libasound2t64
# Сохраните: Ctrl+O, Enter, Ctrl+X
```

### 4. Альтернативное решение (если libasound2t64 не работает)

Если `libasound2t64` все еще не работает, можно попробовать установить через виртуальный пакет:

```dockerfile
# В Dockerfile замените:
libasound2t64 \

# На:
libasound2t64 | libasound2 \
```

Но обычно `libasound2t64` должен работать в Ubuntu 24.04.

## Проверка после исправления

После успешной сборки проверьте:

```bash
# Запустите контейнер
docker-compose up -d

# Проверьте логи
docker-compose logs -f

# Проверьте healthcheck
curl http://localhost:3000/health
```

## Что было исправлено в Dockerfile

1. ✅ `libasound2` → `libasound2t64` (Ubuntu 24.04 использует новый формат)
2. ✅ Добавлен флаг `--no-install-recommends` для уменьшения размера образа
3. ✅ Улучшена установка Google Chrome (прямое скачивание .deb вместо apt-key)

