"""Configuration and options models for HTML to PDF conversion."""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class MarginConfig(BaseModel):
    """Page margins in CSS units (px, in, cm, mm)."""
    top: str = "0mm"
    right: str = "0mm"
    bottom: str = "0mm"
    left: str = "0mm"

    @classmethod
    def default_margins(cls) -> "MarginConfig":
        return cls(top="10mm", right="10mm", bottom="10mm", left="10mm")

    @classmethod
    def no_margins(cls) -> "MarginConfig":
        return cls(top="0mm", right="0mm", bottom="0mm", left="0mm")

    @classmethod
    def normal_margins(cls) -> "MarginConfig":
        return cls(top="15mm", right="15mm", bottom="15mm", left="15mm")


class PDFOptions(BaseModel):
    """Options for PDF generation."""
    # Standard format: 'Letter', 'Legal', 'Tabloid', 'Ledger', 'A0', 'A1', 'A2', 'A3', 'A4', 'A5', 'A6'
    format: Optional[str] = Field(default="A4", description="Standard paper format")
    
    # Custom dimensions (used if format is not specified or single_page is True)
    width: Optional[str] = Field(default=None, description="Custom width (e.g. '800px', '210mm')")
    height: Optional[str] = Field(default=None, description="Custom height (e.g. '1200px', '297mm')")
    
    landscape: bool = Field(default=False, description="Orientation: True for landscape, False for portrait")
    print_background: bool = Field(default=True, description="Whether to print background graphics and colors")
    
    # Media emulation: 'screen' preserves exact styling as viewed in browser, 'print' applies @media print
    media_type: Literal["screen", "print"] = Field(
        default="screen", 
        description="CSS media type to emulate ('screen' or 'print')"
    )
    
    scale: float = Field(default=1.0, ge=0.1, le=2.0, description="Scale of the webpage rendering (0.1 to 2.0)")
    
    margin: MarginConfig = Field(default_factory=MarginConfig.no_margins, description="Margins for PDF pages")
    
    # Wait conditions
    wait_until: Literal["networkidle", "load", "domcontentloaded"] = Field(
        default="networkidle",
        description="Navigation wait condition"
    )
    wait_delay: int = Field(default=200, ge=0, description="Additional delay in milliseconds after load to let JS render")
    
    # Single continuous page option (e.g., long receipt, invoice, dashboard)
    single_page: bool = Field(
        default=False, 
        description="Fit full page content into a single continuous PDF page"
    )
    
    page_ranges: Optional[str] = Field(default=None, description="Paper ranges to print, e.g., '1-5', '8', '11-13'")
    
    # Header and footer
    display_header_footer: bool = Field(default=False, description="Display header and footer")
    header_template: Optional[str] = Field(default=None, description="HTML template for print header")
    footer_template: Optional[str] = Field(default=None, description="HTML template for print footer")
    
    # Injected custom CSS
    custom_css: Optional[str] = Field(default=None, description="Optional custom CSS injected before printing")
    
    # Viewport
    viewport_width: int = Field(default=1280, ge=320, description="Emulated browser viewport width")
    viewport_height: int = Field(default=900, ge=240, description="Emulated browser viewport height")

    # Collapsible menus & Accordions
    expand_collapsible: bool = Field(
        default=True,
        description="Automatically expand all collapsible menus, accordions, and details tags to include hidden content",
    )

    # Session, Localization & Authentication
    use_firefox_cookies: bool = Field(
        default=True,
        description="Automatically import session cookies and localStorage from local Firefox browser for the target domain",
    )
    cookies: Optional[list[dict]] = Field(
        default=None,
        description="Explicit list of cookies to inject into browser context",
    )
    locale: Optional[str] = Field(
        default="en-US",
        description="Language/locale for rendering and Accept-Language header (e.g., 'en-US', 'en', 'ru')",
    )
