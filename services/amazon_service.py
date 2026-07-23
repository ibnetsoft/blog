import httpx
from bs4 import BeautifulSoup
import re
import random
from typing import Dict, Any, Optional

class AmazonService:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
        ]

    def _get_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Device-Memory": "8",
            "Viewport-Width": "1920",
            "Connect-Time": "5",
            "Service-Worker-Navigation-Preload": "true",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.google.com/",
        }

    def clean_url(self, url: str) -> str:
        """아마존 URL에서 불필요한 파라미터를 제거하고 ASIN 중심의 깔끔한 URL 반환"""
        # ASIN 패턴 추출 (dp/ 또는 gp/product/ 뒤의 10자리 영문숫자)
        asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
        if asin_match:
            asin = asin_match.group(1)
            # 도메인 추출 (www.amazon.com, www.amazon.co.jp 등)
            domain_match = re.search(r'(https?://www\.amazon\.[a-z.]+)', url)
            if domain_match:
                return f"{domain_match.group(1)}/dp/{asin}"
        return url

    async def fetch_product_details(self, url: str) -> Dict[str, Any]:
        """아마존 상품 페이지에서 정보를 추출합니다."""
        target_url = self.clean_url(url)
        print(f"[AmazonService] Fetching: {target_url}")

        async with httpx.AsyncClient(headers=self._get_headers(), follow_redirects=True, timeout=20.0) as client:
            try:
                response = await client.get(target_url)
                if response.status_code != 200:
                    return {"status": "error", "error": f"HTTP {response.status_code}"}
                
                html = response.text
                if "api-services-support@amazon.com" in html or "To discuss automated access to Amazon data please contact" in html:
                    return {"status": "error", "error": "Amazon blocked the request (CAPTCHA/Bot detection)"}

                soup = BeautifulSoup(html, "lxml")
                
                # 1. 제목 (Title)
                title_tag = soup.select_one("#productTitle")
                title = title_tag.get_text().strip() if title_tag else "Unknown Product"

                # 2. 가격 (Price)
                price = ""
                # 다양한 가격 태그 시도
                price_selectors = [
                    ".a-price .a-offscreen", 
                    "#priceblock_ourprice", 
                    "#priceblock_dealprice", 
                    ".a-price-whole"
                ]
                for sel in price_selectors:
                    p_tag = soup.select_one(sel)
                    if p_tag:
                        price = p_tag.get_text().strip()
                        break

                # 3. 주요 특징 (Bullet Points)
                features = []
                feature_list = soup.select("#feature-bullets ul li span")
                if feature_list:
                    features = [f.get_text().strip() for f in feature_list if f.get_text().strip()]

                # 4. 상품 설명 (Description)
                description = ""
                desc_tag = soup.select_one("#productDescription")
                if desc_tag:
                    description = desc_tag.get_text().strip()

                # 5. 메인 이미지 (Image)
                image_url = ""
                img_tag = soup.select_one("#landingImage")
                if img_tag:
                    # data-old-hires 또는 data-a-dynamic-image 에서 가장 큰 이미지 추출 시도
                    dynamic_img = img_tag.get("data-a-dynamic-image")
                    if dynamic_img:
                        # JSON 형식의 키값 중 첫 번째(보통 가장 큰 주소) 추출
                        img_match = re.search(r'"(https://[^"]+)"', dynamic_img)
                        if img_match:
                            image_url = img_match.group(1)
                    
                    if not image_url:
                        image_url = img_tag.get("src") or img_tag.get("data-old-hires")

                # 6. 별점 및 리뷰 수 (Rating & Reviews)
                rating = ""
                rating_tag = soup.select_one("span.a-icon-alt")
                if rating_tag:
                    rating = rating_tag.get_text().strip()

                review_count = ""
                review_tag = soup.select_one("#acrCustomerReviewText")
                if review_tag:
                    review_count = review_tag.get_text().strip()

                return {
                    "status": "ok",
                    "url": target_url,
                    "title": title,
                    "price": price,
                    "features": features,
                    "description": description,
                    "image_url": image_url,
                    "rating": rating,
                    "review_count": review_count
                }

            except Exception as e:
                print(f"[AmazonService] Error: {e}")
                return {"status": "error", "error": str(e)}

amazon_service = AmazonService()
