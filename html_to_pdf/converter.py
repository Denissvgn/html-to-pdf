import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

from playwright.sync_api import sync_playwright, Page

from html_to_pdf.config import PDFOptions
from html_to_pdf.cookies import extract_firefox_cookies, extract_firefox_localstorage
from html_to_pdf.utils import normalize_source, find_system_chrome


class HTMLToPDFConverter:
    """High-fidelity HTML to PDF converter using headless Chromium."""

    def __init__(self, chrome_path: Optional[str] = None):
        self.chrome_path = chrome_path or find_system_chrome()

    def _get_launch_args(self) -> list[str]:
        return [
            "--allow-file-access-from-files",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--font-render-hinting=medium",
        ]

    def convert_source(
        self,
        source: str,
        output_path: Optional[Union[str, Path]] = None,
        options: Optional[PDFOptions] = None,
    ) -> bytes:
        """
        Convert a source (local HTML file path or web URL) to PDF.
        """
        normalized_url, _ = normalize_source(source)
        return self._render_url_to_pdf(normalized_url, output_path=output_path, options=options)

    def convert_file(
        self,
        file_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        options: Optional[PDFOptions] = None,
    ) -> bytes:
        """
        Convert a local HTML file to PDF.
        """
        return self.convert_source(str(file_path), output_path=output_path, options=options)

    def convert_url(
        self,
        url: str,
        output_path: Optional[Union[str, Path]] = None,
        options: Optional[PDFOptions] = None,
    ) -> bytes:
        """
        Convert a remote web address (http:// or https://) to PDF.
        """
        return self.convert_source(url, output_path=output_path, options=options)

    def convert_html_string(
        self,
        html_content: str,
        output_path: Optional[Union[str, Path]] = None,
        options: Optional[PDFOptions] = None,
        base_dir: Optional[Union[str, Path]] = None,
    ) -> bytes:
        """
        Convert raw HTML string to PDF. If base_dir is given, temporary file is placed there
        to allow relative assets to resolve.
        """
        target_dir = str(base_dir) if base_dir and os.path.isdir(str(base_dir)) else None
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, dir=target_dir, mode="w", encoding="utf-8") as f:
            f.write(html_content)
            temp_path = f.name

        try:
            return self.convert_file(temp_path, output_path=output_path, options=options)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _render_url_to_pdf(
        self,
        url: str,
        output_path: Optional[Union[str, Path]] = None,
        options: Optional[PDFOptions] = None,
    ) -> bytes:
        """Internal helper to navigate and generate PDF with Playwright."""
        opts = options or PDFOptions()

        launch_kwargs = {
            "headless": True,
            "args": self._get_launch_args(),
        }
        if self.chrome_path:
            launch_kwargs["executable_path"] = self.chrome_path

        is_remote = url.startswith("http://") or url.startswith("https://")

        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            try:
                target_locale = opts.locale or "en-US"
                context_kwargs = {
                    "viewport": {"width": opts.viewport_width, "height": opts.viewport_height},
                    "device_scale_factor": 1,
                    "bypass_csp": True,
                    "ignore_https_errors": True,
                    "locale": target_locale,
                    "extra_http_headers": {
                        "Accept-Language": f"{target_locale},{target_locale.split('-')[0]};q=0.9,en;q=0.8"
                    },
                }
                if is_remote:
                    context_kwargs["user_agent"] = (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
                    )

                context = browser.new_context(**context_kwargs)

                # Cookie and session storage sync
                ff_ls = {}
                if is_remote:
                    if opts.cookies:
                        context.add_cookies(opts.cookies)
                    if opts.use_firefox_cookies:
                        ff_cookies = extract_firefox_cookies(url)
                        if ff_cookies:
                            context.add_cookies(ff_cookies)
                        ff_ls = extract_firefox_localstorage(url)

                # Inject localStorage items & language preferences into client-side JS environment
                short_loc = target_locale.split("-")[0].lower()
                init_js = f"""
                try {{
                    const items = {json.dumps(ff_ls)};
                    for (const [k, v] of Object.entries(items)) {{
                        try {{ window.localStorage.setItem(k, v); }} catch(e) {{}}
                    }}
                    window.localStorage.setItem('LOCALE_CODE', {json.dumps(short_loc)});
                    window.localStorage.setItem('locale', {json.dumps(short_loc)});
                }} catch (e) {{}}
                """
                context.add_init_script(init_js)

                page = context.new_page()

                # Navigate with graceful timeout fallback
                if is_remote:
                    # For remote URLs, load base document first, then optionally wait for networkidle
                    try:
                        page.goto(url, wait_until="load", timeout=20000)
                        if opts.wait_until == "networkidle":
                            try:
                                page.wait_for_load_state("networkidle", timeout=6000)
                            except Exception:
                                pass
                    except Exception:
                        page.goto(url, wait_until="domcontentloaded", timeout=15000)
                else:
                    try:
                        page.goto(url, wait_until=opts.wait_until, timeout=30000)
                    except Exception as e:
                        if opts.wait_until == "networkidle":
                            page.wait_for_load_state("domcontentloaded", timeout=10000)
                        else:
                            raise e

                # Media emulation (screen retains colors, flexbox, shadows; print applies @media print)
                page.emulate_media(media=opts.media_type)

                # Custom CSS injection
                if opts.custom_css:
                    page.add_style_tag(content=opts.custom_css)

                # Optional wait delay for SPA rendering / animations / charts
                delay_ms = opts.wait_delay
                if is_remote and delay_ms < 1000:
                    delay_ms = 1500  # Ensure SPAs (React/Next/Vue) complete mounting
                if delay_ms > 0:
                    page.wait_for_timeout(delay_ms)

                # Expand collapsible menus, accordions, and unconstrain scroll containers
                if opts.expand_collapsible:
                    try:
                        page.evaluate("""() => {
                            // 1. Native HTML5 details
                            document.querySelectorAll("details:not([open])").forEach(d => {
                                d.open = true;
                                d.setAttribute("open", "");
                            });

                            // 2. WAI-ARIA aria-expanded=false
                            document.querySelectorAll('[aria-expanded="false"]').forEach(el => {
                                if (el.tagName !== "A" && !el.closest("a") && el.getAttribute("role") !== "dialog") {
                                    try { el.click(); } catch(e) {}
                                }
                            });

                            // 3. Common accordion buttons (Bootstrap / Tailwind)
                            document.querySelectorAll('.accordion-button.collapsed, [data-toggle="collapse"].collapsed, [data-bs-toggle="collapse"].collapsed').forEach(el => {
                                if (el.tagName !== "A" && !el.closest("a")) {
                                    try { el.click(); } catch(e) {}
                                }
                            });

                            // 4. In-page accordion headers with chevrons (e.g. payment portals & receipts)
                            document.querySelectorAll(".cursor-pointer").forEach(el => {
                                const svg = el.querySelector("svg");
                                if (!svg) return;
                                const svgClass = (svg.getAttribute("class") || "").toLowerCase();
                                const svgName = (svg.getAttribute("data-sentry-component") || "").toLowerCase();
                                if (svgName.includes("chevron") || svgClass.includes("chevron") || svgClass.includes("scale-y-[-1]")) {
                                    const text = el.innerText || "";
                                    if (text.includes("Назад") || text.includes("Back") || text.includes("Поддержка") || text.includes("Support")) {
                                        return;
                                    }
                                    try { el.click(); } catch(e) {}
                                }
                            });
                        }""")
                        page.wait_for_timeout(600)

                        # Unconstrain scroll containers and hide floating chat widgets
                        expansion_css = """
                            html, body, #root, [class*="h-screen"], [class*="overflow-hidden"], [class*="overflow-y-auto"], #PAGE_CONTENT_ID {
                                overflow: visible !important;
                                height: auto !important;
                                max-height: none !important;
                            }
                            .transition-all, .collapse, [class*="max-h-"] {
                                max-height: none !important;
                                height: auto !important;
                                opacity: 1 !important;
                                visibility: visible !important;
                                overflow: visible !important;
                            }
                            [class*="chat"], [id*="chat"], button[class*="fixed"] {
                                display: none !important;
                            }
                        """
                        page.add_style_tag(content=expansion_css)
                        page.wait_for_timeout(300)
                    except Exception as e:
                        # Log error without failing whole conversion
                        pass

                # Configure PDF parameters
                pdf_kwargs = {
                    "print_background": opts.print_background,
                    "landscape": opts.landscape,
                    "scale": opts.scale,
                }

                if opts.margin:
                    pdf_kwargs["margin"] = {
                        "top": opts.margin.top,
                        "right": opts.margin.right,
                        "bottom": opts.margin.bottom,
                        "left": opts.margin.left,
                    }

                if opts.page_ranges:
                    pdf_kwargs["page_ranges"] = opts.page_ranges

                if opts.display_header_footer:
                    pdf_kwargs["display_header_footer"] = True
                    if opts.header_template:
                        pdf_kwargs["header_template"] = opts.header_template
                    if opts.footer_template:
                        pdf_kwargs["footer_template"] = opts.footer_template

                if opts.single_page:
                    # Calculate total document scroll height to generate a continuous 1-page PDF
                    scroll_height = page.evaluate("""() => {
                        let maxH = 0;
                        document.querySelectorAll("*").forEach(el => {
                            const rect = el.getBoundingClientRect();
                            const bottom = rect.bottom + window.scrollY;
                            if (bottom > maxH) maxH = bottom;
                        });
                        return Math.max(maxH, document.body.scrollHeight, document.documentElement.scrollHeight);
                    }""")
                    pdf_kwargs["width"] = opts.width or f"{opts.viewport_width}px"
                    pdf_kwargs["height"] = f"{int(scroll_height) + 40}px"
                else:
                    if opts.width and opts.height:
                        pdf_kwargs["width"] = opts.width
                        pdf_kwargs["height"] = opts.height
                    else:
                        pdf_kwargs["format"] = opts.format or "A4"

                pdf_bytes = page.pdf(**pdf_kwargs)

                if output_path:
                    out = Path(output_path)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(pdf_bytes)

                return pdf_bytes
            finally:
                browser.close()


# Module-level convenience functions
def convert_source(source: str, output_path: Optional[Union[str, Path]] = None, options: Optional[PDFOptions] = None) -> bytes:
    """Convenience function to convert a file or URL to PDF."""
    return HTMLToPDFConverter().convert_source(source, output_path=output_path, options=options)


def convert_file(file_path: Union[str, Path], output_path: Optional[Union[str, Path]] = None, options: Optional[PDFOptions] = None) -> bytes:
    """Convenience function to convert an HTML file to PDF."""
    return HTMLToPDFConverter().convert_file(file_path, output_path=output_path, options=options)


def convert_url(url: str, output_path: Optional[Union[str, Path]] = None, options: Optional[PDFOptions] = None) -> bytes:
    """Convenience function to convert a web URL to PDF."""
    return HTMLToPDFConverter().convert_url(url, output_path=output_path, options=options)


def convert_html_string(html_content: str, output_path: Optional[Union[str, Path]] = None, options: Optional[PDFOptions] = None) -> bytes:
    """Convenience function to convert raw HTML string to PDF."""
    return HTMLToPDFConverter().convert_html_string(html_content, output_path=output_path, options=options)
