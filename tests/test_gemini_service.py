import unittest

from services.gemini_service import GeminiService


class GeminiServicePromptGuardrailTests(unittest.TestCase):
    def test_apply_anatomy_guardrail_adds_constraints_for_human_subjects(self):
        prompt = "Photorealistic portrait of a single businesswoman in an office"

        guarded = GeminiService._apply_anatomy_guardrail(prompt, no_human=False)

        self.assertIn("exactly two arms", guarded)
        self.assertIn("five fingers on each hand", guarded)

    def test_apply_anatomy_guardrail_skips_non_human_prompts(self):
        prompt = "Premium product photo of a ceramic coffee mug on a clean desk"

        guarded = GeminiService._apply_anatomy_guardrail(prompt, no_human=False)

        self.assertEqual(prompt, guarded)

    def test_apply_anatomy_guardrail_skips_when_no_human_mode(self):
        prompt = "Portrait of a young teacher explaining a lesson"

        guarded = GeminiService._apply_anatomy_guardrail(prompt, no_human=True)

        self.assertEqual(prompt, guarded)


if __name__ == "__main__":
    unittest.main()
