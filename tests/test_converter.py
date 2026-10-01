"""Tests for HTML to PDF converter application using generic fixtures and public pages."""

import http.server
import io
import os
import socketserver
import sqlite3
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from html_to_pdf.config import PDFOptions
from html_to_pdf.converter import HTMLToPDFConverter, convert_file, convert_html_string, convert_url
from html_to_pdf.cookies import extract_firefox_cookies, extract_firefox_localstorage, find_firefox_profiles
from html_to_pdf.web.app import DEFAULT_SAMPLE_PATH, app

SAMPLE_RECEIPT_PATH = DEFAULT_SAMPLE_PATH


@pytest.fixture(scope="module")
def converter():
    return HTMLToPDFConverter()


def test_convert_sample_receipt_standard(converter):
    """Test converting the generic sample receipt HTML with standard A4 format."""
    assert SAMPLE_RECEIPT_PATH.exists(), f"Sample receipt not found at {SAMPLE_RECEIPT_PATH}"

    opts = PDFOptions(format="A4", media_type="screen", print_background=True)
    pdf_bytes = converter.convert_file(str(SAMPLE_RECEIPT_PATH), options=opts)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 10000
    assert pdf_bytes.startswith(b"%PDF-")


def test_convert_sample_receipt_single_page(converter):
    """Test converting the generic sample receipt HTML in continuous single-page mode."""
    opts = PDFOptions(single_page=True, media_type="screen", print_background=True)
    pdf_bytes = converter.convert_file(str(SAMPLE_RECEIPT_PATH), options=opts)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 10000
    assert pdf_bytes.startswith(b"%PDF-")


