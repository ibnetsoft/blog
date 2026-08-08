import asyncio
import unittest

from services.publish_utils import run_with_backoff, validate_blog_post_payload, validate_publish_html


class PublishUtilsTests(unittest.TestCase):
    def test_validate_blog_post_payload_rejects_short_content(self):
        result = validate_blog_post_payload("Title", "too short", ["wordpress"])

        self.assertFalse(result["ok"])
        self.assertIn("content is too short", result["errors"])

    def test_validate_publish_html_flags_disallowed_tags(self):
        result = validate_publish_html("<p>safe enough content for length</p><script>alert(1)</script>")

        self.assertFalse(result["ok"])
        self.assertTrue(any("disallowed html tag" in error for error in result["errors"]))

    def test_run_with_backoff_returns_success_after_retryable_failure(self):
        calls = {"count": 0}

        async def operation():
            calls["count"] += 1
            if calls["count"] == 1:
                return {"status": "error", "error": "network timeout"}
            return {"status": "ok", "url": "https://example.com/post"}

        result = asyncio.run(run_with_backoff(operation, platform="wordpress", max_attempts=2, base_delay=0.0))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()
