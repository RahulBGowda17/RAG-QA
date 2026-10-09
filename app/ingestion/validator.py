import os
import re
import hashlib
from pathlib import Path
from typing import Tuple
from app.config import Config


class ValidationError(Exception):
    """Custom exception raised when document validation fails."""
    pass


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and filesystem attacks."""
    if not filename:
        raise ValidationError("Filename cannot be empty.")
    
    # Strip any directory components
    clean_name = os.path.basename(filename)
    # Replace dangerous characters with underscore
    clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean_name)
    # Prevent hidden files or double dots
    clean_name = clean_name.lstrip('.')
    if not clean_name:
        clean_name = "uploaded_document"
    return clean_name


def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file contents for deduplication and integrity."""
    return hashlib.sha256(file_bytes).hexdigest()


def validate_upload(filename: str, file_bytes: bytes) -> Tuple[str, str, int]:
    """
    Validate uploaded file parameters:
    1. Extension check
    2. File size limit
    3. Non-empty check
    4. Magic bytes / header inspection
    
    Returns: (clean_filename, file_type, file_size)
    """
    if not file_bytes:
        raise ValidationError("Uploaded file is empty (0 bytes).")
    
    file_size = len(file_bytes)
    if file_size > Config.MAX_CONTENT_LENGTH:
        raise ValidationError(
            f"File size ({file_size / (1024*1024):.2f} MB) exceeds maximum allowed limit of {Config.MAX_UPLOAD_SIZE_MB} MB."
        )

    clean_filename = sanitize_filename(filename)
    ext = clean_filename.rsplit(".", 1)[-1].lower() if "." in clean_filename else ""

    if ext not in Config.ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file format '.{ext}'. Supported formats are: {', '.join(sorted(Config.ALLOWED_EXTENSIONS))}."
        )

    # Magic byte validation
    if ext == "pdf":
        if not file_bytes.startswith(b"%PDF-"):
            raise ValidationError("Malformed PDF file: missing %PDF header.")
    elif ext == "docx":
        # DOCX is a ZIP container: starts with PK\x03\x04
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise ValidationError("Malformed DOCX file: missing valid Office Open XML ZIP signature.")
    elif ext == "txt":
        # Check if text is decodable as utf-8 or ascii
        try:
            file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                file_bytes.decode("latin-1")
            except Exception:
                raise ValidationError("Malformed text file: unable to decode characters.")

    return clean_filename, ext, file_size