def test_convert_html_string(converter):
    """Test converting raw HTML string."""
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: sans-serif; background-color: #f0fdf4; padding: 40px; }
            h1 { color: #166534; }
            .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Invoice #INV-2026-001</h1>
            <p>Customer: John Doe</p>
            <p>Total: $450.00</p>
        </div>
    </body>
    </html>
    """
    pdf_bytes = converter.convert_html_string(sample_html)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_convert_local_web_server(converter):
    """Test converting an actual web URL by serving content via local HTTP server."""
    server_dir = tempfile.mkdtemp()
    test_html = Path(server_dir) / "index.html"
    test_html.write_text("<html><body><h1>Public Web Render Test</h1></body></html>", encoding="utf-8")

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    import functools
    handler = functools.partial(QuietHandler, directory=server_dir)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    try:
        url = f"http://127.0.0.1:{port}/index.html"
        pdf_bytes = converter.convert_url(url)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF-")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_fastapi_index():
    """Test main HTML UI index route."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "HTML to PDF" in response.text


def test_fastapi_health():
    """Test health check endpoint."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["reference_file_exists"] is True


def test_fastapi_convert_path():
    """Test API endpoint converting reference receipt by file path."""
    client = TestClient(app)
    payload = {
        "file_path": str(SAMPLE_RECEIPT_PATH),
        "format": "A4",
        "single_page": True,
        "media_type": "screen",
    }
    response = client.post("/api/convert/path", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 10000
    assert response.content.startswith(b"%PDF-")


def test_fastapi_convert_html():
    """Test API endpoint converting raw HTML."""
    client = TestClient(app)
    payload = {
        "html_content": "<h1>Test Document</h1><p>FastAPI HTML to PDF</p>",
        "format": "Letter",
    }
    response = client.post("/api/convert/html", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_fastapi_convert_upload():
    """Test API endpoint with uploaded file."""
    client = TestClient(app)
    sample_content = b"<html><body><h2>Uploaded HTML Test</h2></body></html>"
    files = {"file": ("test_doc.html", sample_content, "text/html")}
    response = client.post("/api/convert/upload", files=files)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_expand_collapsible_details_and_aria(converter):
    """Test expanding HTML5 details and aria-expanded elements."""
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Accordion Test</h1>
        <details>
            <summary>Click to view secret details</summary>
            <p>Hidden Content In Details Tag</p>
        </details>
        <button aria-expanded="false" aria-controls="section1" onclick="document.getElementById('section1').hidden=false">
            Toggle Aria Section
        </button>
        <div id="section1" hidden>
            <p>Hidden Content In Aria Section</p>
        </div>
    </body>
    </html>
    """
    opts = PDFOptions(expand_collapsible=True)
    pdf_bytes = converter.convert_html_string(html, options=opts)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")

    proc = subprocess.run(["pdftotext", "-", "-"], input=pdf_bytes, capture_output=True)
    extracted = proc.stdout.decode("utf-8", errors="ignore")
    assert "Hidden Content In Details Tag" in extracted


def test_expand_collapsible_sample_receipt(converter):
    """Test that expanding collapsibles on the sample receipt includes recipient and sender details."""
    assert SAMPLE_RECEIPT_PATH.exists()

    opts = PDFOptions(expand_collapsible=True, single_page=True)
    pdf_bytes = converter.convert_file(str(SAMPLE_RECEIPT_PATH), options=opts)

    proc = subprocess.run(["pdftotext", "-", "-"], input=pdf_bytes, capture_output=True)
    extracted = proc.stdout.decode("utf-8", errors="ignore")

    # Both collapsible accordion sections must be expanded and their inner fields included
    assert "Recipient's details" in extracted
    assert "Alex Morgan" in extracted
    assert "Germany" in extracted
    assert "Sender's details" in extracted
    assert "Jordan Taylor" in extracted


def test_locale_rendering_in_html(converter):
    """Test that specifying locale injects correct navigator.language and localStorage."""
    test_html = """
    <!DOCTYPE html>
    <html>
    <body>
        <div id="lang-val"></div>
        <div id="ls-val"></div>
        <script>
            document.getElementById('lang-val').textContent = 'NavLang: ' + navigator.language;
            document.getElementById('ls-val').textContent = 'LSCode: ' + (window.localStorage.getItem('LOCALE_CODE') || 'none');
        </script>
    </body>
    </html>
    """
    opts = PDFOptions(locale="en-US")
    pdf_bytes = converter.convert_html_string(test_html, options=opts)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")

    proc = subprocess.run(["pdftotext", "-", "-"], input=pdf_bytes, capture_output=True)
    extracted = proc.stdout.decode("utf-8", errors="ignore")
    assert "NavLang: en-US" in extracted
    assert "LSCode: en" in extracted


def test_mock_firefox_cookie_extraction():
    """Test extracting cookies from a mock Firefox profile database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_dir = Path(tmpdir)
        db_path = profile_dir / "cookies.sqlite"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE moz_cookies (
                id INTEGER PRIMARY KEY,
                originAttributes TEXT NOT NULL DEFAULT '',
                name TEXT,
                value TEXT,
                host TEXT,
                path TEXT,
                expiry INTEGER,
                lastAccessed INTEGER,
                creationTime INTEGER,
                isSecure INTEGER,
                isHttpOnly INTEGER,
                inBrowserElement INTEGER DEFAULT 0,
                sameSite INTEGER DEFAULT 0,
                rawSameSite INTEGER DEFAULT 0,
                schemeMap INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            INSERT INTO moz_cookies (name, value, host, path, isSecure, expiry)
            VALUES ('session_token', 'abc123xyz', '.example.com', '/', 1, 2000000000)
        """)
        conn.commit()
        conn.close()

        cookies = extract_firefox_cookies("https://app.example.com", profile_dir=profile_dir)
        assert len(cookies) == 1
        assert cookies[0]["name"] == "session_token"
        assert cookies[0]["value"] == "abc123xyz"
        assert cookies[0]["domain"] == ".example.com"


def test_mock_firefox_localstorage_extraction():
    """Test extracting localStorage key-values from a mock Firefox profile structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_dir = Path(tmpdir)
        ls_dir = profile_dir / "storage" / "default" / "https+++example.com" / "ls"
        ls_dir.mkdir(parents=True)
        db_path = ls_dir / "data.sqlite"

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE data (
                key TEXT PRIMARY KEY,
                utf16_length INTEGER NOT NULL,
                conversion_type INTEGER NOT NULL,
                compression_type INTEGER NOT NULL,
                last_access_time INTEGER NOT NULL DEFAULT 0,
                value BLOB NOT NULL
            )
        """)
        # Insert Latin1 uncompressed string (conversion_type=1, compression_type=0)
        cur.execute("""
            INSERT INTO data (key, utf16_length, conversion_type, compression_type, value)
            VALUES (?, ?, 1, 0, ?)
        """, (b"LOCALE_CODE", 2, b"en"))
        # Insert UTF-16LE uncompressed string (conversion_type=2, compression_type=0)
        cur.execute("""
            INSERT INTO data (key, utf16_length, conversion_type, compression_type, value)
            VALUES (?, ?, 2, 0, ?)
        """, (b"THEME", 4, "dark".encode("utf-16le")))
        conn.commit()
        conn.close()

        items = extract_firefox_localstorage("https://example.com/dashboard", profile_dir=profile_dir)
        assert items.get("LOCALE_CODE") == "en"
        assert items.get("THEME") == "dark"
