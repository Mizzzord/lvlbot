import sqlite3
import sys

def check_database():
    try:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()

        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables: {tables}")

        # Проверяем таблицу subscriptions
        if 'subscriptions' in tables:
            cursor.execute("PRAGMA table_info(subscriptions);")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"Subscriptions columns: {columns}")

            # Проверяем последние записи в таблице subscriptions
            cursor.execute("SELECT COUNT(*) FROM subscriptions;")
            count = cursor.fetchone()[0]
            print(f"Total subscriptions: {count}")

            if count > 0:
                cursor.execute("SELECT * FROM subscriptions ORDER BY id DESC LIMIT 5;")
                recent_subs = cursor.fetchall()
                print("Recent subscriptions:")
                for sub in recent_subs:
                    print(f"  ID: {sub[0]}, User: {sub[1]}, Level: {sub[6] if len(sub) > 6 else 'N/A'}, Status: {sub[7] if len(sub) > 7 else 'N/A'}")
        else:
            print("Таблица subscriptions не найдена!")

        # Проверяем таблицу users
        if 'users' in tables:
            cursor.execute("PRAGMA table_info(users);")
            user_columns = [row[1] for row in cursor.fetchall()]
            print(f"Users columns: {user_columns}")

            # Проверяем наличие subscription_active колонки
            if 'subscription_active' in user_columns:
                cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_active = 1;")
                active_count = cursor.fetchone()[0]
                print(f"Active subscriptions in users table: {active_count}")
            else:
                print("Колонка subscription_active не найдена в таблице users!")

        conn.close()
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    check_database()
