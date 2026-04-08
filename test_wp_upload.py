
import asyncio
import os
import httpx
import base64
from config import config

async def test_wp_upload():
    wp_url = config.WP_URL.rstrip('/')
    username = config.WP_USERNAME
    password = config.WP_PASSWORD
    
    if not wp_url or not username or not password:
        print("❌ WordPress settings are missing in .env")
        return

    print(f"Testing WordPress Upload to: {wp_url}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    
    endpoint = f"{wp_url}/index.php?rest_route=/wp/v2/media"
    auth_str = f"{username}:{password}"
    auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    # Create a dummy image for testing
    test_image_path = "test_upload.png"
    from PIL import Image
    img = Image.new('RGB', (100, 100), color = (73, 109, 137))
    img.save(test_image_path)
    
    try:
        with open(test_image_path, 'rb') as f:
            image_data = f.read()

        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Disposition": f'attachment; filename="test_upload.png"',
            "Content-Type": "image/png"
        }

        async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
            print("Sending request to WordPress...")
            res = await client.post(endpoint, content=image_data, headers=headers, timeout=30)
            
            print(f"Status Code: {res.status_code}")
            if res.status_code in [200, 201]:
                data = res.json()
                print("✅ Upload Success!")
                print(f"Media ID: {data.get('id')}")
                print(f"URL: {data.get('source_url')}")
            else:
                print(f"❌ Upload Failed: {res.text[:500]}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if os.path.exists(test_image_path):
            os.remove(test_image_path)

if __name__ == "__main__":
    asyncio.run(test_wp_upload())
