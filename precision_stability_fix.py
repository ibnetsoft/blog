import sqlite3
import re

db_path = 'blog_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, category_name, template_html FROM category_templates")
rows = cursor.fetchall()

# 카테고리별 테마 분류
DARK_CATEGORIES = ['Automobile', 'Finance', 'FX외환', 'K-pop', 'Sports', '웹서비스']
LIGHT_CATEGORIES = ['Beauty', 'Medical', 'Shopping', 'Trip', 'General']

def stability_fix(html, cat):
    # 1. 레이아웃(폭) 정상화
    # 100vw -> 100% 로 변경
    html = re.sub(r'width\s*:\s*100vw\s*!?;', 'width: 100% !important;', html, flags=re.IGNORECASE)
    html = re.sub(r'margin-left\s*:\s*calc\([^)]+\)\s*!?;', 'margin-left: 0 !important;', html, flags=re.IGNORECASE)
    
    # max-width 및 box-sizing 보강
    if '.container' in html:
        html = re.sub(r'\.container\s*\{', '.container { box-sizing: border-box; max-width: 1200px !important; ', html, flags=re.IGNORECASE)
    
    # 2. 테마별 색상 정밀 적용
    is_dark = cat in DARK_CATEGORIES
    
    if is_dark:
        main_color = "#ffffff"
        secondary_color = "#e2e8f0"
        highlight = "#FFD700" # 노랑
        bg_card = "#1e293b"
    else:
        main_color = "#1e293b"
        secondary_color = "#475569"
        highlight = "#8A2BE2" # 보라
        bg_card = "#f1f5f9"

    # 기본 텍스트 색상 강제 (Nuclear)
    html = re.sub(r'body\s*\{[^}]*color\s*:\s*([^;]+);', f'body {{ color: {main_color};', html, flags=re.IGNORECASE)
    
    # 제목 태그들 색상 보정
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li']:
        # 스타일 블록 내부의 색상 정의 찾기
        html = re.sub(rf'({tag}\s*\{{[^}}]*color\s*:\s*)([^;}}]+)', rf'\1{main_color}', html, flags=re.IGNORECASE)

    # 3. 컴포넌트(Note, Card, Expert) 가시성 보정
    # 밝은 박스나 강조 박스 내부는 배경색에 반전되는 색상을 명시적으로 지정
    if is_dark:
        # 다크 테마의 강조 박스 (.note, .expert-box 등)
        html = re.sub(r'(\.note|\.expert-box|\.card|\.content-card)\s*\{', 
                      rf'\1 {{ background-color: {bg_card} !important; color: {main_color} !important; ', html, flags=re.IGNORECASE)
    else:
        # 라이트 테마의 강조 박스
        html = re.sub(r'(\.note|\.expert-box|\.card|\.content-card)\s*\{', 
                      rf'\1 {{ background-color: {bg_card} !important; color: {main_color} !important; ', html, flags=re.IGNORECASE)

    # 4. 강조 색상(Highlight) 코드 통일
    # 기존에 노랑이나 보라였던 것들을 테마 가이드라인에 맞게 일괄 치환
    html = re.sub(r'#FFD700|#8A2BE2|#facc15', highlight, html, flags=re.IGNORECASE)

    # 5. 불필요한 이미지 플레이스홀더 기본 숨김 처리 (Gemini가 이미지를 안 넣었을 때 대비)
    html = re.sub(r'img\s*\{', 'img { max-width: 100%; height: auto; border-radius: 12px; display: block; margin: 20px auto; ', html, flags=re.IGNORECASE)

    return html

updated = 0
for t_id, cat, html in rows:
    fixed_html = stability_fix(html, cat)
    cursor.execute("UPDATE category_templates SET template_html = ? WHERE id = ?", (fixed_html, t_id))
    updated += 1

conn.commit()
conn.close()
print(f"Successfully stabilized {updated} templates for both Japanese and English blogs.")
