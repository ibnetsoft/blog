import asyncio
import httpx
from services.blog_service import blog_service
from config import config
import database as db

async def test_blogger_with_bad_tags():
    # Attempt to post with tags that need sanitization
    account_id = 1
    acc = db.get_blogger_account(account_id)
    if not acc:
        print("Account 1 not found")
        return

    print(f"Verifying Blogger fix for account: {acc['name']} (ID: {acc['id']})")
    print(f"Blog ID: {acc.get('blog_id')}")
    
    title = "Verify Fix Post " + config.get_kst_time().strftime("%Y-%m-%d %H:%M:%S")
    content = "<p>This is a verification post to ensure labels are sanitized and payload is simplified.</p>"
    # Tags with commas, special chars, and long strings
    tags = "tag1,tag2,tag3"
    
    print("Calling post_to_blogger...")
    try:
        res = await asyncio.wait_for(blog_service.post_to_blogger(
            title=title,
            content=content,
            tags=tags,
            account_id=account_id,
            category="category,with,commas"
        ), timeout=60)
    except asyncio.TimeoutError:
        print("Timeout calling post_to_blogger")
        return
    except Exception as e:
        print(f"Exception during post_to_blogger: {e}")
        return
    
    print(f"Result: {res}")
    if res.get("status") == "ok":
        print("SUCCESS: Sanitization worked, post created.")
    else:
        print(f"FAILED: {res.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_blogger_with_bad_tags())
