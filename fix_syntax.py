import os

with open('services/prompts.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
skip_until_triple_quote = False

for line in lines:
    # Look for the broken sequence
    if '"""' in line and '니다.' in line and not line.strip().startswith('#'):
        # Fix the line by removing the junk after triple quotes
        idx = line.find('"""')
        new_lines.append(line[:idx+3] + '\n')
        continue
    
    # If a line contains JUST '니다.', skip it
    if line.strip() == '니다.':
        continue
        
    new_lines.append(line)

# Second pass: ensure we don't have two GEMINI_GENERATE_BLOG definitions if one is an accidental merge
# Or better: just fix the syntax error first.
# The user's screenshot had: 
# - **분량**: 반드시 **최소 1,500자 이상의 풍부한 내용**을 작성하세요.
# This was on line 313.

with open('services/prompts.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Syntax error cleanup attempted")
