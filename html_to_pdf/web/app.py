"""FastAPI application providing Web UI and REST API for HTML to PDF conversion."""

import asyncio
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from html_to_pdf.config import MarginConfig, PDFOptions
from html_to_pdf.converter import HTMLToPDFConverter
from html_to_pdf.merger import merge_pdfs
from html_to_pdf.utils import find_system_chrome, is_url

# Paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="HTML to PDF Converter",
    description="High-fidelity HTML to PDF conversion service using headless Chromium",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
converter = HTMLToPDFConverter()

DEFAULT_SAMPLE_PATH = Path(__file__).resolve().parent.parent.parent / "examples" / "sample_receipt.html"
REFERENCE_FILE_PATH = os.getenv("HTML_TO_PDF_SAMPLE", str(DEFAULT_SAMPLE_PATH))



class URLConvertRequest(BaseModel):
    url: str
    format: Optional[str] = "A4"
    landscape: bool = False
    single_page: bool = False
    media_type: str = "screen"
    print_background: bool = True
    margin: str = "0mm"
    scale: float = 1.0
    wait_delay: int = 200
    viewport_width: int = 1280
    viewport_height: int = 900
    use_firefox_cookies: bool = True
    expand_collapsible: bool = True
    locale: Optional[str] = "en-US"


class FilePathConvertRequest(BaseModel):
    file_path: str
    format: Optional[str] = "A4"
    landscape: bool = False
    single_page: bool = False
    media_type: str = "screen"
    print_background: bool = True
    margin: str = "0mm"
    scale: float = 1.0
    wait_delay: int = 200
    viewport_width: int = 1280
    viewport_height: int = 900
    expand_collapsible: bool = True
    locale: Optional[str] = "en-US"


class HTMLContentConvertRequest(BaseModel):
    html_content: str
    format: Optional[str] = "A4"
    landscape: bool = False
    single_page: bool = False
    media_type: str = "screen"
    print_background: bool = True
    margin: str = "0mm"
    scale: float = 1.0
    wait_delay: int = 200
    viewport_width: int = 1280
    viewport_height: int = 900
    expand_collapsible: bool = True
    locale: Optional[str] = "en-US"


