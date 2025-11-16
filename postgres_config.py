import os
import psycopg2
import psycopg2.extras
import logging
import urllib.request
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# PostgreSQL Configuration согласно документации Timeweb
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "ce577c3306225bd06a426f70.twc1.net")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")  # Порт по умолчанию для PostgreSQL
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "Go_prime")
POSTGRES_USER = os.getenv("POSTGRES_USER", "Go_prime_main")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_SSL_MODE = os.getenv("POSTGRES_SSL_MODE", "verify-full")
# Используем значение из env или путь по умолчанию согласно документации Timeweb
POSTGRES_SSL_ROOT_CERT = os.getenv("POSTGRES_SSL_ROOT_CERT", "~/.cloud-certs/root.crt")
# URL для скачивания сертификата Timeweb
TIMEWEB_CERT_URL = "https://st.timeweb.com/cloud-static/ca.crt"

# Преобразуем порт в int, если он указан
try:
    POSTGRES_PORT = int(POSTGRES_PORT) if POSTGRES_PORT else 5432
except ValueError:
    POSTGRES_PORT = 5432
    logger.warning(f"Неверный формат порта PostgreSQL: {os.getenv('POSTGRES_PORT')}. Используется порт по умолчанию 5432")

def ensure_ssl_certificate():
    """
    Убеждается что SSL сертификат Timeweb установлен.
    Если сертификат отсутствует, скачивает его автоматически.
    Согласно документации Timeweb: https://st.timeweb.com/cloud-static/ca.crt
    """
    expanded_cert_path = os.path.expanduser(POSTGRES_SSL_ROOT_CERT)
    cert_dir = os.path.dirname(expanded_cert_path)
    
    # Создаем директорию если её нет
    if not os.path.exists(cert_dir):
        try:
            os.makedirs(cert_dir, mode=0o700)
            logger.info(f"Создана директория для SSL сертификатов: {cert_dir}")
        except OSError as e:
            logger.error(f"Не удалось создать директорию {cert_dir}: {e}")
            return False
    
    # Проверяем существует ли сертификат
    if os.path.exists(expanded_cert_path):
        logger.debug(f"SSL сертификат найден: {expanded_cert_path}")
        return True
    
    # Скачиваем сертификат если его нет
    try:
        logger.info(f"Скачивание SSL сертификата Timeweb из {TIMEWEB_CERT_URL}...")
        urllib.request.urlretrieve(TIMEWEB_CERT_URL, expanded_cert_path)
        
        # Устанавливаем правильные права доступа (только для владельца)
        os.chmod(expanded_cert_path, 0o600)
        
        logger.info(f"✅ SSL сертификат успешно установлен: {expanded_cert_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Не удалось скачать SSL сертификат: {e}")
        logger.error(f"Попробуйте скачать вручную:")
        logger.error(f"  mkdir -p {cert_dir}")
        logger.error(f"  curl -o {expanded_cert_path} {TIMEWEB_CERT_URL}")
        logger.error(f"  chmod 0600 {expanded_cert_path}")
        return False

def get_postgres_connection():
    """
    Создание подключения к PostgreSQL через psycopg2.
    Согласно документации Timeweb использует SSL с сертификатом.
    """
    conn_params = {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "database": POSTGRES_DATABASE,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
    }
    
    # Обрабатываем SSL только если он не отключен
    ssl_mode_lower = POSTGRES_SSL_MODE.lower() if POSTGRES_SSL_MODE else "disable"
    
    if ssl_mode_lower != "disable":
        # Убеждаемся что сертификат установлен (для verify-full режима)
        if ssl_mode_lower in ("verify-full", "verify-ca"):
            ensure_ssl_certificate()
        
        conn_params["sslmode"] = POSTGRES_SSL_MODE
    
    # Добавляем sslrootcert только если путь указан и файл существует
    if POSTGRES_SSL_ROOT_CERT and POSTGRES_SSL_ROOT_CERT.strip():
        expanded_cert_path = os.path.expanduser(POSTGRES_SSL_ROOT_CERT)
        if os.path.exists(expanded_cert_path):
            conn_params["sslrootcert"] = expanded_cert_path
            logger.debug(f"Используется SSL сертификат: {expanded_cert_path}")
        elif ssl_mode_lower in ("verify-full", "verify-ca"):
            logger.warning(f"⚠️ SSL сертификат не найден: {expanded_cert_path}")
            logger.warning("Подключение может не работать. Попробуйте установить сертификат вручную.")
    else:
        # SSL отключен - не добавляем параметры SSL вообще
        logger.debug("SSL отключен, пропускаем проверку сертификата")
    
    return psycopg2.connect(**conn_params)

def get_postgres_connection_string():
    """
    Получение строки подключения для asyncpg.
    ВАЖНО: asyncpg не поддерживает sslmode в URL строке так же как psycopg2.
    Для asyncpg нужно использовать параметр ssl в словаре параметров через get_postgres_connection_params().
    Эта функция используется только для совместимости, рекомендуется использовать get_postgres_connection_params().
    """
    # URL-кодируем пароль и другие параметры для безопасной передачи в URL
    encoded_user = quote_plus(POSTGRES_USER)
    encoded_password = quote_plus(POSTGRES_PASSWORD)
    encoded_host = quote_plus(POSTGRES_HOST)
    encoded_database = quote_plus(POSTGRES_DATABASE)
    
    # Формируем базовую строку подключения с портом
    # SSL параметры обрабатываются через get_postgres_connection_params()
    conn_string = f"postgresql://{encoded_user}:{encoded_password}@{encoded_host}:{POSTGRES_PORT}/{encoded_database}"
    
    return conn_string

