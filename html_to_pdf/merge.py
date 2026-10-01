"""Alias entrypoint for html_to_pdf.merger."""
import sys
from html_to_pdf.merger import main, merge_pdfs

__all__ = ["main", "merge_pdfs"]

if __name__ == "__main__":
    sys.exit(main())
