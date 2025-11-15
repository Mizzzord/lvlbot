<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Документация по подключению Telegram бота к базе данных PostgreSQL на Timeweb

Я провел полное изучение вашей базы данных на Timeweb и собрал подробную документацию по подключению.

## Общая информация о базе данных

**Название кластера:** Brave Plover
**ID кластера:** 4105635
**Тип СУБД:** PostgreSQL 18
**Статус:** Включена
**Конфигурация:** 1 CPU -  2 ГБ RAM -  20 ГБ NVMe

### Параметры подключения

- **Имя базы данных:** Go_prime
- **Пользователь:** Go_prime_main
- **Пароль:** [скрыт, доступен в панели управления]
- **Порт:** 5432


### Сетевые адреса

- **Публичный IP:** 77.232.136.27
- **Приватный IP:** 192.168.0.4
- **Домен:** ce577c3306225bd06a426f70.twc1.net


### Хранилище

- **Занято:** 0.1 ГБ (1%)
- **Свободно:** 19.9 ГБ
- **Всего:** 20 ГБ

***

## Способы подключения к базе данных

### 1. Подключение через Python (рекомендуется для Telegram ботов)

#### Шаг 1: Установка библиотеки

```bash
pip install psycopg2-binary
```


#### Шаг 2: Установка сертификата безопасности (для macOS)

```bash
mkdir -p ~/.cloud-certs && \
curl -o ~/.cloud-certs/root.crt "https://st.timeweb.com/cloud-static/ca.crt" && \
chmod 0600 ~/.cloud-certs/root.crt
```


#### Шаг 3: Код подключения

```python
#!/usr/bin/python
import os
import psycopg2

conn = psycopg2.connect(
    host="ce577c3306225bd06a426f70.twc1.net",
    database="Go_prime",
    user="Go_prime_main",
    password="ВАШ_ПАРОЛЬ",  # Замените на реальный пароль
    sslmode='verify-full',
    sslrootcert=os.path.expanduser('~/.cloud-certs/root.crt')
)

# Пример использования
cursor = conn.cursor()
cursor.execute("SELECT version();")
db_version = cursor.fetchone()
print(f"PostgreSQL версия: {db_version}")
cursor.close()
conn.close()
```


***

### 2. Подключение через Node.JS

#### Шаг 1: Установка библиотеки

```bash
npm install pg
```


#### Шаг 2: Установка сертификата

```bash
mkdir -p ~/.cloud-certs && \
curl -o ~/.cloud-certs/root.crt "https://st.timeweb.com/cloud-static/ca.crt" && \
chmod 0600 ~/.cloud-certs/root.crt
```


#### Шаг 3: Код подключения

```javascript
const fs = require('fs');
const path = require('path');
const os = require('os');
const { Client } = require('pg');

const client = new Client({
    user: 'Go_prime_main',
    host: 'ce577c3306225bd06a426f70.twc1.net',
    database: 'Go_prime',
    password: 'ВАШ_ПАРОЛЬ',
    port: 5432,
    ssl: {
        rejectUnauthorized: true,
        ca: fs.readFileSync(path.join(os.homedir(), '.cloud-certs', 'root.crt'), 'utf-8')
    }
});

client.connect();
```


***

### 3. Подключение через PHP

#### Шаг 1: Установка сертификата

```bash
mkdir -p ~/.cloud-certs && \
curl -o ~/.cloud-certs/root.crt "https://st.timeweb.com/cloud-static/ca.crt" && \
chmod 0600 ~/.cloud-certs/root.crt
```


#### Шаг 2: Проверка расширений в php.ini

Убедитесь, что активированы следующие расширения:

- extension=openssl
- extension=pdo_pgsql
- extension=pgsql


#### Шаг 3: Код подключения

```php
<?php
$certPath = getenv('HOME') . '/.cloud-certs/root.crt';
$dsn = "pgsql:host=ce577c3306225bd06a426f70.twc1.net;dbname=Go_prime;sslmode=verify-full;sslrootcert={$certPath}";
$myPDO = new PDO(
    $dsn,
    'Go_prime_main',
    'ВАШ_ПАРОЛЬ'
);
?>
```


***

### 4. Подключение через .env файл

Создайте файл `.env` в корне вашего проекта:

