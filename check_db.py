import sqlite3

def check_logs():
    try:
        conn = sqlite3.connect('blog_app.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("--- LAST 5 JOB LOGS ---")
        cursor.execute("SELECT * FROM job_logs ORDER BY created_at DESC LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            print(dict(row))
            
        print("\n--- BLOGGER ACCOUNTS ---")
        cursor.execute("SELECT * FROM blogger_accounts")
        rows = cursor.fetchall()
        for row in rows:
            print(dict(row))

        print("\n--- LAST 5 PUBLISH SESSIONS ---")
        cursor.execute("SELECT id, title, blog_wp_url, blog_blogger_url, status, updated_at FROM publish_sessions ORDER BY updated_at DESC LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            print(dict(row))
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_logs()
