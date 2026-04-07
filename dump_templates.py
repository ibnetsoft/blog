import sqlite3
import json
import os

db_path = 'blog_app.db'
if not os.path.exists(db_path):
    print("DB does not exist.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT category_name, template_html FROM category_templates')
    rows = cursor.fetchall()
    templates = {row[0]: row[1] for row in rows}
    with open('templates_dump.json', 'w', encoding='utf-8') as f:
        json.dump(templates, f, indent=4, ensure_ascii=False)
    print(f"Dumped {len(templates)} templates.")