def build_options(
    format: Optional[str] = "A4",
    landscape: bool = False,
    single_page: bool = False,
    media_type: str = "screen",
    print_background: bool = True,
    margin_str: str = "0mm",
    scale: float = 1.0,
    wait_delay: int = 200,
    viewport_width: int = 1280,
    viewport_height: int = 900,
    use_firefox_cookies: bool = True,
    expand_collapsible: bool = True,
    locale: Optional[str] = "en-US",
) -> PDFOptions:
    margins = MarginConfig(
        top=margin_str,
        right=margin_str,
        bottom=margin_str,
        left=margin_str,
    )
    return PDFOptions(
        format=format,
        landscape=landscape,
        single_page=single_page,
        media_type="screen" if media_type == "screen" else "print",
        print_background=print_background,
        margin=margins,
        scale=scale,
        wait_delay=wait_delay,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        use_firefox_cookies=use_firefox_cookies,
        expand_collapsible=expand_collapsible,
        locale=locale,
    )


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Render the main conversion UI."""
    ref_exists = os.path.exists(REFERENCE_FILE_PATH)
    chrome_path = find_system_chrome()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "reference_file_path": REFERENCE_FILE_PATH,
            "reference_file_exists": ref_exists,
            "chrome_path": chrome_path or "Playwright Chromium",
        },
    )


@app.get("/api/health")
async def health_check():
    """Return system and converter status."""
    chrome_bin = find_system_chrome()
    ref_exists = os.path.exists(REFERENCE_FILE_PATH)
    return {
        "status": "healthy",
        "chrome_path": chrome_bin,
        "reference_file_exists": ref_exists,
        "reference_file": REFERENCE_FILE_PATH,
    }


@app.post("/api/convert/url")
async def api_convert_url(req: URLConvertRequest):
    """Convert a remote URL to PDF."""
    if not is_url(req.url):
        raise HTTPException(status_code=400, detail="Invalid web URL. Must start with http:// or https://")

    options = build_options(
        format=req.format,
        landscape=req.landscape,
        single_page=req.single_page,
        media_type=req.media_type,
        print_background=req.print_background,
        margin_str=req.margin,
        scale=req.scale,
        wait_delay=req.wait_delay,
        viewport_width=req.viewport_width,
        viewport_height=req.viewport_height,
        use_firefox_cookies=req.use_firefox_cookies,
        expand_collapsible=req.expand_collapsible,
        locale=req.locale,
    )

    t0 = time.time()
    try:
        pdf_bytes = await asyncio.to_thread(converter.convert_url, req.url, options=options)
        elapsed = time.time() - t0
        filename = "document.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Conversion-Time": f"{elapsed:.3f}s",
                "X-PDF-Size": str(len(pdf_bytes)),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/convert/path")
async def api_convert_path(req: FilePathConvertRequest):
    """Convert an existing local server file path to PDF."""
    path = os.path.abspath(os.path.expanduser(req.file_path))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found on system: {path}")

    options = build_options(
        format=req.format,
        landscape=req.landscape,
        single_page=req.single_page,
        media_type=req.media_type,
        print_background=req.print_background,
        margin_str=req.margin,
        scale=req.scale,
        wait_delay=req.wait_delay,
        viewport_width=req.viewport_width,
        viewport_height=req.viewport_height,
        expand_collapsible=req.expand_collapsible,
        locale=req.locale,
    )

    t0 = time.time()
    try:
        pdf_bytes = await asyncio.to_thread(converter.convert_file, path, options=options)
        elapsed = time.time() - t0
        out_name = Path(path).stem + ".pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{out_name}"',
                "X-Conversion-Time": f"{elapsed:.3f}s",
                "X-PDF-Size": str(len(pdf_bytes)),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/convert/upload")
async def api_convert_upload(
    file: UploadFile = File(...),
    format: str = Form("A4"),
    landscape: bool = Form(False),
    single_page: bool = Form(False),
    media_type: str = Form("screen"),
    print_background: bool = Form(True),
    margin: str = Form("0mm"),
    scale: float = Form(1.0),
    wait_delay: int = Form(200),
    viewport_width: int = Form(1280),
    viewport_height: int = Form(900),
    expand_collapsible: bool = Form(True),
    locale: str = Form("en-US"),
):
    """Convert an uploaded HTML file to PDF."""
    options = build_options(
        format=format,
        landscape=landscape,
        single_page=single_page,
        media_type=media_type,
        print_background=print_background,
        margin_str=margin,
        scale=scale,
        wait_delay=wait_delay,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        expand_collapsible=expand_collapsible,
        locale=locale,
    )

    t0 = time.time()
    temp_dir = tempfile.mkdtemp(prefix="htmltopdf_upload_")
    try:
        temp_file_path = os.path.join(temp_dir, file.filename or "upload.html")
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        pdf_bytes = await asyncio.to_thread(converter.convert_file, temp_file_path, options=options)
        elapsed = time.time() - t0
        out_name = Path(file.filename or "document").stem + ".pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{out_name}"',
                "X-Conversion-Time": f"{elapsed:.3f}s",
                "X-PDF-Size": str(len(pdf_bytes)),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/api/convert/html")
async def api_convert_html(req: HTMLContentConvertRequest):
    """Convert raw HTML content string to PDF."""
    if not req.html_content.strip():
        raise HTTPException(status_code=400, detail="HTML content cannot be empty")

    options = build_options(
        format=req.format,
        landscape=req.landscape,
        single_page=req.single_page,
        media_type=req.media_type,
        print_background=req.print_background,
        margin_str=req.margin,
        scale=req.scale,
        wait_delay=req.wait_delay,
        viewport_width=req.viewport_width,
        viewport_height=req.viewport_height,
        expand_collapsible=req.expand_collapsible,
        locale=req.locale,
    )

    t0 = time.time()
    try:
        pdf_bytes = await asyncio.to_thread(converter.convert_html_string, req.html_content, options=options)
        elapsed = time.time() - t0
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'inline; filename="rendered.pdf"',
                "X-Conversion-Time": f"{elapsed:.3f}s",
                "X-PDF-Size": str(len(pdf_bytes)),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PDFMergeRequest(BaseModel):
    files: list[str]
    output_filename: Optional[str] = "merged.pdf"


@app.post("/api/pdf/merge")
async def api_merge_paths(req: PDFMergeRequest):
    """Merge an ordered list of server PDF file paths into a single PDF in predetermined order."""
    if not req.files:
        raise HTTPException(status_code=400, detail="List of PDF files is required")

    t0 = time.time()
    try:
        merged_bytes = await asyncio.to_thread(merge_pdfs, req.files)
        elapsed = time.time() - t0
        filename = req.output_filename or "merged.pdf"
        if not filename.endswith(".pdf"):
            filename += ".pdf"
        return Response(
            content=merged_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Conversion-Time": f"{elapsed:.3f}s",
                "X-PDF-Size": str(len(merged_bytes)),
            },
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/merge-uploads")
async def api_merge_uploads(
    files: list[UploadFile] = File(...),
    output_filename: str = Form("merged.pdf"),
):
    """Merge multiple uploaded PDF files in the exact order received."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded to merge")

    t0 = time.time()
    try:
        file_bytes_list = []
        for f in files:
            content = await f.read()
            file_bytes_list.append(content)

        merged_bytes = await asyncio.to_thread(merge_pdfs, file_bytes_list)
        elapsed = time.time() - t0
        filename = output_filename or "merged.pdf"
        if not filename.endswith(".pdf"):
            filename += ".pdf"
        return Response(
            content=merged_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Conversion-Time": f"{elapsed:.3f}s",
                "X-PDF-Size": str(len(merged_bytes)),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

