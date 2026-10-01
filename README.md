# HTML to PDF Converter Studio

[![CI](https://github.com/Denissvgn/html-to-pdf/actions/workflows/ci.yml/badge.svg)](https://github.com/Denissvgn/html-to-pdf/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

A high-fidelity HTML-to-PDF conversion service, Python library, and CLI suite powered by Chromium and Playwright. Converts local HTML documents (including companion asset folders such as `_files`), live web pages, and raw HTML strings into pixel-perfect PDF documents. Includes an ordered PDF merger utility, session synchronization for authenticated web apps, and an interactive FastAPI Web Studio.

---

## Features

- **Reference-Grade Rendering Fidelity**: Uses headless Google Chrome/Chromium to render exact typography, CSS Grid, Flexbox, SVG vectors, and modern CSS custom properties (`var(--...)`).
- **Local Files & Web URLs**:
  - Convert any local `.html` file with its accompanying asset folders (e.g., `document.html` and `document_files/`).
  - Convert live web addresses (`https://...` or `http://...`).
  - Convert raw HTML strings directly in Python or via REST API.
- **Continuous Single-Page Mode**: Ideal for receipts, invoices, transaction summaries, and dashboards without awkward page-break splits.
- **Smart Collapsible Menu Expansion**: Automatically detects and expands all accordion sections, HTML5 `<details>`, WAI-ARIA `[aria-expanded="false"]` controls, and SVG chevron headers, ensuring hidden content is revealed in the exported PDF.
- **Firefox Session Sync**: Automatically imports cookies from active Firefox profiles (Snap, native `.mozilla`, Flatpak) to export authenticated user dashboards and receipts without re-authenticating.
- **Ordered PDF Merger**: Merge multiple PDF documents while strictly preserving a predetermined sequence via CLI arguments, text file lists, stdin pipes, or API endpoints.
- **Media Emulation**: Emulate `screen` (preserving browser styling and colors) or `print` (applying document print CSS).
- **Backgrounds & Sizing**: Full control over paper formats (`A4`, `Letter`, `Legal`, `Tabloid`, `A3`, `A5`), custom dimensions, margins, scale, and background graphics.
- **Interactive Web Studio**: Clean, responsive browser interface with instant PDF preview and 1-click download.
- **Full REST API**: Integrated FastAPI endpoints for automated workflows and integrations.
- **Command-Line Interface (CLI)**: Fast CLI tools (`html-to-pdf` and `pdf-merge`) for scripting and terminal operations.

---

## Installation

### Prerequisites
- Python 3.9 or higher
- System dependencies (such as Chromium dependencies and poppler-utils if using PDF tools)

### 1. Clone the repository
```bash
git clone https://github.com/Denissvgn/html-to-pdf.git
cd html-to-pdf
```

### 2. Set up a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install packages & Playwright browser
```bash
pip install -r requirements.txt
playwright install chromium
```

---

## Quick Usage

### 1. Web Application Studio

Start the web studio:
```bash
python run.py
# or with custom port/host:
python run.py --host 0.0.0.0 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
Interactive OpenAPI docs are available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

### 2. Command-Line Interface (CLI)

#### Convert Local HTML File
```bash
# Standard A4 multi-page
html-to-pdf html_to_pdf/examples/sample_receipt.html -o receipt.pdf

# Single continuous page (ideal for receipt or invoice layout)
html-to-pdf html_to_pdf/examples/sample_receipt.html -o receipt_single.pdf --single-page
```

#### Convert Authenticated Web Page
When converting authenticated or logged-in pages, the tool can automatically import your active Firefox session cookies:
```bash
# Uses Firefox cookies automatically (default: --from-firefox)
html-to-pdf "https://example.com/dashboard/receipt/12345" -o receipt.pdf --single-page

# Explicitly disable session import:
html-to-pdf "https://example.com/receipt/12345" -o receipt.pdf --no-firefox
```

#### Convert Public Web URL
```bash
html-to-pdf "https://news.ycombinator.com" -o hackernews.pdf --format A4 --media screen
```

#### Auto-Expand Collapsible Sections
By default, `--expand-collapsible` is enabled:
```bash
# Expands all collapsible accordions (like recipient & sender info):
html-to-pdf html_to_pdf/examples/sample_receipt.html -o receipt_expanded.pdf --single-page

# Or keep sections in their original collapsed state:
html-to-pdf html_to_pdf/examples/sample_receipt.html -o receipt_collapsed.pdf --no-expand
```

#### Language / Locale Selection
Export pages in your preferred language (e.g. English `en-US` or other locales). Automatically synchronizes with Firefox `localStorage` language settings and sets browser locale and `Accept-Language` headers:
```bash
# Export in English (default):
html-to-pdf "https://example.com/receipt/12345" -o receipt_en.pdf --single-page --locale en-US

# Export in German:
html-to-pdf "https://example.com/receipt/12345" -o receipt_de.pdf --single-page --locale de-DE
```

#### CLI Options
```
usage: html-to-pdf [-h] [-o OUTPUT] [-f {A0..A6,Letter,Legal,Tabloid,Ledger}]
                   [-l] [--single-page] [-m {screen,print}] [--no-background]
                   [--margin MARGIN] [--scale SCALE] [--delay DELAY]
                   [--from-firefox | --no-firefox]
                   [--expand-collapsible | --no-expand]
                   [--locale LOCALE]
                   [--viewport-width VIEWPORT_WIDTH] [--viewport-height VIEWPORT_HEIGHT]
                   source
```

---

### 3. Merging PDFs in Predetermined Order

Merge multiple PDF documents into a single document while strictly preserving your exact sequence:

#### Method A: Direct file list in command
```bash
# Using dedicated pdf-merge tool:
pdf-merge -o combined_invoices.pdf invoice_01.pdf invoice_02.pdf invoice_03.pdf

# Or using the sub-command:
html-to-pdf merge -o combined_invoices.pdf invoice_01.pdf invoice_02.pdf invoice_03.pdf
```

#### Method B: Ordered text file list
Create a text file (e.g. `order.txt`) with one file path per line in your desired order:
```text
invoice_01.pdf
invoice_02.pdf
invoice_03.pdf
```
Then run:
```bash
pdf-merge -o combined_invoices.pdf --file-list order.txt
```

#### Method C: Pipe from standard input (stdin)
```bash
ls -1v invoice_*.pdf | pdf-merge -o combined_invoices.pdf -
```

---

### 4. Python Library Usage

```python
from html_to_pdf import HTMLToPDFConverter, PDFOptions, convert_file, convert_url, merge_pdfs

# 1. Convert local file
convert_file("html_to_pdf/examples/sample_receipt.html", output_path="receipt.pdf")

# 2. Convert URL with custom options
options = PDFOptions(
    format="A4",
    single_page=True,
    media_type="screen",
    print_background=True,
    use_firefox_cookies=True,
    expand_collapsible=True,
    scale=1.0,
    wait_delay=500,
    locale="en-US"
)

converter = HTMLToPDFConverter()
pdf_bytes = converter.convert_url("https://example.com/receipt/12345", options=options)

# 3. Glue multiple PDFs in predetermined order
merge_pdfs(
    ["invoice_01.pdf", "invoice_02.pdf", "invoice_03.pdf"],
    output_path="all_invoices.pdf"
)
```

---

## REST API Endpoints

- `POST /api/convert/path`: Convert local file path on server.
  ```json
  {
    "file_path": "html_to_pdf/examples/sample_receipt.html",
    "format": "A4",
    "single_page": true,
    "media_type": "screen"
  }
  ```
- `POST /api/convert/url`: Convert public or intranet URL.
  ```json
  {
    "url": "https://example.com/invoice/12345",
    "format": "Letter"
  }
  ```
- `POST /api/convert/upload`: Multipart upload of `.html` file.
- `POST /api/convert/html`: Convert raw HTML string.
- `POST /api/merge`: Merge multiple uploaded PDF files in specified order.
- `GET /api/health`: Health status and detected Chrome/Chromium binary.

---

## Testing

Run the automated test suite with pytest:
```bash
pytest -v
```

---

## License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.

Author: [Denis Sivagin](https://github.com/Denissvgn)
