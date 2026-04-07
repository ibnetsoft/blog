import sqlite3
import json

db_path = 'blog_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, category_name, template_html FROM category_templates")
rows = cursor.fetchall()
templates = {row[1]: row[2] for row in rows}

with open('templates_inspect.json', 'w', encoding='utf-8') as f:
    json.dump(templates, f, indent=4, ensure_ascii=False)
