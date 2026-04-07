import sqlite3
import re

db_path = 'blog_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, template_html FROM category_templates")
rows = cursor.fetchall()

def restore_padding_v2(html):
    # 1. .container 의 강제 padding: 0 !important; 등을 5%로 복구
    # 기존에 제가 실수로 넣었던 모든 종류의 0 패딩을 잡아냅니다.
    html = re.sub(r'padding\s*:\s*0[^;]*!important\s*;', 'padding: 0 5% !important;', html, flags=re.IGNORECASE)
    html = re.sub(r'padding\s*:\s*0\s*;', 'padding: 0 5% !important;', html, flags=re.IGNORECASE)
    
    # 2. 컴포넌트 내부 여백(Card, Note 등)
    # 텍스트가 박스 테두리에 붙지 않게 최소 25px 보장
    box_elements = ['.card', '.note', '.expert-box', '.content-card', '.hero-text']
    for elem in box_elements:
        if elem in html:
            # 해당 클래스의 스타일 블록 내부에서 padding: 0 이나 아주 작은 값을 찾아 교체
            html = re.sub(rf'({re.escape(elem)}\s*\{{[^}}]*padding\s*:\s*)(?:0|[0-5]px)[^;}}]*', rf'\1 25px !important', html, flags=re.IGNORECASE)

    return html

updated_count = 0
for t_id, html in rows:
    fixed = restore_padding_v2(html)
    if fixed != html:
        cursor.execute("UPDATE category_templates SET template_html = ? WHERE id = ?", (fixed, t_id))
        updated_count += 1

conn.commit()
conn.close()
print(f"Successfully restored padding in {updated_count} templates.")
