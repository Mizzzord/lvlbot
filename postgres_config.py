import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "d165469ae0aa83744a530bc9.twc1.net")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "default_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "gen_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_SSL_MODE = os.getenv("POSTGRES_SSL_MODE", "verify-full")
POSTGRES_SSL_ROOT_CERT = os.getenv("POSTGRES_SSL_ROOT_CERT", "ca.crt")

def get_postgres_connection():
    """Создание подключения к PostgreSQL"""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DATABASE,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        sslmode=POSTGRES_SSL_MODE,
        sslrootcert=POSTGRES_SSL_ROOT_CERT
    )

def get_postgres_connection_string():
    """Получение строки подключения для asyncpg"""
    return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DATABASE}?sslmode={POSTGRES_SSL_MODE}&sslrootcert={POSTGRES_SSL_ROOT_CERT}"

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

    # Проверка существования файла сертификата
    cert_path = POSTGRES_SSL_ROOT_CERT
    if not os.path.exists(cert_path):
        raise FileNotFoundError(f"Файл сертификата не найден: {cert_path}")

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