```env
POSTGRESQL_HOST=ce577c3306225bd06a426f70.twc1.net
POSTGRESQL_PORT=5432
POSTGRESQL_USER=Go_prime_main
POSTGRESQL_PASSWORD=ВАШ_ПАРОЛЬ
POSTGRESQL_DBNAME=Go_prime
```

Затем используйте библиотеку для работы с переменными окружения (например, `python-dotenv` для Python).

***

### 5. Подключение через DSN строку

```
pgsql:host=ce577c3306225bd06a426f70.twc1.net;port=5432;dbname=Go_prime;user=Go_prime_main;password=ВАШ_ПАРОЛЬ
```


***

### 6. Подключение через командную строку (psql)

#### Установка клиента PostgreSQL:

**Ubuntu/Debian:**

```bash
sudo apt install postgresql-client
```

**macOS:**

```bash
brew install postgresql
```


#### Подключение:

```bash
export PGSSLROOTCERT=$HOME/.cloud-certs/root.crt
psql 'postgresql://Go_prime_main:ВАШ_ПАРОЛЬ@ce577c3306225bd06a426f70.twc1.net:5432/Go_prime?sslmode=verify-full'
```


***

## Типы подключения

### По домену (рекомендуется)

- **Host:** ce577c3306225bd06a426f70.twc1.net
- **Требуется:** SSL сертификат
- **Преимущества:** Защищенное TLS соединение


### По публичному IP

- **Host:** 77.232.136.27
- **Порт:** 5432
- **Использование:** Доступ из интернета


### По приватному IP

- **Host:** 192.168.0.4
- **Порт:** 5432
- **Использование:** Только внутри приватной сети Timeweb (Fair Ganymede)

***

## Сетевые настройки

- **Приватная сеть:** Fair Ganymede
- **Публичный доступ:** Включен
- **Firewall:** Не настроен (можно настроить в панели управления)

***

## Пример интеграции с Telegram ботом на Python (aiogram)

```python
import os
import psycopg2
from psycopg2 import pool
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Создание пула подключений к БД
db_pool = psycopg2.pool.SimpleConnectionPool(
    1, 20,
    host="ce577c3306225bd06a426f70.twc1.net",
    database="Go_prime",
    user="Go_prime_main",
    password=os.getenv("DB_PASSWORD"),
    sslmode='verify-full',
    sslrootcert=os.path.expanduser('~/.cloud-certs/root.crt')
)

# Инициализация бота
bot = Bot(token="YOUR_BOT_TOKEN")
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    # Получение подключения из пула
    conn = db_pool.getconn()
    cursor = conn.cursor()
    
    # Сохранение пользователя в БД
    cursor.execute("""
        INSERT INTO users (telegram_id, username, first_name, join_date)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (telegram_id) DO NOTHING
    """, (message.from_user.id, message.from_user.username, message.from_user.first_name))
    
    conn.commit()
    cursor.close()
    db_pool.putconn(conn)
    
    await message.answer("Привет! Вы успешно зарегистрированы.")

if __name__ == "__main__":
    dp.run_polling(bot)
```


***

## Дополнительная информация

### Мониторинг (Prometheus)

- **node_exporter:** http://192.168.0.4:9100
- **postgres_exporter:** http://192.168.0.4:9308


### Веб-интерфейс

Доступ через Adminer - кнопка "Веб-интерфейс" в панели управления.[^1]

### Резервные копии

Настраиваются во вкладке "Бэкапы" в панели управления.

### Официальная документация

- [PostgreSQL на Timeweb Cloud](https://timeweb.cloud/docs/postgresql)[^2]
- [Создание кластера баз данных](https://timeweb.cloud/docs)[^3]

***

## Рекомендации по безопасности

1. **Используйте переменные окружения** для хранения паролей
2. **Всегда используйте SSL/TLS** подключение (через домен)
3. **Настройте Firewall** для ограничения доступа по IP
4. **Регулярно создавайте резервные копии** через панель управления
5. **Не храните пароли в коде** - используйте .env файлы

Вся необходимая информация для подключения вашего Telegram бота к базе данных PostgreSQL на Timeweb собрана и готова к использованию!

<div align="center">⁂</div>

[^1]: https://timeweb.cloud/my/database/4105635

[^2]: https://timeweb.cloud/docs/dbaas/postgresql

[^3]: https://timeweb.cloud/docs/dbaas/dbaas-create