def get_postgres_connection_params():
    """
    Получение параметров подключения для asyncpg (основной способ).
    Возвращает словарь параметров для asyncpg.connect().
    Согласно документации Timeweb использует SSL с сертификатом для безопасного подключения.
    """
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
    
    # Обрабатываем SSL только если он не отключен
    ssl_mode_lower = POSTGRES_SSL_MODE.lower() if POSTGRES_SSL_MODE else "disable"
    
    if ssl_mode_lower == "disable":
        # SSL отключен - не добавляем SSL параметры вообще
        logger.debug("SSL отключен, пропускаем проверку сертификата")
        return params
    
    # Убеждаемся что сертификат установлен (для verify-full режима)
    if ssl_mode_lower in ("verify-full", "verify-ca"):
        ensure_ssl_certificate()
    
    # Добавляем SSL параметры для asyncpg
    # asyncpg требует объект SSLContext или специальные значения
    # Согласно документации Timeweb рекомендуется использовать verify-full с сертификатом
    if ssl_mode_lower == "require":
        # Требуем SSL без проверки сертификата
        params["ssl"] = "require"
        logger.info("Используется SSL режим: require (без проверки сертификата)")
    elif ssl_mode_lower == "prefer":
        # Предпочитаем SSL, но не требуем
        params["ssl"] = "prefer"
    elif ssl_mode_lower == "allow":
        # Разрешаем SSL
        params["ssl"] = "allow"
    elif ssl_mode_lower in ("verify-ca", "verify-full"):
        # Требуем SSL с проверкой сертификата (рекомендуется для Timeweb)
        ssl_context = ssl.create_default_context()
        if POSTGRES_SSL_ROOT_CERT and POSTGRES_SSL_ROOT_CERT.strip():
            expanded_cert_path = os.path.expanduser(POSTGRES_SSL_ROOT_CERT)
            if os.path.exists(expanded_cert_path):
                try:
                    ssl_context.load_verify_locations(expanded_cert_path)
                    logger.info(f"✅ SSL сертификат загружен: {expanded_cert_path}")
                    params["ssl"] = ssl_context
                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки SSL сертификата: {e}")
                    logger.warning("Используется режим 'require' вместо 'verify-full'")
                    params["ssl"] = "require"
            else:
                # Если файл сертификата не найден, используем require вместо verify
                logger.warning(f"⚠️ Файл сертификата не найден: {expanded_cert_path}")
                logger.warning("Используется режим 'require' вместо 'verify-full'")
                logger.info("Попробуйте установить сертификат вручную:")
                logger.info(f"  mkdir -p {os.path.dirname(expanded_cert_path)}")
                logger.info(f"  curl -o {expanded_cert_path} {TIMEWEB_CERT_URL}")
                logger.info(f"  chmod 0600 {expanded_cert_path}")
                params["ssl"] = "require"
        else:
            logger.warning("Путь к SSL сертификату не указан. Используется режим 'require'")
            params["ssl"] = "require"
    else:
        # Неизвестный режим SSL - используем require по умолчанию
        logger.warning(f"⚠️ Неизвестный режим SSL: {POSTGRES_SSL_MODE}. Используется режим 'require'")
        params["ssl"] = "require"
    
    return params

# Проверка конфигурации
def validate_postgres_config():
    """
    Проверка наличия всех необходимых переменных окружения.
    Согласно документации Timeweb проверяет наличие обязательных параметров.
    """
    required_vars = ["POSTGRES_HOST", "POSTGRES_DATABASE", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing_vars = []

    for var in required_vars:
        env_value = os.getenv(var)
        # Проверяем что переменная установлена и не пустая
        if not env_value or env_value.strip() == "":
            missing_vars.append(var)

    if missing_vars:
        error_msg = f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}"
        logger.error(f"❌ {error_msg}")
        logger.error("Проверьте файл .env и убедитесь что все переменные установлены.")
        raise ValueError(error_msg)

    # Проверка и установка SSL сертификата (только если SSL режим требует сертификат и не отключен)
    ssl_mode_lower = POSTGRES_SSL_MODE.lower() if POSTGRES_SSL_MODE else "disable"
    if ssl_mode_lower not in ("disable",) and POSTGRES_SSL_MODE in ("verify-full", "verify-ca"):
        cert_path = POSTGRES_SSL_ROOT_CERT
        if cert_path and cert_path.strip():
            expanded_cert_path = os.path.expanduser(cert_path)
            if not os.path.exists(expanded_cert_path):
                logger.warning(f"⚠️ Файл сертификата не найден: {expanded_cert_path}")
                logger.info("Попытка автоматической установки сертификата...")
                if not ensure_ssl_certificate():
                    logger.error("❌ Не удалось установить SSL сертификат автоматически.")
                    logger.error("Установите сертификат вручную:")
                    logger.error(f"  mkdir -p {os.path.dirname(expanded_cert_path)}")
                    logger.error(f"  curl -o {expanded_cert_path} {TIMEWEB_CERT_URL}")
                    logger.error(f"  chmod 0600 {expanded_cert_path}")
                    raise FileNotFoundError(
                        f"Файл сертификата не найден: {expanded_cert_path}. "
                        f"Скачайте его из {TIMEWEB_CERT_URL}"
                    )

    logger.info("✅ Конфигурация PostgreSQL валидна")
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
