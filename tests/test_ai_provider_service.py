import unittest
from unittest.mock import patch

from services.ai_provider_service import AIProviderService


class AIProviderServiceTests(unittest.TestCase):
    def test_resolve_provider_matches_custom_alias_by_name(self):
        service = AIProviderService()
        custom_provider = {
            "name": "deepseek",
            "provider_type": "openai_compatible",
            "api_url": "https://api.deepseek.com/v1",
            "api_key": "secret",
            "default_model": "deepseek-chat",
        }

        with patch.object(service, "_active_custom_providers", return_value=[custom_provider]):
            selection = service.resolve_provider("deepseek", "")

        self.assertEqual(selection.name, "deepseek")
        self.assertEqual(selection.provider_type, "openai_compatible")
        self.assertEqual(selection.model, "deepseek-chat")

    def test_resolve_provider_matches_glm_alias_from_custom_provider_metadata(self):
        service = AIProviderService()
        custom_provider = {
            "name": "zhipu-custom",
            "provider_type": "openai_compatible",
            "api_url": "https://open.bigmodel.cn/api/paas/v4",
            "api_key": "secret",
            "default_model": "glm-4.5",
        }

        with patch.object(service, "_active_custom_providers", return_value=[custom_provider]):
            selection = service.resolve_provider("glm", "")

        self.assertEqual(selection.name, "zhipu-custom")
        self.assertEqual(selection.model, "glm-4.5")


if __name__ == "__main__":
    unittest.main()
