"""PDF Merging engine to glue multiple PDF documents into a single document in predetermined order."""

import argparse
import io
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence, Union

try:
    from pypdf import PdfWriter, PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


def merge_pdfs(
    pdf_inputs: Sequence[Union[str, Path, bytes, io.BytesIO]],
    output_path: Optional[Union[str, Path]] = None,
) -> bytes:
    """
    Merge multiple PDF files or PDF byte arrays into a single PDF in the exact predetermined order.

    :param pdf_inputs: Ordered sequence of file paths (str/Path) or raw PDF bytes/ByteIO streams.
    :param output_path: Optional destination path to write the merged PDF.
    :return: Merged PDF document bytes.
    """
    if not pdf_inputs:
        raise ValueError("At least one PDF input is required to merge.")

    if not PYPDF_AVAILABLE:
        # Fallback to pdfunite if available on system
        return _merge_with_pdfunite(pdf_inputs, output_path)

    writer = PdfWriter()
    temp_handles = []

    try:
        for idx, item in enumerate(pdf_inputs, start=1):
            if isinstance(item, (str, Path)):
                path = Path(item).resolve()
                if not path.is_file():
                    raise FileNotFoundError(f"PDF file #{idx} not found: {path}")
                f = open(path, "rb")
                temp_handles.append(f)
                writer.append(f)
            elif isinstance(item, (bytes, bytearray)):
                buf = io.BytesIO(item)
                writer.append(buf)
            elif isinstance(item, io.BytesIO):
                writer.append(item)
            else:
                raise TypeError(f"Unsupported input type for item #{idx}: {type(item)}")

        out_buffer = io.BytesIO()
        writer.write(out_buffer)
        merged_bytes = out_buffer.getvalue()

        if output_path:
            out_file = Path(output_path).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "wb") as f:
                f.write(merged_bytes)

        return merged_bytes
    finally:
        for f in temp_handles:
            try:
                f.close()
            except Exception:
                pass
        writer.close()


def _merge_with_pdfunite(
    pdf_inputs: Sequence[Union[str, Path, bytes, io.BytesIO]],
    output_path: Optional[Union[str, Path]] = None,
) -> bytes:
    """Fallback merging using system /usr/bin/pdfunite."""
    import subprocess
    import tempfile

    temp_files = []
    try:
        cmd = ["pdfunite"]
        for idx, item in enumerate(pdf_inputs, start=1):
            if isinstance(item, (str, Path)):
                path = Path(item).resolve()
                if not path.is_file():
                    raise FileNotFoundError(f"PDF file #{idx} not found: {path}")
                cmd.append(str(path))
            else:
                tf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                if isinstance(item, (bytes, bytearray)):
                    tf.write(item)
                elif isinstance(item, io.BytesIO):
                    tf.write(item.getvalue())
                tf.close()
                temp_files.append(tf.name)
                cmd.append(tf.name)

        target_out = output_path or tempfile.mktemp(suffix=".pdf")
        cmd.append(str(target_out))

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"pdfunite failed: {result.stderr}")

        with open(target_out, "rb") as f:
            data = f.read()

        if not output_path and os.path.exists(target_out):
            os.remove(target_out)

        return data
    finally:
        for tf in temp_files:
            if os.path.exists(tf):
                os.remove(tf)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-merge",
        description="Glue multiple PDF documents into a single PDF in predetermined order.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 1. Merge files specified directly on command line in predetermined order:
  python -m html_to_pdf.merger -o combined.pdf 9561489400.pdf 9561897100.pdf 9561900700.pdf

  # 2. Merge from an ordered text file listing paths (one per line):
  python -m html_to_pdf.merger -o all_receipts.pdf --file-list receipts.txt

  # 3. Read ordered list of files from standard input:
  ls -1v 956*.pdf | python -m html_to_pdf.merger -o combined.pdf -
        """,
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="PDF file paths in predetermined order (use '-' to read from standard input)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Destination output PDF file path",
    )
    parser.add_argument(
        "-l",
        "--file-list",
        help="Path to text file containing PDF file paths in predetermined order (one per line)",
    )
    return parser


def main(args: Optional[List[str]] = None) -> int:
    parser = create_parser()
    parsed = parser.parse_args(args)

    input_paths: List[str] = []

    # Read from file list if provided
    if parsed.file_list:
        list_file = Path(parsed.file_list).resolve()
        if not list_file.is_file():
            print(f"[!] Error: File list '{list_file}' not found.", file=sys.stderr)
            return 1
        with open(list_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    input_paths.append(stripped)

    # Process positional files
    for item in parsed.files:
        if item == "-":
            # Read paths from stdin
            for line in sys.stdin:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    input_paths.append(stripped)
        else:
            input_paths.append(item)

    if not input_paths:
        print("[!] Error: No input PDF files provided to merge.", file=sys.stderr)
        parser.print_help(sys.stderr)
        return 1

    print(f"[*] Gluing {len(input_paths)} PDF files into: {parsed.output}")
    for idx, path in enumerate(input_paths, start=1):
        print(f"    {idx}. {path}")

    t0 = time.time()
    try:
        merged_bytes = merge_pdfs(input_paths, output_path=parsed.output)
        elapsed = time.time() - t0
        size_kb = len(merged_bytes) / 1024
        print(f"[✓] Successfully glued {len(input_paths)} PDFs into '{parsed.output}' ({size_kb:.1f} KB in {elapsed:.2f}s)")
        return 0
    except Exception as e:
        print(f"[!] Error merging PDFs: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
