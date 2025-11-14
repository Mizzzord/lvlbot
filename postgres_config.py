import os
import psycopg2
import psycopg2.extras
import logging
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# PostgreSQL Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "ce577c3306225bd06a426f70.twc1.net")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")  # Порт по умолчанию для PostgreSQL
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "Go_prime")
POSTGRES_USER = os.getenv("POSTGRES_USER", "Go_prime_main")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_SSL_MODE = os.getenv("POSTGRES_SSL_MODE", "verify-full")
# Используем значение из env или путь по умолчанию
POSTGRES_SSL_ROOT_CERT = os.getenv("POSTGRES_SSL_ROOT_CERT", "~/.cloud-certs/root.crt")

# Преобразуем порт в int, если он указан
try:
    POSTGRES_PORT = int(POSTGRES_PORT) if POSTGRES_PORT else 5432
except ValueError:
    POSTGRES_PORT = 5432
    logger.warning(f"Неверный формат порта PostgreSQL: {os.getenv('POSTGRES_PORT')}. Используется порт по умолчанию 5432")

def get_postgres_connection():
    """Создание подключения к PostgreSQL"""
    conn_params = {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "database": POSTGRES_DATABASE,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "sslmode": POSTGRES_SSL_MODE,
    }
    
    # Добавляем sslrootcert только если путь указан и файл существует
    if POSTGRES_SSL_ROOT_CERT and POSTGRES_SSL_ROOT_CERT.strip():
        expanded_cert_path = os.path.expanduser(POSTGRES_SSL_ROOT_CERT)
        if os.path.exists(expanded_cert_path):
            conn_params["sslrootcert"] = expanded_cert_path
    
    return psycopg2.connect(**conn_params)

def get_postgres_connection_string():
    """Получение строки подключения для asyncpg"""
    # URL-кодируем пароль и другие параметры для безопасной передачи в URL
    encoded_user = quote_plus(POSTGRES_USER)
    encoded_password = quote_plus(POSTGRES_PASSWORD)
    encoded_host = quote_plus(POSTGRES_HOST)
    encoded_database = quote_plus(POSTGRES_DATABASE)
    
    # Формируем базовую строку подключения с портом
    # ВАЖНО: asyncpg не поддерживает sslmode в URL строке так же как psycopg2
    # Для asyncpg нужно использовать параметр ssl в словаре параметров
    # Поэтому в строке подключения мы не добавляем sslmode
    conn_string = f"postgresql://{encoded_user}:{encoded_password}@{encoded_host}:{POSTGRES_PORT}/{encoded_database}"
    
    # Для asyncpg лучше не добавлять ssl параметры в URL, они обрабатываются через параметры
    # Но если нужно, можно добавить только для простых случаев
    # Для Timeweb обычно используется sslmode=disable или sslmode=require
    
    return conn_string

def get_postgres_connection_params():
    """Получение параметров подключения для asyncpg (основной способ)"""
    """Возвращает словарь параметров для asyncpg.connect()"""
    import ssl
    
    # Проверяем что пароль не пустой
    if not POSTGRES_PASSWORD:
        logger.error("❌ POSTGRES_PASSWORD не установлен или пустой!")
        raise ValueError("POSTGRES_PASSWORD не установлен в переменных окружения. Проверьте .env файл.")
    
    params = {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "database": POSTGRES_DATABASE,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
    }
    
    # Логируем параметры подключения (без пароля) для отладки
    logger.info(f"Подключение к PostgreSQL: host={POSTGRES_HOST}, port={POSTGRES_PORT}, database={POSTGRES_DATABASE}, user={POSTGRES_USER}, ssl_mode={POSTGRES_SSL_MODE}")
    logger.debug(f"Длина пароля: {len(POSTGRES_PASSWORD)} символов")
    
    # Добавляем SSL параметры для asyncpg
    # asyncpg требует объект SSLContext или специальные значения
    # Для Timeweb обычно используется sslmode=disable или sslmode=require
    if POSTGRES_SSL_MODE:
        ssl_mode_lower = POSTGRES_SSL_MODE.lower()
        
        if ssl_mode_lower == "disable":
            # Отключаем SSL
            params["ssl"] = False
        elif ssl_mode_lower == "require":
            # Требуем SSL без проверки сертификата
            params["ssl"] = "require"
        elif ssl_mode_lower == "prefer":
            # Предпочитаем SSL, но не требуем
            params["ssl"] = "prefer"
        elif ssl_mode_lower == "allow":
            # Разрешаем SSL
            params["ssl"] = "allow"
        elif ssl_mode_lower in ("verify-ca", "verify-full"):
            # Требуем SSL с проверкой сертификата
            ssl_context = ssl.create_default_context()
            if POSTGRES_SSL_ROOT_CERT and POSTGRES_SSL_ROOT_CERT.strip():
                expanded_cert_path = os.path.expanduser(POSTGRES_SSL_ROOT_CERT)
                if os.path.exists(expanded_cert_path):
                    ssl_context.load_verify_locations(expanded_cert_path)
                else:
                    # Если файл сертификата не найден, используем require вместо verify
                    logger.warning(f"Файл сертификата не найден: {expanded_cert_path}. Используется режим 'require'")
                    params["ssl"] = "require"
                    return params
            params["ssl"] = ssl_context
        else:
            # Неизвестный режим SSL - используем require по умолчанию
            logger.warning(f"Неизвестный режим SSL: {POSTGRES_SSL_MODE}. Используется режим 'require'")
            params["ssl"] = "require"
    
    return params

# Проверка конфигурации
def validate_postgres_config():
    """Проверка наличия всех необходимых переменных окружения"""
    required_vars = ["POSTGRES_HOST", "POSTGRES_DATABASE", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")

    # Проверка существования файла сертификата (только если SSL режим требует сертификат и путь указан)
    if POSTGRES_SSL_MODE in ("verify-full", "verify-ca"):
        cert_path = POSTGRES_SSL_ROOT_CERT
        if cert_path and cert_path.strip():  # Проверяем только если путь указан и не пустой
            expanded_cert_path = os.path.expanduser(cert_path)
            if not os.path.exists(expanded_cert_path):
                raise FileNotFoundError(f"Файл сертификата не найден: {expanded_cert_path}")

    return True

if __name__ == "__main__":
    # Тест подключения
    try:
        validate_postgres_config()
        print("✅ Конфигурация PostgreSQL валидна")

        conn = get_postgres_connection()
        print("✅ Подключение к PostgreSQL успешно")

        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Версия PostgreSQL: {version[0]}")

        cursor.close()
        conn.close()
        print("✅ Подключение закрыто")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
