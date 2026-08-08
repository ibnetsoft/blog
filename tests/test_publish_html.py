import unittest

from services.publish_service import publish_service


class BuildBlogHtmlTests(unittest.TestCase):
    def test_replaces_image_placeholder_with_figure_markup(self):
        content = "Intro\n[[IMAGE_1]]\nOutro"
        images = [{"image_url": "https://example.com/a.png", "caption": "Example"}]

        html = publish_service.build_blog_html(content, images)

        self.assertIn('src="https://example.com/a.png"', html)
        self.assertIn("<figcaption", html)
        self.assertNotIn("[[IMAGE_1]]", html)

    def test_strips_unused_image_placeholders_when_no_images(self):
        content = "Hello [[IMAGE_1]] world (이미지 1)"

        html = publish_service.build_blog_html(content, [])

        self.assertNotIn("[[IMAGE_1]]", html)
        self.assertNotIn("(이미지 1)", html)


if __name__ == "__main__":
    unittest.main()
