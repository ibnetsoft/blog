import sqlite3
import re

def fix_css(html):
    # 1. We want to convert `.gradient-text` or similar gradient text blocks.
    # Often it looks like this:
    # .gradient-text {
    #     background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%);
    #     -webkit-background-clip: text;
    #     -webkit-text-fill-color: transparent;
    #     color: transparent;
    # }
    
    # We will search for any CSS block containing `-webkit-background-clip: text`
    # and replace `color: transparent` with `color: #FFD700`,
    # remove `-webkit-background-clip` and `background: linear-...`
    
    def replace_block(match):
        block = match.group(0)
        if 'background-clip: text' in block or '-webkit-text-fill-color: transparent' in block or 'color: transparent' in block:
            # Replace background properties inside this block
            block = re.sub(r'background\s*:[^;]+;', '', block)
            block = re.sub(r'-webkit-background-clip\s*:[^;]+;', '', block)
            block = re.sub(r'background-clip\s*:[^;]+;', '', block)
            block = re.sub(r'-webkit-text-fill-color\s*:[^;]+;', 'color: #FFD700;', block)
            block = re.sub(r'color\s*:\s*transparent\s*;', 'color: #FFD700;', block)
            return block
        return block

    # Match CSS rules
    new_html = re.sub(r'\{[^\}]+\}', replace_block, html)
    
    # 2. Fix the line breaking issue!
    # The screenshot shows text literally broken character by character.
    # This usually happens because `word-break: break-all;` is overused on `.container`, `.content-card`, etc.
    # Let's replace word-break: break-all; with word-wrap: break-word; overflow-wrap: break-word; word-break: keep-all; 
    new_html = re.sub(r'word-break\s*:\s*break-all\s*;', 'word-break: keep-all; overflow-wrap: break-word;', new_html)
    
    # Let's also ensure `.list` or `.feature-item` doesn't have an extremely narrow width (like flex: 0 0 50px).
    # A common issue is a flex column or grid column that uses `min-width: 0` or similar aggressively.
    # To be safe, just fix word-break and see.
    return new_html

conn = sqlite3.connect('blog_app.db')
cursor = conn.cursor()
cursor.execute('SELECT id, template_html FROM category_templates')
rows = cursor.fetchall()
for row in rows:
    t_id, html = row
    fixed_html = fix_css(html)
    cursor.execute('UPDATE category_templates SET template_html = ? WHERE id = ?', (fixed_html, t_id))
    
conn.commit()
conn.close()
print("All templates updated.")
