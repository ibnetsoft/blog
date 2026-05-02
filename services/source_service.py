import re
import httpx
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import PyPDF2
import os
from typing import Optional, List, Dict

class SourceService:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def extract_content(self, source_type: str, value: str) -> Dict[str, str]:
        """주어진 소스 타입에 따라 콘텐츠 추출"""
        try:
            if source_type == "url":
                return await self.extract_from_web(value)
            elif source_type == "youtube":
                return await self.extract_from_youtube(value)
            elif source_type == "file":
                return await self.extract_from_file(value)
            else:
                return {"status": "error", "message": f"지원하지 않는 소스 타입입니다: {source_type}"}
        except Exception as e:
            return {"status": "error", "message": f"추출 중 오류 발생: {str(e)}"}

    async def extract_from_web(self, url: str) -> Dict[str, str]:
        """웹 페이지 본문 추출"""
        try:
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=15) as client:
                res = await client.get(url)
                res.raise_for_status()
                
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 불필요한 태그 제거
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
                tag.decompose()
                
            # 본문 후보 태그들
            article = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|article|post|body', re.I))
            
            if not article:
                text = soup.body.get_text(separator='\n', strip=True) if soup.body else soup.get_text(separator='\n', strip=True)
            else:
                text = article.get_text(separator='\n', strip=True)
                
            lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 10]
            clean_text = '\n'.join(lines)

            if not clean_text.strip():
                return {"status": "error", "message": "해당 URL에서 본문 내용을 추출할 수 없습니다. 로그인이 필요하거나 동적 페이지일 수 있습니다."}

            title = soup.title.string if soup.title else url

            return {
                "status": "ok",
                "title": title.strip() if title else url,
                "content": clean_text[:10000],
                "type": "web"
            }
        except Exception as e:
            return {"status": "error", "message": f"웹 추출 실패: {str(e)}"}

    async def extract_from_youtube(self, url: str) -> Dict[str, str]:
        """유튜브 자막 및 메타데이터 추출"""
        try:
            video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
            if not video_id_match:
                return {"status": "error", "message": "유효한 유튜브 비디오 ID를 찾을 수 없습니다."}
            
            video_id = video_id_match.group(1)
            
            try:
                # 1. 자막 추출 시도
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                try:
                    transcript = transcript_list.find_transcript(['ko', 'en', 'ja'])
                except:
                    transcript = next(iter(transcript_list))
                
                data = transcript.fetch()
                full_text = " ".join([item['text'] for item in data])
                
                return {
                    "status": "ok",
                    "title": f"YouTube: {video_id}",
                    "content": full_text[:15000],
                    "type": "youtube"
                }
            except Exception as e:
                # 2. 자막 실패 시 메타데이터(제목, 설명)로 폴백
                metadata = await self.fetch_youtube_metadata(url)
                if metadata["status"] == "ok":
                    return {
                        "status": "ok",
                        "title": metadata["title"],
                        "content": f"[자막 없음 - 영상 정보로 대체]\n\n제목: {metadata['title']}\n설명: {metadata['description']}",
                        "type": "youtube_meta"
                    }
                return {"status": "error", "message": f"자막 및 정보를 불러올 수 없는 영상입니다: {str(e)}"}
                
        except Exception as e:
            return {"status": "error", "message": f"유튜브 추출 실패: {str(e)}"}

    async def fetch_youtube_metadata(self, url: str) -> Dict[str, str]:
        """비디오 메타데이터(제목, 설명) 추출"""
        try:
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=10) as client:
                res = await client.get(url)
                res.raise_for_status()
                
            soup = BeautifulSoup(res.text, 'html.parser')
            title = soup.find('meta', property='og:title')
            desc = soup.find('meta', property='og:description')
            
            return {
                "status": "ok",
                "title": title['content'] if title else "제목 없음",
                "description": desc['content'] if desc else "설명 없음"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def extract_from_file(self, filepath: str) -> Dict[str, str]:
        """파일(PDF, TXT)에서 텍스트 추출"""
        try:
            if not os.path.exists(filepath):
                return {"status": "error", "message": "파일을 찾을 수 없습니다."}
                
            ext = os.path.splitext(filepath)[1].lower()
            
            if ext == ".pdf":
                text = ""
                with open(filepath, 'rb') as f:
                    pdf = PyPDF2.PdfReader(f)
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text += extracted + "\n"
                if not text.strip():
                    return {"status": "error", "message": "PDF에서 텍스트를 추출할 수 없습니다. 이미지 스캔본 PDF이거나 보호된 파일일 수 있습니다."}
                return {"status": "ok", "title": os.path.basename(filepath), "content": text[:15000], "type": "pdf"}
            
            elif ext in [".txt", ".md"]:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                return {"status": "ok", "title": os.path.basename(filepath), "content": text[:15000], "type": "text"}
            
            else:
                return {"status": "error", "message": "지원하지 않는 파일 형식입니다 (PDF, TXT만 가능)."}
                
        except Exception as e:
            return {"status": "error", "message": f"파일 추출 실패: {str(e)}"}

source_service = SourceService()
