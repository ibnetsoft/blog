import sqlite3
import re

db_path = 'blog_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, template_html FROM category_templates")
rows = cursor.fetchall()

def fix_css(html):
    # 1. Fix overlapping text caused by HTML entities inside CSS `content` properties
    # CSS does not parse HTML entities like &#8594;. It prints them literally, causing a 7-character string
    # to overlap with the text next to it because absolute positioning padding only accounts for 1 character.
    html = re.sub(r'content\s*:\s*["\']?&#8594;["\']?\s*;', 'content: "→";', html)
    html = re.sub(r'content\s*:\s*["\']?&#10003;["\']?\s*;', 'content: "✓";', html)
    html = re.sub(r'content\s*:\s*["\']?&#10007;["\']?\s*;', 'content: "✗";', html)
    
    # 2. Check for light backgrounds to dynamically color the highlighted text
    is_light = False
    
    # Check body or common container background colors
    # We look for #fff, #ffffff, white, #f9f9f9, #f3f4f6, etc.
    if re.search(r'background(?:-color)?\s*:\s*(?:#fff|#ffffff|white|#f8f9fa|#f3f4f6|#f0f2f5)\b', html, re.IGNORECASE):
        # Additional check - if it's explicitly a dark theme using #000 or #111 on the body, then it's NOT light.
        # Sometimes templates have both (like a dark footer on a light body).
        is_light = True
        if re.search(r'body\s*\{[^}]*background(?:-color)?\s*:\s*(?:#000|#111|#1a1a1a|#121212)', html, re.IGNORECASE):
            is_light = False
            
    # Apply colors: Purple for light, Yellow for dark.
    if is_light:
        html = re.sub(r'#FFD700', '#8A2BE2', html, flags=re.IGNORECASE)
        # Check if the template still has any gradients and remove them.
        html = re.sub(r'color\s*:\s*transparent\s*;', 'color: #8A2BE2;', html)
        html = re.sub(r'-webkit-text-fill-color\s*:\s*transparent\s*;', 'color: #8A2BE2;', html)
    else:
        # Re-enforce Yellow for dark themes
        html = re.sub(r'#8A2BE2', '#FFD700', html, flags=re.IGNORECASE)
        html = re.sub(r'color\s*:\s*transparent\s*;', 'color: #FFD700;', html)
        html = re.sub(r'-webkit-text-fill-color\s*:\s*transparent\s*;', 'color: #FFD700;', html)

    # Clean up background-clips that might have been left over if gradient was removed
    html = re.sub(r'-webkit-background-clip\s*:\s*text\s*;', '', html)
    html = re.sub(r'background-clip\s*:\s*text\s*;', '', html)
    
    return html

for t_id, html in rows:
    fixed_html = fix_css(html)
    cursor.execute("UPDATE category_templates SET template_html = ? WHERE id = ?", (fixed_html, t_id))

conn.commit()
conn.close()
print("Executed color matching and overlap fixes.")
