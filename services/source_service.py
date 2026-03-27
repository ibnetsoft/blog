import httpx
from bs4 import BeautifulSoup
import os
import re
from typing import Optional, Dict

class SourceService:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def extract_text_from_url(self, url: str) -> Dict[str, str]:
        """URL에서 정보(기사 또는 유튜브 자막) 추출"""
        # 유튜브 URL 체크
        if "youtube.com" in url or "youtu.be" in url:
            return await self.extract_text_from_youtube(url)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=self.headers, follow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 제목 추출
                title = ""
                title_tag = soup.find('h1') or soup.find('title')
                if title_tag:
                    title = title_tag.get_text().strip()
                
                # 본문 추출 (일반적인 뉴스 사이트 태그들 시도)
                # 불필요한 태그 제거
                for s in soup(['script', 'style', 'nav', 'header', 'footer', 'iframe', 'aside', 'button', 'input']):
                    s.extract()
                
                # 본문 후보 태그들
                content_selectors = [
                    'article', '.article_body', '.article_content', '#articleBody', 
                    '.news_content', '.view_content', '.content_area', 'main'
                ]
                
                content = ""
                for selector in content_selectors:
                    found = soup.select_one(selector)
                    if found:
                        content = found.get_text(separator='\n').strip()
                        break
                
                if not content:
                    # 후보가 없으면 body에서 추출
                    content = soup.body.get_text(separator='\n').strip() if soup.body else ""
                
                # 공백 정리
                content = re.sub(r'\n+', '\n', content)
                content = re.sub(r' +', ' ', content)
                
                return {
                    "title": title or "제목 없음",
                    "content": content,
                    "url": url
                }
        except Exception as e:
            print(f"URL Extraction Error: {e}")
            raise Exception(f"Failed to extract content from URL: {str(e)}")

    async def extract_text_from_youtube(self, url: str) -> Dict[str, str]:
        """유튜브 URL에서 자막(Transcript) 추출"""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        # Video ID 추출
        video_id = None
        if "v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]

        if not video_id:
            raise Exception("유튜브 URL에서 Video ID를 찾을 수 없습니다.")

        # 제목 추출
        title = f"YouTube Video ({video_id})"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                )
                if res.status_code == 200:
                    title = res.json().get('title', title)
        except:
            pass

        # 자막 추출 (동기 라이브러리 → thread pool 실행)
        def _fetch_transcript():
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()

            # 1차 시도: 한국어/영어 직접 요청
            try:
                return api.fetch(video_id, languages=['ko', 'ko-KR', 'en', 'en-US'])
            except Exception:
                pass

            # 2차 시도: 사용 가능한 자막 중 첫 번째
            try:
                transcript_list = api.list(video_id)
                for t in transcript_list:
                    try:
                        return t.fetch()
                    except Exception:
                        continue
            except Exception as e2:
                raise Exception(f"자막 목록 조회 실패: {e2}")

            raise Exception("이 영상에는 사용 가능한 자막이 없습니다.")

        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as pool:
                data = await loop.run_in_executor(pool, _fetch_transcript)
        except Exception as e:
            print(f"YouTube Extraction Error: {e}")
            raise Exception(f"유튜브 자막 추출 실패: {str(e)}")

        # item이 dict(구버전) 또는 object(신버전) 모두 처리
        texts = []
        for item in data:
            if isinstance(item, dict):
                texts.append(item.get('text', ''))
            elif hasattr(item, 'text'):
                texts.append(str(item.text))
            else:
                texts.append(str(item))

        full_text = " ".join(texts)

        if not full_text.strip():
            raise Exception("자막을 가져왔으나 내용이 비어있습니다.")

        return {
            "title": title,
            "content": full_text,
            "url": url
        }

    def extract_text_from_file(self, file_path: str) -> Dict[str, str]:
        """로컬 파일(TXT)에서 텍스트 추출"""
        try:
            filename = os.path.basename(file_path)
            content = ""
            
            # 인코딩 시도 (utf-8, cp949)
            encodings = ['utf-8', 'cp949', 'euc-kr']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if not content:
                raise Exception("Failed to read file with supported encodings.")
                
            return {
                "title": filename,
                "content": content,
                "url": None
            }
        except Exception as e:
            print(f"File Extraction Error: {e}")
            raise Exception(f"Failed to extract text from file: {str(e)}")

source_service = SourceService()
