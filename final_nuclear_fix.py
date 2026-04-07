import sqlite3
import re

db_path = 'blog_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, category_name, template_html FROM category_templates")
rows = cursor.fetchall()

def nuclear_fix_template(html, cat):
    # 1. 텍스트 그라데이션 및 투명 속성 완전 제거
    html = re.sub(r'color\s*:\s*transparent\s*!?;', '', html, flags=re.IGNORECASE)
    html = re.sub(r'-webkit-text-fill-color\s*:\s*transparent\s*!?;', '', html, flags=re.IGNORECASE)
    html = re.sub(r'background-clip\s*:\s*text\s*!?;', '', html, flags=re.IGNORECASE)
    html = re.sub(r'-webkit-background-clip\s*:\s*text\s*!?;', '', html, flags=re.IGNORECASE)

    # 2. 배경색에 따른 텍스트 색상 강제 지정
    # 배경색 추출 (body { background: ... } 또는 background-color)
    bg_match = re.search(r'background(?:-color)?\s*:\s*([^;}]+)', html, re.IGNORECASE)
    bg_val = bg_match.group(1).strip().lower() if bg_match else ""
    
    is_dark = True # 기본값
    if '#fff' in bg_val or 'white' in bg_val or '#f' in bg_val:
        # 밝은 배경 조건 (대략적으로 #f... 는 밝은 색)
        if not any(c in bg_val for c in ['#0', '#1', '#2']):
            is_dark = False

    if is_dark:
        # 다크 테마: 본문은 흰색(#ffffff), 강조는 노랑(#FFD700)
        main_color = "#ffffff"
        highlight_color = "#FFD700"
        # 잘못 설정된 어두운 색상들(#1e..., #33..., #47...)을 흰색으로 교체
        html = re.sub(r'color\s*:\s*(?:#1e|#33|#47|#0f|#1b)[^;}]+;', f'color: {main_color};', html, flags=re.IGNORECASE)
    else:
        # 라이트 테마: 본문은 짙은 남색(#1e293b), 강조는 보라(#8A2BE2)
        main_color = "#1e293b"
        highlight_color = "#8A2BE2"

    # 모든 h1, h2, h3, p에 대해 색상 보정 (이미 정의된 색상이 가독성 나쁠 경우 대비)
    tags = ['h1', 'h2', 'h3', 'p', 'li', 'span']
    for tag in tags:
        # 스타일 블록 내부의 태그 정의를 찾아 색상 덮어쓰기
        html = re.sub(rf'({tag}\s*\{{[^}}]*color\s*:\s*)([^;}}]+)', rf'\1{main_color}', html, flags=re.IGNORECASE)
    
    # 강조색(강한 색상) 일괄 적용
    html = re.sub(r'#FFD700|#8A2BE2|#facc15', highlight_color, html, flags=re.IGNORECASE)

    # 3. 레이아웃(폭) 강제 확장
    # grid-template-columns 를 1fr로 강제 고정 (멀티라인 고려)
    html = re.sub(r'grid-template-columns\s*:[^;}]+;', 'grid-template-columns: 1fr !important;', html, flags=re.IGNORECASE)
    # max-width 1200px 확대
    html = re.sub(r'max-width\s*:\s*[6789]\d{2}px', 'max-width: 1200px', html, flags=re.IGNORECASE)
    # 좁은 width (60% 등)를 100%로 확장
    html = re.sub(r'width\s*:\s*(?:60|70|80)%;', 'width: 100%;', html, flags=re.IGNORECASE)

    return html

updated_count = 0
for t_id, cat, html in rows:
    fixed = nuclear_fix_template(html, cat)
    cursor.execute("UPDATE category_templates SET template_html = ? WHERE id = ?", (fixed, t_id))
    updated_count += 1

conn.commit()
conn.close()
print(f"Totally fixed {updated_count} templates with high-contrast colors and wide layouts.")
