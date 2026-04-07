import asyncio
from services.blog_service import BlogService
from database import get_blogger_accounts

async def main():
    service = BlogService()
    accounts = get_blogger_accounts()
    if not accounts:
        print("No accounts found.")
        return
    
    # get first connected account
    acc = next((a for a in accounts if a.get('refresh_token')), None)
    if not acc:
        print("No connected accounts.")
        return
        
    print(f"Testing with account: {acc['name']} (ID: {acc['id']})")
    
    test_content = """
    <html>
      <body>
        <div class="bp-wrap">
          <style> .bp-wrap * { opacity: 1 !important; visibility: visible !important; } </style>
          <h1>Premium Test Post</h1>
          <p>This is a test post to verify Google Blogger API compatibility.</p>
        </div>
      </body>
    </html>
    """
    
    # 1. raw content
    print("\n--- TEST 1: Raw Premium Content ---")
    res1 = await service.post_to_blogger(
        title="Blogger API Compatibility Test 1",
        content=test_content,
        tags=["Test", "API"],
        account_id=acc['id'],
        summary="Test summary"
    )
    print("Result 1:", res1)
    
if __name__ == "__main__":
    asyncio.run(main())
