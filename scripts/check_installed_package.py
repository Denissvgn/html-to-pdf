"""Check a built installation with `python -I scripts/check_installed_package.py`."""

import io
import subprocess
import sys
import tempfile
import unittest
from importlib.metadata import metadata
from pathlib import Path

import html_to_pdf
from fastapi.testclient import TestClient
from pypdf import PdfReader

from html_to_pdf.web.app import DEFAULT_SAMPLE_PATH, app


class InstalledPackageTests(unittest.TestCase):
    def test_distribution_metadata_and_import_location(self):
        source_package = (Path(__file__).resolve().parents[1] / "html_to_pdf").resolve()
        self.assertNotIn(source_package, Path(html_to_pdf.__file__).resolve().parents)
        package_metadata = metadata("html-to-pdf")
        self.assertEqual(package_metadata["Author"], "Denis Sivagin")
        self.assertEqual(package_metadata["License-Expression"], "MIT")
        self.assertIn(
            "Author, https://github.com/Denissvgn",
            package_metadata.get_all("Project-URL"),
        )

    def test_web_resources(self):
        with TestClient(app) as client:
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("HTML to PDF", response.text)
            for filename in ("style.css", "app.js"):
                with self.subTest(filename=filename):
                    response = client.get(f"/static/{filename}")
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.content)

    def test_bundled_sample_conversion(self):
        self.assertTrue(DEFAULT_SAMPLE_PATH.is_file())
        with TestClient(app) as client:
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertTrue(health.json()["reference_file_exists"])
            for expand_collapsible in (False, True):
                with self.subTest(expand_collapsible=expand_collapsible):
                    response = client.post(
                        "/api/convert/path",
                        json={
                            "file_path": str(DEFAULT_SAMPLE_PATH),
                            "single_page": True,
                            "expand_collapsible": expand_collapsible,
                        },
                    )
                    self.assertEqual(response.status_code, 200, response.text[:500])
                    self.assertEqual(response.headers["content-type"], "application/pdf")
                    reader = PdfReader(io.BytesIO(response.content))
                    self.assertEqual(len(reader.pages), 1)
                    text = reader.pages[0].extract_text()
                    for detail in ("Alex Morgan", "Jordan Taylor"):
                        self.assertEqual(detail in text, expand_collapsible)

    def test_installed_cli_entry_points(self):
        with tempfile.TemporaryDirectory() as directory:
            for command in ("html-to-pdf", "pdf-merge"):
                with self.subTest(command=command):
                    executable = Path(sys.executable).parent / command
                    result = subprocess.run(
                        [str(executable), "--help"],
                        cwd=directory,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage:", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
