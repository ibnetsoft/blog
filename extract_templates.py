import sqlite3

def extract_templates():
    conn = sqlite3.connect('blog_app.db')
    cursor = conn.cursor()
    
    # Get Beauty template
    cursor.execute("SELECT content FROM category_templates WHERE name='Beauty'")
    beauty = cursor.fetchone()
    if beauty:
        with open('beauty_template.html', 'w', encoding='utf-8') as f:
            f.write(beauty[0])
            
    # Get General template
    cursor.execute("SELECT content FROM category_templates WHERE name='General'")
    general = cursor.fetchone()
    if general:
        with open('general_template.html', 'w', encoding='utf-8') as f:
            f.write(general[0])
            
    conn.close()
    print("Templates extracted to beauty_template.html and general_template.html")

if __name__ == "__main__":
    extract_templates()
