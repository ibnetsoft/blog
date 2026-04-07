import sqlite3
import re
import json

db_path = 'blog_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, template_html FROM category_templates WHERE category_name IN ('Sports', 'Medical', 'General')")
rows = cursor.fetchall()

def fix_feature_width(html):
    # CSS problem: The feature icon col was probably like .feature-icon { width: 30px; } or flex: 0 0 30px;
    # Or in the markdown conversion it became a table column that has no width constraints.
    # The image shows `Ful l-  Bo dy ...` which happens when `word-wrap: break-word` meets extremely narrow columns.
    
    # 1. Look for narrow widths on anything inside feature or list.
    html = re.sub(r'flex:\s*0\s*0\s*[1-6][0-9]px\s*;', 'flex: 0 0 120px;', html)
    html = re.sub(r'width:\s*[1-6][0-9]px\s*;', 'width: auto; min-width: 60px;', html)
    
    # Let's ensure the left column doesn't get squeezed.
    # We can add a universal safety net for .feature-icon or .list-icon
    html = re.sub(r'\.feature-icon\s*\{', '.feature-icon { min-width: 80px; text-align: left; ', html)
    html = re.sub(r'\.list-icon\s*\{', '.list-icon { min-width: 80px; text-align: left; ', html)
    
    return html

for t_id, html in rows:
    fixed = fix_feature_width(html)
    cursor.execute("UPDATE category_templates SET template_html = ? WHERE id = ?", (fixed, t_id))

conn.commit()
conn.close()
print("Fixed widths applied to DB.")
