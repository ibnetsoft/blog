import database as db
import json

# 공통 레이아웃 프레임워크 (가변적인 부분을 {{content}} 등으로 감쌈)
# 실제 프롬프트에서는 Gemini가 이 구조를 참고하도록 할 것

TEMPLATES = {
    "Automobile": """
    /* Automobile Template: Sleek, High-Tech, Metallic */
    :root {
      --primary: #c0c0c0; /* Silver */
      --secondary: #1a1a1a; /* Dark gray */
      --accent: #ff3d00; /* Racing red */
      --bg: #0d0d0d;
      --text: #ffffff;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }
    .hero { background: linear-gradient(135deg, #1f1f1f 0%, #000000 100%); border-bottom: 4px solid var(--accent); padding: 80px 20px; text-align: center; }
    .content-card { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; overflow: hidden; margin: 20px 0; }
    .specs-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
    .spec-item { border-left: 3px solid var(--accent); padding-left: 15px; }
    h1, h2 { text-transform: uppercase; letter-spacing: 2px; font-weight: 900; }
    """,
    
    "Beauty": """
    /* Beauty Template: Elegant, Soft, Minimalist */
    :root {
      --primary: #fbdae1; /* Soft pink */
      --secondary: #fff5f7; /* pale cream */
      --accent: #d4a373; /* Muted gold */
      --bg: #ffffff;
      --text: #4a4a4a;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Playfair Display', serif; }
    .hero { background: var(--secondary); padding: 100px 20px; text-align: center; }
    .hero h1 { font-style: italic; font-weight: 300; font-size: 3rem; }
    .article-section { max-width: 800px; margin: 0 auto; line-height: 1.8; }
    .tip-box { background: var(--primary); border-radius: 50px; padding: 30px; margin: 40px 0; border: 1px solid rgba(0,0,0,0.05); }
    .ingred-list { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
    .ingred-item { background: white; padding: 10px 20px; border-radius: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
    """,

    "Finance": """
    /* Finance Template: Professional, Trustworthy, Solid */
    :root {
      --primary: #002d62; /* Navy blue */
      --secondary: #f4f7f9; /* light blue gray */
      --accent: #c5a059; /* Classic gold */
      --bg: #ffffff;
      --text: #1a1a1a;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Roboto', sans-serif; }
    .header-bar { border-top: 6px solid var(--primary); padding: 40px 0; background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    .analysis-box { background: var(--secondary); border-radius: 12px; padding: 40px; border: 1px solid #e1e8ed; }
    .stat-row { display: flex; justify-content: space-between; border-bottom: 1px dashed #ced4da; padding: 15px 0; }
    .verdict { border: 2px solid var(--primary); border-radius: 8px; padding: 25px; margin-top: 30px; background: rgba(0,45,98,0.02); }
    h2 { color: var(--primary); border-left: 5px solid var(--accent); padding-left: 15px; }
    """,

    "FX외환": """
    /* FX Template: Digital, Real-time, Analytical */
    :root {
      --primary: #00ffb3; /* Neon green */
      --secondary: #121212; /* Rich black */
      --accent: #00d4ff; /* Cyan */
      --bg: #0a0a0a;
      --text: #e0e0e0;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Exo 2', sans-serif; }
    .trading-panel { background: rgba(255,255,255,0.03); border: 1px solid rgba(0,255,179,0.2); border-radius: 12px; padding: 25px; font-family: monospace; }
    .price-up { color: #00ff62; text-shadow: 0 0 10px rgba(0,255,98,0.5); }
    .price-down { color: #ff3d00; text-shadow: 0 0 10px rgba(255,61,0,0.5); }
    .glass-card { background: rgba(255,255,255,0.05); backdrop-filter: blur(8px); border-radius: 16px; padding: 30px; margin: 20px 0; }
    .chart-placeholder { height: 300px; background: linear-gradient(to right, transparent 95%, rgba(0,212,255,0.1) 95%), linear-gradient(to bottom, transparent 95%, rgba(0,212,255,0.1) 95%); background-size: 40px 40px; border: 1px solid #333; }
    """,

    "K-pop": """
    /* K-pop Template: Vibrant, Dynamic, Pop Culture */
    :root {
      --primary: #ff007a; /* Hot pink */
      --secondary: #7000ff; /* Electric purple */
      --accent: #00f0ff; /* Neon cyan */
      --bg: #000000;
      --text: #ffffff;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; overflow-x: hidden; }
    .magazine-header { position: relative; padding: 120px 20px; overflow: hidden; background: linear-gradient(45deg, var(--primary), var(--secondary)); }
    .magazine-header::after { content: 'STARDOM'; position: absolute; font-size: 15rem; font-weight: 900; opacity: 0.1; top: -20px; left: -20px; pointer-events: none; }
    .idol-card { border: 2px solid var(--accent); border-radius: 0 40px 0 40px; overflow: hidden; background: #111; margin: 30px 0; transition: transform 0.3s; }
    .idol-card:hover { transform: scale(1.02); }
    .lyrics-box { background: rgba(255,255,255,0.05); padding: 30px; border-radius: 20px; font-style: italic; border-right: 5px solid var(--primary); }
    h1 { font-size: 4rem; font-weight: 900; letter-spacing: -2px; line-height: 1; }
    """,

    "Medical": """
    /* Medical Template: Clinical, Clean, Informative */
    :root {
      --primary: #0077b6; /* Health blue */
      --secondary: #eef9ff; /* Soft sky */
      --accent: #00b4d8; /* Light medical blue */
      --bg: #ffffff;
      --text: #2b2d42;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }
    .expert-note { background: var(--secondary); border-left: 8px solid var(--primary); padding: 30px; margin: 30px 0; border-radius: 0 12px 12px 0; }
    .checklist-section { background: white; border: 1px solid #dee2e6; border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
    .symptom-tag { display: inline-block; background: #f8f9fa; border: 1px solid #e9ecef; padding: 8px 16px; border-radius: 6px; margin: 5px; font-weight: 600; font-size: 0.9rem; }
    .caution-box { background: #fff5f5; border: 1px solid #feb2b2; color: #c53030; padding: 20px; border-radius: 8px; font-weight: bold; }
    h2 { color: var(--primary); padding-bottom: 10px; border-bottom: 2px solid var(--secondary); }
    """,

    "Shopping": """
    /* Shopping Template: Commercial, Bold, Conversion-Oriented */
    :root {
      --primary: #ff4d00; /* Sales orange */
      --secondary: #fff8f5; /* Light peach */
      --accent: #2ecc71; /* Success green */
      --bg: #ffffff;
      --text: #111111;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Montserrat', sans-serif; }
    .deal-badge { background: var(--primary); color: white; padding: 10px 20px; border-radius: 4px; font-weight: 900; display: inline-block; transform: rotate(-3deg); }
    .product-showcase { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; background: var(--secondary); border-radius: 24px; padding: 40px; margin: 40px 0; align-items: center; }
    .price-tag { font-size: 2.5rem; font-weight: 900; color: var(--primary); }
    .review-bubble { background: #f1f3f5; border-radius: 20px; padding: 20px; position: relative; margin-bottom: 20px; }
    .buy-button { background: var(--primary); color: white; padding: 18px 40px; border-radius: 12px; font-weight: bold; text-align: center; box-shadow: 0 10px 20px rgba(255,77,0,0.2); }
    """,

    "Sports": """
    /* Sports Template: High-Energy, Bold, Competitive */
    :root {
      --primary: #e63946; /* Adrenaline red */
      --secondary: #1d3557; /* Competition blue */
      --accent: #f1faee; /* Clean white */
      --bg: #f8f9fa;
      --text: #1a1a1a;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Chakra Petch', sans-serif; }
    .scoreview { background: var(--secondary); color: white; padding: 50px 20px; text-align: center; clip-path: polygon(0 0, 100% 10%, 100% 100%, 0 90%); }
    .player-stat-card { background: white; border-bottom: 5px solid var(--primary); padding: 30px; border-radius: 4px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .highlights-list { list-style: none; padding: 0; }
    .highlight-item { background: linear-gradient(90deg, var(--primary) 0%, transparent 5px, #fff 5px); margin: 10px 0; padding: 15px 20px; border: 1px solid #eee; }
    h1 { font-style: italic; text-transform: uppercase; font-weight: 800; font-size: 3.5rem; }
    """,

    "Trip": """
    /* Trip Template: Airy, Natural, Travel Diary */
    :root {
      --primary: #2a9d8f; /* Ocean green */
      --secondary: #e9c46a; /* Sand yellow */
      --accent: #f4a261; /* Sunset orange */
      --bg: #ffffff;
      --text: #264653;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; }
    .itinerary-timeline { border-left: 2px dashed var(--secondary); margin-left: 20px; padding-left: 30px; position: relative; }
    .itinerary-node { position: absolute; left: -10px; width: 20px; hright: 20px; background: var(--primary); border-radius: 50%; }
    .photo-masonry { column-count: 2; column-gap: 20px; }
    .location-badge { background: var(--secondary); color: #fff; padding: 5px 15px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; }
    .travel-quote { font-family: 'Playfair Display', serif; font-size: 1.5rem; color: var(--primary); text-align: center; margin: 50px 0; quotes: "“" "”"; }
    """,

    "웹서비스": """
    /* Web Service Template: Modern SaaS, Clean UI, Interactive */
    :root {
      --primary: #6366f1; /* Indigo */
      --secondary: #f8fafc; /* light slate */
      --accent: #ec4899; /* Pink */
      --bg: #ffffff;
      --text: #0f172a;
    }
    body { background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }
    .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 30px; }
    .feature-card { background: white; border: 1px solid #e2e8f0; border-radius: 20px; padding: 35px; transition: all 0.3s; }
    .feature-card:hover { border-color: var(--primary); transform: translateY(-5px); box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
    .code-block { background: #1e293b; color: #bae6fd; padding: 25px; border-radius: 12px; font-family: monospace; overflow-x: auto; }
    .cta-banner { background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%); color: white; padding: 60px; border-radius: 30px; text-align: center; }
    h2 { font-weight: 800; letter-spacing: -0.02em; }
    """
}


