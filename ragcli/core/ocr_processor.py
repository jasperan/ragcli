"""OCR processing for PDFs using DeepSeek-OCR via vLLM in ragcli."""

import requests
import base64
from typing import Optional
from pdfplumber import open as pdf_open
from PIL import Image
from io import BytesIO
from ..config.config_manager import load_config

def pdf_to_markdown(pdf_path: str, config: dict) -> Optional[str]:
    """Extract text from PDF using OCR via vLLM."""
    vllm_endpoint = config['ocr']['vllm_endpoint']
    model = config['ocr']['model']
    temperature = config['ocr']['temperature']
    max_tokens = config['ocr']['max_tokens']
    
    if not config['ocr']['enabled']:
        # Fallback to text extraction if OCR disabled
        text = ""
        with pdf_open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        return text
    
    # OCR mode: Convert pages to images, send to vLLM
    extracted_markdown = ""
    
    with pdf_open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # Render page to image
            img = page.to_image(resolution=300)
            pil_img = img.original  # PIL Image
            
            # Convert to base64
            buffer = BytesIO()
            pil_img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # vLLM request
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract all text from this image and format as markdown, preserving tables and structure."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}},
                        ]
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            response = requests.post(
                f"{vllm_endpoint}/v1/chat/completions",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            content = response.json()['choices'][0]['message']['content']
            extracted_markdown += f"## Page {page_num}\n{content}\n\n"
    
    return extracted_markdown.strip()

# TODO: Batch pages, error retries (2), post-process markdown, handle non-PDF
