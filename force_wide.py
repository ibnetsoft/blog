import sqlite3
import re

db_path = 'blog_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, category_name, template_html FROM category_templates")
rows = cursor.fetchall()

def force_wide_layout(html, cat_name):
    # 1. Broadly target ANY grid-template-columns that suggests a multi-column sidebar layout.
    # The previous regex missed layouts like `grid-template-columns: minmax(0, 1fr) 250px;` or `300px 1fr`
    
    # Let's find any `grid-template-columns: ... ;` that is NOT `repeat(auto-fit...)` because repeat is for galleries/features.
    # If it's a structural grid for the container, it's usually `1fr 300px` or `2fr 1fr` or `minmax(...) 300px`.
    
    def replacer(match):
        val = match.group(1)
        # Avoid destroying feature grids which use repeat
        if 'repeat' in val or 'auto-fit' in val or 'auto-fill' in val:
            return match.group(0)
        # If there are two or more columns defined (indicated by spaces between values that are not in functions)
        # Actually, simpler: if it has 1fr or minmax and something else, just force it to 1fr.
        return 'grid-template-columns: 1fr;'

    html = re.sub(r'grid-template-columns\s*:\s*([^;]+);', replacer, html)
    
    # 2. Some sidebars are forced using CSS Grid areas or flex: 
    # .main-content { min-width: 0; }
    # .sidebar { width: 300px; }
    # Let's just make any flex container that holds the sidebar wrap.
    # If there is `.sidebar` or `.tags-wrapper` or `.aside`, we can force them to 100% width or display block
    html = re.sub(r'\.sidebar\s*\{[^}]*\}', '.sidebar { width: 100%; display: block; margin-top: 2rem; }', html)
    html = re.sub(r'aside\s*\{[^}]*\}', 'aside { width: 100%; display: block; margin-top: 2rem; }', html)
    html = re.sub(r'\.features-wrapper\s*\{[^}]*\}', '.features-wrapper { width: 100%; display: block; }', html)
    
    # 3. Ensure the max-width of the container is large enough.
    # Replace all max-widths between 600-900 with 1200px
    html = re.sub(r'max-width\s*:\s*[6789]\d{2}px\s*;', 'max-width: 1200px;', html)
    
    # 4. Remove right paddings/margins that were meant to leave space for absolute sidebars
    html = re.sub(r'padding-right\s*:\s*(?:200|250|300|350|400)px\s*;', 'padding-right: 0;', html)
    html = re.sub(r'margin-right\s*:\s*(?:200|250|300|350|400)px\s*;', 'margin-right: 0;', html)

    # 5. Fix alignment of tags (the red tags in the screenshot)
    # The tags are likely in a `.tags` or `.tag-list` class.
    # Let's make sure they display nicely inline and don't float.
    html = re.sub(r'float\s*:\s*(?:left|right)\s*;', 'float: none;', html)

    return html

updated = 0
for t_id, cat_name, html in rows:
    fixed_html = force_wide_layout(html, cat_name)
    if fixed_html != html:
        cursor.execute("UPDATE category_templates SET template_html = ? WHERE id = ?", (fixed_html, t_id))
        updated += 1

conn.commit()
conn.close()
print(f"Force-fixed narrow widths in {updated} templates.")
