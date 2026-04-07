import sqlite3
import re

db_path = 'blog_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, template_html FROM category_templates")
rows = cursor.fetchall()

def fix_narrow_content(html):
    # 1. Expand standard container max-widths
    # Many templates use 800px or 1000px. Let's make it 1200px for a wide layout.
    html = re.sub(r'max-width\s*:\s*[6789][0-9]{2}px\s*;', 'max-width: 1200px;', html)
    
    # 2. Fix Grid Layouts
    # If the template uses `grid-template-columns: 1fr 300px;` or `2fr 1fr` or similar, 
    # it forces the text into a narrow channel. We should remove the side column or collapse it to 1fr.
    html = re.sub(r'grid-template-columns\s*:\s*([^;]+);', 
                  lambda m: m.group(0) if 'minmax' in m.group(1) or 'repeat' in m.group(1) else 'grid-template-columns: 1fr;', 
                  html)
                  
    # Wait, some grids are for features (like repeat(auto-fit, minmax(...))). We should ONLY override if it's like `2fr 1fr` or `1fr 300px` or `7fr 3fr`.
    # Let's specifically target explicit multi-columns without repeat.
    # Like grid-template-columns: 1fr 300px; or grid-template-columns: 7fr 3fr;
    # But a safer approach is to specifically target the wrapper that holds the content and the sidebar.
    html = re.sub(r'grid-template-columns\s*:\s*(?:\d+fr|\d+px|%)\s+(?:\d+fr|\d+px|%)\s*;', 'grid-template-columns: 1fr;', html)
    
    # 3. Increase padding/content area. Remove strict width limits on .content or .post-body
    html = re.sub(r'\.post-content\s*\{\s*max-width\s*:\s*\d+px', '.post-content { max-width: 100%', html)
    html = re.sub(r'width\s*:\s*[4567][0-9]{2}px\s*;', 'width: 100%;', html)
    
    # 4. In case the text wrapper has large margins:
    html = re.sub(r'margin(?:-left|-right)?\s*:\s*(?:20|30)%', 'margin: 0', html)
    
    return html

for t_id, html in rows:
    fixed = fix_narrow_content(html)
    cursor.execute("UPDATE category_templates SET template_html = ? WHERE id = ?", (fixed, t_id))

conn.commit()
conn.close()
print("Fixed narrow grid layouts in DB.")
