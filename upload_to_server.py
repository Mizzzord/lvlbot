#!/usr/bin/env python3
"""
Скрипт для загрузки проекта на SSH сервер через SFTP
"""
import paramiko
import os
import stat
from pathlib import Path

# Настройки подключения
HOST = "83.222.8.216"
PORT = 22
USERNAME = "root"
PASSWORD = "y7mjZ#kXJR6P7,"
REMOTE_DIR = "/root/lvlbot"
LOCAL_DIR = "/Users/staf/Desktop/Mycode/lvlbot"

# Файлы и папки, которые не нужно загружать
EXCLUDE = {
    '.git', '__pycache__', '.venv', '.DS_Store', 
    'bot_database.db', 'player_cards', 'player_photos',
    'task_submissions', 'upload_to_server.py',
    '.env', 'Player Card Design/node_modules'
}

def should_skip(path_parts):
    """Проверяет, нужно ли пропустить файл/папку"""
    for part in path_parts:
        if part in EXCLUDE:
            return True
    return False

def upload_directory(sftp, local_path, remote_path):
    """Рекурсивно загружает директорию на сервер"""
    local_path = Path(local_path)
    
    for item in local_path.iterdir():
        local_item = local_path / item.name
        remote_item = f"{remote_path}/{item.name}"
        
        # Проверяем, нужно ли пропустить
        relative_parts = local_item.relative_to(LOCAL_DIR).parts
        if should_skip(relative_parts):
            print(f"⏭️  Пропуск: {item.name}")
            continue
        
        if local_item.is_dir():
            print(f"📁 Создание директории: {remote_item}")
            try:
                sftp.mkdir(remote_item)
            except IOError:
                pass  # Директория уже существует
            upload_directory(sftp, local_item, remote_item)
        else:
            print(f"📄 Загрузка: {item.name}")
            sftp.put(str(local_item), remote_item)

def main():
    print(f"🔌 Подключение к {HOST}...")
    
    # Создаем SSH клиент
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Подключаемся
        ssh.connect(HOST, PORT, USERNAME, PASSWORD)
        print("✅ Подключено!")
        
        # Открываем SFTP сессию
        sftp = ssh.open_sftp()
        
        # Создаем основную директорию
        print(f"\n📂 Создание директории {REMOTE_DIR}...")
        try:
            sftp.mkdir(REMOTE_DIR)
        except IOError:
            print("  (директория уже существует)")
        
        # Загружаем файлы
        print(f"\n📤 Начинаем загрузку файлов...\n")
        upload_directory(sftp, LOCAL_DIR, REMOTE_DIR)
        
        print("\n✅ Загрузка завершена!")
        
        # Закрываем соединения
        sftp.close()
        ssh.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

