"""HTML to PDF Converter package."""

from html_to_pdf.config import PDFOptions, MarginConfig
from html_to_pdf.converter import (
    HTMLToPDFConverter,
    convert_source,
    convert_file,
    convert_url,
    convert_html_string,
)

from html_to_pdf.merger import merge_pdfs

__all__ = [
    "HTMLToPDFConverter",
    "PDFOptions",
    "MarginConfig",
    "convert_source",
    "convert_file",
    "convert_url",
    "convert_html_string",
    "merge_pdfs",
]

__version__ = "1.0.0"

