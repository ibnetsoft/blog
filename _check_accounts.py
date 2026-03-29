import sqlite3, os, json

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blog_app.db")


print(f"DB path: {db_path}")
print(f"Exists: {os.path.exists(db_path)}")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# List all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables: {tables}")

# Check blogger_accounts
if "blogger_accounts" in tables:
    cur.execute("SELECT id, name, lang, blog_id, CASE WHEN refresh_token IS NOT NULL AND refresh_token != '' THEN 1 ELSE 0 END as connected FROM blogger_accounts")
    rows = cur.fetchall()
    for r in rows:
        print(f"  ID={r['id']}, name={r['name']}, lang={r['lang']}, blog_id={r['blog_id']}, connected={r['connected']}")
else:
    print("No blogger_accounts table found")

conn.close()
