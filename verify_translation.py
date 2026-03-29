import asyncio
import os
import sys

# 프로젝트 경로 추가
sys.path.append(r"d:\BLOG\blog_app")

from services.blog_service import blog_service

async def verify():
    print("Testing translation for all metadata fields...")
    import sys
    import os
    # BlogService 인스턴스 생성 또는 가져오기
    from services.blog_service import blog_service
    
    # 실제 호출
    res = await blog_service.translate_blog(
        title="안녕하세요, 오늘의 뉴스입니다.",
        content="<p>본문 내용입니다.</p>",
        target_language="ja",
        summary="요약 내용입니다.",
        tags="뉴스, 일상",
        category="시사",
        skip_content=True
    )
    
    print("\n[RESULT]")
    import json
    print(json.dumps(res, indent=2, ensure_ascii=False))
    
    expected_keys = ["status", "title", "content", "summary", "tags", "category"]
    missing = [k for k in expected_keys if k not in res]
    
    if not missing and res.get("status") == "ok":
        print("\nSUCCESS: All expected fields are present in the response.")
    else:
        print(f"\nFAILED: Missing keys: {missing}")

if __name__ == "__main__":
    try:
        asyncio.run(verify())
    except Exception as e:
        print(f"Error during verification: {e}")
