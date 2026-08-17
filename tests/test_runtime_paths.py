from __future__ import annotations

import unittest
from unittest.mock import patch

from jarvis.local_commands import extract_file_command, run_file_command
from jarvis.wake import is_wake_word_match


class WakeWordTests(unittest.TestCase):
    def test_observed_transcription_variants_wake_jarvis(self) -> None:
        for transcript in ("Hey Javi.", "Hey Javis.", "Hey Jud", "Hey job is", "Major."):
            with self.subTest(transcript=transcript):
                self.assertTrue(is_wake_word_match(transcript))

    def test_unrelated_words_do_not_wake_jarvis(self) -> None:
        for transcript in (
            "the major update is ready",
            "Hey John, it's...",
            "play some music",
            "open the document",
        ):
            with self.subTest(transcript=transcript):
                self.assertFalse(is_wake_word_match(transcript))


class LocalFileCommandTests(unittest.TestCase):
    def test_extracts_open_command_without_gemini(self) -> None:
        self.assertEqual(
            extract_file_command("Open the file named summer ATS resume"),
            ("open", "summer ats resume"),
        )

    def test_extracts_find_command_with_spoken_filename(self) -> None:
        self.assertEqual(
            extract_file_command("Find the document called Samar ATS Resume"),
            ("find", "samar ats resume"),
        )

    def test_local_open_result_is_spoken_from_tool_contract(self) -> None:
        with patch(
            "jarvis.local_commands.open_file",
            return_value="TOOL_OK: Open request for Samar_ATS_Resume.pdf was accepted by the operating system.",
        ):
            result = run_file_command("open", "summer ats resume")

        self.assertTrue(result.startswith("Confirmed, sir."))
        self.assertIn("Samar_ATS_Resume.pdf", result)

    def test_local_open_failure_is_not_reported_as_success(self) -> None:
        with patch(
            "jarvis.local_commands.open_file",
            return_value="TOOL_ERROR: No file matching 'summer ats resume' was found.",
        ):
            result = run_file_command("open", "summer ats resume")

        self.assertTrue(result.startswith("I couldn't complete that, sir."))
        self.assertNotIn("Confirmed, sir.", result)


if __name__ == "__main__":
    unittest.main()