def populate():
    print("🚀 Populating Category Templates...")
    for cat, css in TEMPLATES.items():
        print(f" - Storing template for {cat}...")
        # 더 나은 템플릿 구조를 위해 기본 HTML 래퍼와 CSS를 결합
        full_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Roboto:wght@400;700&family=Montserrat:wght@400;700;900&family=Outfit:wght@300;400;700;900&family=Chakra+Petch:ital,wght@0,400;0,700;1,400&family=Exo+2:wght@400;700&display=swap" rel="stylesheet">
    <style>
        {css}
        
        /* Common Layout Utilities */
        .container {{ width: 100%; max-width: 1100px; margin: 0 auto; padding: 0 20px; }}
        .section-padding {{ padding: 60px 0; }}
        img {{ max-width: 100%; height: auto; border-radius: 12px; margin: 20px 0; }}
        
        /* Animation Classes */
        .reveal {{ animation: fadeInUp 0.8s ease forwards; opacity: 0; }}
        @keyframes fadeInUp {{
            from {{ opacity: 0; transform: translateY(30px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
    </style>
</head>
<body>
    <!-- Gemini: Use the CSS classes defined above to structure the article. 
         Main article should be inside a <div class="container section-padding">. 
         Use Hero section for introduction. -->
    [[CONTENT]]
</body>
</html>
"""
        db.save_category_template(cat, full_template.strip())
    
    # "General" fallback template
    general_css = """
    :root { --primary: #3b82f6; --text: #1f2937; --bg: #ffffff; }
    body { font-family: 'Inter', sans-serif; line-height: 1.6; color: var(--text); }
    .container { max-width: 900px; margin: 0 auto; padding: 40px 20px; }
    h1 { font-size: 2.5rem; font-weight: 800; margin-bottom: 1rem; color: #111827; }
    p { margin-bottom: 1.5rem; }
    """
    db.save_category_template("General", f"<!DOCTYPE html><html><head><style>{general_css}</style></head><body><div class='container'>[[CONTENT]]</div></body></html>")
    
    print("✅ Done!")

if __name__ == "__main__":
    populate()
