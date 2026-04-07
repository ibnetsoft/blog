import sqlite3
import re

db_path = 'blog_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, template_html FROM category_templates")
rows = cursor.fetchall()

def restore_padding(html):
    # 1. .container 의 강제 padding: 0 을 적절한 여백(약 5%)으로 변경
    # 이전: padding: 0 !important; -> 이후: padding: 0 5% !important;
    html = re.sub(r'padding\s*:\s*0\s*!?;', 'padding: 0 5% !important;', html, flags=re.IGNORECASE)
    
    # 2. 혹시 .container 에 padding 정의가 없다면 추가
    if '.container' in html and 'padding' not in re.search(r'\.container\s*\{([^}]+)\}', html).group(1):
        html = re.sub(r'(\.container\s*\{)', r'\1 padding: 0 5% !important; ', html, flags=re.IGNORECASE)

    # 3. .card, .note, .expert-box 등 주요 박스 내부 여백 보장 (최소 20px)
    box_classes = ['.card', '.note', '.expert-box', '.content-card', '.hero-text']
    for cls in box_classes:
        if cls in html:
            # 기존 패딩이 너무 작거나 없을 경우 25px로 강제
            html = re.sub(rf'({re.escape(cls)}\s*\{{[^}}]*padding\s*:\s*)([0-5]px|0|10px)', rf'\1 25px', html, flags=re.IGNORECASE)
            # 패딩 정의가 아예 없는 경우 주입
            if 'padding' not in re.search(rf'{re.escape(cls)}\s*\{{([^}}]+)\}}', html).group(1):
                html = re.sub(rf'({re.escape(cls)}\s*\{{)', r'\1 padding: 25px !important; ', html, flags=re.IGNORECASE)

    return html

updated_count = 0
for t_id, html in rows:
    fixed = restore_padding(html)
    if fixed != html:
        cursor.execute("UPDATE category_templates SET template_html = ? WHERE id = ?", (fixed, t_id))
        updated_count += 1

conn.commit()
conn.close()
print(f"Restored left/right padding for {updated_count} templates.")
