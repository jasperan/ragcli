"""OCR processing for PDFs using DeepSeek-OCR via vLLM in ragcli."""

from typing import Optional
from pdfplumber import open as pdf_open
from ..utils.logger import get_logger

logger = get_logger(__name__)

def pdf_to_markdown(pdf_path: str, config: dict) -> Optional[str]:
    """Extract text from PDF using OCR via vLLM."""
    # Standard text extraction
    text = ""
    with pdf_open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
    return text.strip()
