import asyncio
import httpx
from services.blog_service import blog_service
from config import config
import database as db

async def test_blogger_direct():
    # Attempt to post a simple test to the failing account
    account_id = 1
    acc = db.get_blogger_account(account_id)
    if not acc:
        print("Account 1 not found")
        return

    print(f"Testing Blogger account: {acc['name']} (ID: {acc['id']})")
    
    title = "Test Post from Antigravity " + config.get_kst_time().strftime("%Y-%m-%d %H:%M:%S")
    content = "<p>This is a test post to diagnose the 400 Invalid Argument error.</p>"
    tags = ["test", "debug"]
    
    res = await blog_service.post_to_blogger(
        title=title,
        content=content,
        tags=tags,
        account_id=account_id
    )
    
    print(f"Result: {res}")

if __name__ == "__main__":
    asyncio.run(test_blogger_direct())
