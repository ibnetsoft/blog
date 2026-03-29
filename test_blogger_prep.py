import re

def prepare_html_for_blogger_logic(content, summary=None):
    # 실제 blog_service.py의 로직을 간략화하여 구조만 검증
    style_blocks = ["body { color: red; }"]
    body_content = "Hello World"
    
    result_parts = []
    # 5. CSS 스코핑 (생략)
    scoped_css = ".bp-wrap { color: red; }"
    
    # 7. 조립
    if scoped_css.strip():
        result_parts.append(f"<style>\n{scoped_css}</style>")
    
    result_parts.append('<div class="bp-wrap">')
    if summary:
        result_parts.append(f'<div style="display:none;">{summary}</div>')
    result_parts.append(f'{body_content.strip()}\n</div>')
    
    return "\n".join(result_parts)

content = "..."
summary = "This is a summary"
result = prepare_html_for_blogger_logic(content, summary)
print("--- GENERATED HTML STRUCTURE ---")
print(result)

# 검증 포인트
styles_idx = result.find("<style>")
none_div_idx = result.find('display:none')
bp_wrap_idx = result.find('class="bp-wrap"')

print(f"\nPositions: Style={styles_idx}, bp-wrap={bp_wrap_idx}, none-div={none_div_idx}")

if styles_idx < bp_wrap_idx < none_div_idx:
    print("\nSUCCESS: Style is at the top, none-div is inside bp-wrap.")
else:
    print("\nFAILURE: Wrong HTML structure.")
