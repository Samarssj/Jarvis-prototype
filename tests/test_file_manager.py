from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.tools import file_manager


class FileManagerMatchingTests(unittest.TestCase):
    def test_spoken_summer_finds_samar_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Samar_ATS_Resume.pdf.pdf"
            target.write_bytes(b"resume")

            with patch.object(file_manager, "SAFE_ROOTS", [root]):
                result = file_manager.find_file("summer")

            self.assertIn("TOOL_OK", result)
            self.assertIn(target.name, result)

    def test_spoken_name_ignores_separators_and_repeated_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Samar_ATS_Resume.pdf-3.pdf"
            target.write_bytes(b"resume")

            with patch.object(file_manager, "SAFE_ROOTS", [root]):
                result = file_manager.find_file("Samar ATS Resume")

            self.assertIn("TOOL_OK", result)
            self.assertIn(target.name, result)

    def test_unrelated_word_does_not_match_fuzzily(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Samar_ATS_Resume.pdf").write_bytes(b"resume")

            with patch.object(file_manager, "SAFE_ROOTS", [root]):
                result = file_manager.find_file("completely-unrelated-document")

            self.assertIn("TOOL_ERROR", result)
            self.assertIn("No file matching", result)

    def test_multiple_candidates_are_returned_in_ranked_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            closest = root / "Samar_ATS_Resume.pdf.pdf"
            farther = root / "Samar_ATS_Old_Resume.pdf"
            closest.write_bytes(b"resume")
            farther.write_bytes(b"resume")

            with patch.object(file_manager, "SAFE_ROOTS", [root]):
                result = file_manager.find_file("samar ats resume")

            self.assertIn("TOOL_OK", result)
            self.assertLess(result.index(closest.name), result.index(farther.name))


if __name__ == "__main__":
    unittest.main()
