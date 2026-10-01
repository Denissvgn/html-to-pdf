"""Command-line interface for HTML to PDF converter."""

import argparse
import sys
import time
from pathlib import Path

from html_to_pdf.config import PDFOptions, MarginConfig
from html_to_pdf.converter import HTMLToPDFConverter
from html_to_pdf.utils import is_url


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="html-to-pdf",
        description="Convert HTML files (with companion assets) or web URLs to PDF with high fidelity.",
    )
    parser.add_argument(
        "source",
        help="Source HTML file path or web URL (http:// or https://)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Path for output PDF file (defaults to <source_name>.pdf or output.pdf)",
    )
    parser.add_argument(
        "-f", "--format",
        default="A4",
        choices=["A0", "A1", "A2", "A3", "A4", "A5", "A6", "Letter", "Legal", "Tabloid", "Ledger"],
        help="Standard paper format (default: A4)",
    )
    parser.add_argument(
        "-l", "--landscape",
        action="store_true",
        help="Use landscape orientation instead of portrait",
    )
    parser.add_argument(
        "--single-page",
        action="store_true",
        help="Generate a continuous single-page PDF fitting full content height (ideal for receipts/dashboards)",
    )
    parser.add_argument(
        "-m", "--media",
        choices=["screen", "print"],
        default="screen",
        help="CSS media emulation: 'screen' (browser look) or 'print' (@media print styles) (default: screen)",
    )
    parser.add_argument(
        "--no-background",
        action="store_true",
        help="Disable printing background graphics and colors",
    )
    parser.add_argument(
        "--margin",
        default="0mm",
        help="Uniform margin size, e.g. '0mm', '10mm', '0.5in' (default: 0mm)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor for rendering, 0.1 to 2.0 (default: 1.0)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=200,
        help="Additional delay in milliseconds after page load to allow dynamic scripts/fonts to finish (default: 200)",
    )
    parser.add_argument(
        "--viewport-width",
        type=int,
        default=1280,
        help="Browser viewport width (default: 1280)",
    )
    parser.add_argument(
        "--viewport-height",
        type=int,
        default=900,
        help="Browser viewport height (default: 900)",
    )
    parser.add_argument(
        "--from-firefox",
        dest="use_firefox",
        action="store_true",
        default=True,
        help="Automatically import session cookies from local Firefox for authenticated web pages (default: True)",
    )
    parser.add_argument(
        "--no-firefox",
        dest="use_firefox",
        action="store_false",
        help="Do not import Firefox cookies",
    )
    parser.add_argument(
        "--expand-collapsible",
        dest="expand_collapsible",
        action="store_true",
        default=True,
        help="Automatically expand all collapsible menus, accordions, and details tags (default: True)",
    )
    parser.add_argument(
        "--no-expand",
        dest="expand_collapsible",
        action="store_false",
        help="Do not auto-expand collapsible menus",
    )
    parser.add_argument(
        "--locale",
        default="en-US",
        help="Language/locale for rendering and Accept-Language header (e.g., 'en-US', 'en', 'ru') (default: en-US)",
    )
    return parser


def determine_default_output(source: str) -> str:
    if is_url(source):
        # Generate safe name from domain/path
        clean = source.replace("https://", "").replace("http://", "").strip("/")
        base = clean.split("/")[0].replace(":", "_")
        return f"{base}.pdf"
    
    path = Path(source)
    return str(path.with_suffix(".pdf").name)


def main(args: list[str] = None) -> int:
    if args is None:
        args = sys.argv[1:]

    if args and args[0] in ("merge", "glue", "concat"):
        from html_to_pdf.merger import main as merger_main
        return merger_main(args[1:])

    parser = create_parser()
    parsed_args = parser.parse_args(args)

    output_path = parsed_args.output or determine_default_output(parsed_args.source)

    margins = MarginConfig(
        top=parsed_args.margin,
        right=parsed_args.margin,
        bottom=parsed_args.margin,
        left=parsed_args.margin,
    )

    options = PDFOptions(
        format=parsed_args.format,
        landscape=parsed_args.landscape,
        single_page=parsed_args.single_page,
        media_type=parsed_args.media,
        print_background=not parsed_args.no_background,
        margin=margins,
        scale=parsed_args.scale,
        wait_delay=parsed_args.delay,
        viewport_width=parsed_args.viewport_width,
        viewport_height=parsed_args.viewport_height,
        use_firefox_cookies=parsed_args.use_firefox,
        expand_collapsible=parsed_args.expand_collapsible,
        locale=parsed_args.locale,
    )

    print(f"[*] Converting: {parsed_args.source}")
    print(f"[*] Output destination: {output_path}")
    print(f"[*] Mode: media={options.media_type}, format={options.format}, single_page={options.single_page}")

    start_time = time.time()
    try:
        converter = HTMLToPDFConverter()
        pdf_bytes = converter.convert_source(parsed_args.source, output_path=output_path, options=options)
        elapsed = time.time() - start_time
        size_kb = len(pdf_bytes) / 1024
        print(f"[✓] Successfully generated PDF: {output_path} ({size_kb:.1f} KB in {elapsed:.2f}s)")
        return 0
    except Exception as e:
        print(f"[✗] Error during conversion: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
