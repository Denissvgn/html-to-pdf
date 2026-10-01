"""Tests for PDF merging functionality and predetermined ordering."""

import io
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from html_to_pdf.converter import convert_html_string
from html_to_pdf.merger import merge_pdfs, main as merger_main
from html_to_pdf.web.app import app


@pytest.fixture
def sample_pdf_bytes():
    pdf1 = convert_html_string("<h1>First Document (Page 1)</h1>")
    pdf2 = convert_html_string("<h1>Second Document (Page 2)</h1>")
    pdf3 = convert_html_string("<h1>Third Document (Page 3)</h1>")
    return [pdf1, pdf2, pdf3]


def test_merge_pdfs_in_memory_order(sample_pdf_bytes):
    """Test merging PDF byte streams in exact order."""
    merged = merge_pdfs(sample_pdf_bytes)
    assert isinstance(merged, bytes)
    assert merged.startswith(b"%PDF-")

    reader = PdfReader(io.BytesIO(merged))
    assert len(reader.pages) == 3

    assert "First Document" in reader.pages[0].extract_text()
    assert "Second Document" in reader.pages[1].extract_text()
    assert "Third Document" in reader.pages[2].extract_text()


def test_merge_pdfs_reverse_order(sample_pdf_bytes):
    """Test merging in reversed predetermined order."""
    reversed_inputs = list(reversed(sample_pdf_bytes))
    merged = merge_pdfs(reversed_inputs)

    reader = PdfReader(io.BytesIO(merged))
    assert len(reader.pages) == 3

    assert "Third Document" in reader.pages[0].extract_text()
    assert "Second Document" in reader.pages[1].extract_text()
    assert "First Document" in reader.pages[2].extract_text()


def test_merge_pdfs_file_paths(sample_pdf_bytes):
    """Test merging from disk files with output path specified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        p1 = tmp_path / "doc_a.pdf"
        p2 = tmp_path / "doc_b.pdf"
        p1.write_bytes(sample_pdf_bytes[0])
        p2.write_bytes(sample_pdf_bytes[1])

        out = tmp_path / "merged_output.pdf"
        res = merge_pdfs([p1, p2], output_path=out)

        assert out.is_file()
        assert out.stat().st_size == len(res)

        reader = PdfReader(str(out))
        assert len(reader.pages) == 2
        assert "First Document" in reader.pages[0].extract_text()
        assert "Second Document" in reader.pages[1].extract_text()


def test_merge_missing_file_raises():
    """Test that missing input file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        merge_pdfs(["/tmp/definitely_non_existent_12345.pdf"])


def test_merge_empty_inputs_raises():
    """Test that empty inputs sequence raises ValueError."""
    with pytest.raises(ValueError):
        merge_pdfs([])


def test_cli_merger_main(sample_pdf_bytes):
    """Test CLI entry point with command line arguments."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        f1 = tmp_path / "part1.pdf"
        f2 = tmp_path / "part2.pdf"
        out = tmp_path / "glued.pdf"

        f1.write_bytes(sample_pdf_bytes[0])
        f2.write_bytes(sample_pdf_bytes[1])

        exit_code = merger_main(["-o", str(out), str(f1), str(f2)])
        assert exit_code == 0
        assert out.is_file()

        reader = PdfReader(str(out))
        assert len(reader.pages) == 2
        assert "First Document" in reader.pages[0].extract_text()
        assert "Second Document" in reader.pages[1].extract_text()


def test_cli_merger_file_list(sample_pdf_bytes):
    """Test CLI entry point using --file-list argument."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        f1 = tmp_path / "first.pdf"
        f2 = tmp_path / "second.pdf"
        out = tmp_path / "glued_list.pdf"

        f1.write_bytes(sample_pdf_bytes[0])
        f2.write_bytes(sample_pdf_bytes[1])

        list_file = tmp_path / "order.txt"
        list_file.write_text(f"{f2}\n{f1}\n", encoding="utf-8")

        exit_code = merger_main(["-o", str(out), "--file-list", str(list_file)])
        assert exit_code == 0
        assert out.is_file()

        reader = PdfReader(str(out))
        assert len(reader.pages) == 2
        # Predetermined order from order.txt: f2 first, then f1
        assert "Second Document" in reader.pages[0].extract_text()
        assert "First Document" in reader.pages[1].extract_text()


def test_fastapi_merge_paths_endpoint(sample_pdf_bytes):
    """Test POST /api/pdf/merge endpoint with server file paths."""
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        f1 = tmp_path / "receipt1.pdf"
        f2 = tmp_path / "receipt2.pdf"
        f1.write_bytes(sample_pdf_bytes[0])
        f2.write_bytes(sample_pdf_bytes[1])

        payload = {
            "files": [str(f1), str(f2)],
            "output_filename": "all_receipts.pdf",
        }
        response = client.post("/api/pdf/merge", json=payload)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-")

        reader = PdfReader(io.BytesIO(response.content))
        assert len(reader.pages) == 2
        assert "First Document" in reader.pages[0].extract_text()
        assert "Second Document" in reader.pages[1].extract_text()


def test_fastapi_merge_uploads_endpoint(sample_pdf_bytes):
    """Test POST /api/pdf/merge-uploads endpoint with multipart files."""
    client = TestClient(app)
    files = [
        ("files", ("receipt_a.pdf", sample_pdf_bytes[1], "application/pdf")),
        ("files", ("receipt_b.pdf", sample_pdf_bytes[2], "application/pdf")),
    ]
    response = client.post("/api/pdf/merge-uploads", files=files, data={"output_filename": "combined.pdf"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    reader = PdfReader(io.BytesIO(response.content))
    assert len(reader.pages) == 2
    assert "Second Document" in reader.pages[0].extract_text()
    assert "Third Document" in reader.pages[1].extract_text()
