import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "ce577c3306225bd06a426f70.twc1.net")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "Go_prime")
POSTGRES_USER = os.getenv("POSTGRES_USER", "Go_prime_main")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_SSL_MODE = os.getenv("POSTGRES_SSL_MODE", "verify-full")
# Используем значение из env или путь по умолчанию
POSTGRES_SSL_ROOT_CERT = os.getenv("POSTGRES_SSL_ROOT_CERT", "~/.cloud-certs/root.crt")

def get_postgres_connection():
    """Создание подключения к PostgreSQL"""
    conn_params = {
        "host": POSTGRES_HOST,
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
    expanded_cert_path = os.path.expanduser(POSTGRES_SSL_ROOT_CERT) if POSTGRES_SSL_ROOT_CERT else ""
    cert_param = f"&sslrootcert={expanded_cert_path}" if expanded_cert_path else ""
    return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DATABASE}?sslmode={POSTGRES_SSL_MODE}{cert_param}"

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
