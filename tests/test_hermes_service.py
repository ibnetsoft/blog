import unittest
from unittest.mock import AsyncMock, patch

from services.hermes_service import HermesService


class HermesServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_publish_request_collects_generated_platform_outputs(self):
        service = HermesService()
        generated_results = {
            "status": "ok",
            "results": [
                {
                    "status": "ok",
                    "platform": "wordpress",
                    "target_id": "wordpress",
                    "language": "ko",
                    "title": "테스트 제목",
                    "summary": "요약",
                    "tags": ["ai", "blog"],
                    "content": "<p>본문</p>",
                }
            ],
        }

        with patch("services.hermes_service.blog_service.generate_independent_multi_language_blogs", new=AsyncMock(return_value=generated_results)), \
             patch("services.hermes_service.blog_service.add_images_to_content", new=AsyncMock(return_value={"status": "ok", "content": "<p>본문+이미지</p>"})):
            result = await service.build_publish_request(
                topic="테스트 토픽",
                category="IT",
                platforms=[{"platform": "wordpress", "target_id": "wordpress", "language": "ko"}],
                provider="deepseek",
                model="deepseek-chat",
            )

        self.assertEqual(result["status"], "ok")
        request = result["request"]
        self.assertEqual(request.title, "테스트 제목")
        self.assertEqual(request.platforms, ["wordpress"])
        self.assertEqual(request.contents["wordpress"], "<p>본문+이미지</p>")


if __name__ == "__main__":
    unittest.main()
