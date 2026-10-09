import io
import re
from typing import List, Dict, Any, Tuple
import pymupdf
import docx


def clean_text(text: str) -> str:
    """Normalize whitespace and strip non-printable characters while preserving structure."""
    if not text:
        return ""
    # Replace non-breaking spaces and form feeds
    text = text.replace("\xa0", " ").replace("\x0c", "\n")
    # Normalize excessive newlines to at most 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip trailing and leading whitespace
    return text.strip()


def parse_pdf(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], int]:
    """
    Extract text page by page from PDF using PyMuPDF.
    If a page contains no digital text (e.g., scanned PDF), attempts OCR fallback via pytesseract.
    Returns: (list of {page_number, text, section}, total_page_count)
    """
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    pages_data = []
    total_pages = len(doc)

    for page_idx in range(total_pages):
        page = doc[page_idx]
        raw_text = page.get_text("text")
        cleaned = clean_text(raw_text)

        # Scanned page OCR fallback if digital text is empty
        if not cleaned:
            try:
                import pytesseract
                from PIL import Image
                pix = page.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = pytesseract.image_to_string(img)
                cleaned = clean_text(ocr_text)
            except Exception:
                # If tesseract binary is not installed on system PATH, skip silently
                pass

        if cleaned:
            pages_data.append({
                "page_number": page_idx + 1,
                "text": cleaned,
                "section": f"Page {page_idx + 1}"
            })

    doc.close()
    return pages_data, total_pages


def parse_docx(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], int]:
    """
    Extract text paragraph by paragraph with heading awareness from DOCX.
    Returns: (list of {page_number, text, section}, estimated_page_count)
    """
    stream = io.BytesIO(file_bytes)
    doc = docx.Document(stream)
    elements_data = []
    current_section = "Introduction"
    current_paragraphs = []
    
    for para in doc.paragraphs:
        text = clean_text(para.text)
        if not text:
            continue
        
        # Check if paragraph is a heading
        if para.style and para.style.name and para.style.name.startswith("Heading"):
            if current_paragraphs:
                elements_data.append({
                    "page_number": 1,
                    "text": "\n".join(current_paragraphs),
                    "section": current_section
                })
                current_paragraphs = []
            current_section = text
        else:
            current_paragraphs.append(text)

    if current_paragraphs:
        elements_data.append({
            "page_number": 1,
            "text": "\n".join(current_paragraphs),
            "section": current_section
        })

    # Estimate page count (~300 words per page)
    total_words = sum(len(e["text"].split()) for e in elements_data)
    estimated_pages = max(1, (total_words + 299) // 300)
    
    return elements_data, estimated_pages


def parse_txt(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], int]:
    """
    Extract text from standard text files.
    Returns: (list of {page_number, text, section}, estimated_page_count)
    """
    try:
        raw_text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_text = file_bytes.decode("latin-1", errors="replace")

    cleaned = clean_text(raw_text)
    paragraphs = [clean_text(p) for p in cleaned.split("\n\n") if clean_text(p)]
    
    elements_data = []
    if paragraphs:
        for idx, para in enumerate(paragraphs):
            elements_data.append({
                "page_number": 1,
                "text": para,
                "section": f"Section {idx + 1}"
            })
    else:
        elements_data.append({
            "page_number": 1,
            "text": cleaned,
            "section": "General"
        })

    total_words = sum(len(e["text"].split()) for e in elements_data)
    estimated_pages = max(1, (total_words + 299) // 300)

    return elements_data, estimated_pages


def parse_document(file_type: str, file_bytes: bytes) -> Tuple[List[Dict[str, Any]], int]:
    """Parse document according to its file extension."""
    if file_type == "pdf":
        return parse_pdf(file_bytes)
    elif file_type == "docx":
        return parse_docx(file_bytes)
    elif file_type == "txt":
        return parse_txt(file_bytes)
    else:
        raise ValueError(f"No parser available for file type: {file_type}")
