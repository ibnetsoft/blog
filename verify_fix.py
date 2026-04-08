import re

def test_label_cleaning(tags_str):
    # Simulate the logic in post_to_blogger
    full_labels = []
    
    # 영어 쉼표(,)와 아랍어 쉼표(،) 모두 지원
    full_labels.extend([t.strip() for t in re.split(r'[,،]', tags_str) if t.strip()])
    
    print(f"Original tags: '{tags_str}'")
    print(f"Split labels: {full_labels}")
    
    safe_labels = []
    for label in full_labels:
        if not label: continue
        
        # 영어 쉼표와 아랍어 쉼표 모두 공백으로 제거
        clean_label = re.sub(r'[,،]', ' ', label)
        
        # BiDi 제어 문자 제거
        clean_label = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', clean_label)
        
        # 특수 문자 제거
        for char in '<>{}[]~':
            clean_label = clean_label.replace(char, '')
            
        # 연속된 공백 정리
        clean_label = re.sub(r'\s+', ' ', clean_label).strip()
        
        if len(clean_label) > 200:
            clean_label = clean_label[:197] + "..."
            
        if clean_label and clean_label not in safe_labels:
            safe_labels.append(clean_label)
            
    print(f"Safe labels: {safe_labels}")
    return safe_labels

# Test 1: Arabic labels with Arabic commas
test_label_cleaning("الشهر، الحوثيون، اليمن، الحرب الأهلية")

# Test 2: Mixed labels
test_label_cleaning("Houthi, اليمن، Security, الحرب")

# Test 3: Labels with BiDi controls (simulated)
test_label_cleaning("Tag1\u200e, Tag2\u200f")

# Test 4: Labels with multiple spaces and special chars
test_label_cleaning("Tag [1] ,  Tag ~ 2 ")
