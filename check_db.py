import sqlite3
import os

DB_PATH = r"d:\BLOG\blog_app\blog_app.db"

def check_accounts():
    if not os.path.exists(DB_PATH):
        print(f"DB file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("--- Blogger Accounts ---")
    cursor.execute("SELECT id, name, blog_id, lang, refresh_token FROM blogger_accounts")
    rows = cursor.fetchall()
    for row in rows:
        has_token = "Yes" if row['refresh_token'] else "No"
        print(f"ID: {row['id']}, Name: {row['name']}, BlogID: {row['blog_id']}, Lang: {row['lang']}, Connected: {has_token}")
    
    conn.close()

if __name__ == "__main__":
    check_accounts()
