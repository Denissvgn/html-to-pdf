#!/usr/bin/env python3
"""Run script for HTML to PDF Studio web application."""

import argparse
import sys
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Start the HTML to PDF web application")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable automatic reloading on code changes")
    args = parser.parse_args()

    print(f"==================================================")
    print(f"  Starting HTML to PDF Converter Studio")
    print(f"  URL: http://{args.host}:{args.port}")
    print(f"  API Docs: http://{args.host}:{args.port}/docs")
    print(f"==================================================")

    uvicorn.run(
        "html_to_pdf.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
