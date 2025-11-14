"""Document processing utilities for chunking and preprocessing."""

import tiktoken
from pathlib import Path
from typing import List, Dict, Any, Optional
from .ocr_processor import pdf_to_markdown


def preprocess_document(file_path: str, config: dict) -> tuple[str, bool]:
    """Preprocess document to extract text and metadata.

    Args:
        file_path: Path to the document file
        config: Configuration dictionary

    Returns:
        tuple: (extracted_text, ocr_processed_flag)

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If format unsupported or file too large
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_format = path.suffix.lstrip('.').lower()
    if file_format not in config['documents']['supported_formats']:
        raise ValueError(f"Unsupported format: {file_format}")

    file_size = path.stat().st_size
    max_size = config['documents']['max_file_size_mb'] * 1024 * 1024
    if file_size > max_size:
        raise ValueError(f"File too large: {file_size} > {max_size} bytes")

    text = ""
    ocr_processed = False

    if file_format == 'pdf':
        ocr_processed = True
        text = pdf_to_markdown(str(path), config) or ""
    else:  # txt, md
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

    return text, ocr_processed


def chunk_text(text: str, config: dict) -> List[Dict[str, Any]]:
    """Chunk text into smaller pieces with token-based splitting.

    Args:
        text: Full document text
        config: Configuration dictionary

    Returns:
        List of chunks with metadata: [{'text': str, 'token_count': int, 'char_count': int}, ...]
    """
    # Use tiktoken for accurate token counting (GPT-based)
    try:
        enc = tiktoken.get_encoding("cl100k_base")  # GPT-3.5/4 encoding
    except:
        # Fallback to simple word count if tiktoken fails
        enc = None

    def token_count(text: str) -> int:
        if enc:
            return len(enc.encode(text))
        else:
            return len(text.split())  # Approx

    chunk_size = config['documents']['chunk_size']
    overlap_tokens = int(chunk_size * config['documents']['chunk_overlap_percentage'] / 100)

    # Custom chunking with token overlap
    chunks = []
    start = 0
    text_tokens = enc.encode(text) if enc else text.split()

    while start < len(text_tokens):
        end = min(start + chunk_size, len(text_tokens))
        chunk_tokens = text_tokens[start:end]
        chunk_text = enc.decode(chunk_tokens) if enc else ' '.join(chunk_tokens)

        chunks.append({
            'text': chunk_text,
            'token_count': len(chunk_tokens),
            'char_count': len(chunk_text)
        })

        start = end - overlap_tokens
        if start >= end:  # Prevent infinite loop
            break

    return chunks


def calculate_total_tokens(chunks: List[Dict[str, Any]]) -> int:
    """Calculate total tokens across all chunks."""
    return sum(chunk['token_count'] for chunk in chunks)


def get_document_metadata(text: str, chunks: List[Dict[str, Any]], ocr_processed: bool) -> Dict[str, Any]:
    """Generate document metadata."""
    return {
        'extracted_text_size_bytes': len(text.encode('utf-8')),
        'chunk_count': len(chunks),
        'total_tokens': calculate_total_tokens(chunks),
        'ocr_processed': ocr_processed
    }
