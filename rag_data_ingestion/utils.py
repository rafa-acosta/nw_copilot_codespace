"""
Utility functions for data ingestion and processing.

Provides common utilities for file I/O, validation, and error handling.
"""

import os
from pathlib import Path
from typing import Union, Optional, List


def validate_file_exists(file_path: Union[str, Path]) -> bool:
    """
    Validate that a file exists.
    
    Args:
        file_path: Path to the file.
        
    Returns:
        True if file exists, False otherwise.
        
    Raises:
        TypeError: If file_path is not a string or Path object.
    """
    if not isinstance(file_path, (str, Path)):
        raise TypeError(f"Expected str or Path, got {type(file_path)}")
    
    return Path(file_path).is_file()


def validate_file_extension(
    file_path: Union[str, Path],
    allowed_extensions: List[str],
) -> bool:
    """
    Validate that a file has an allowed extension.
    
    Args:
        file_path: Path to the file.
        allowed_extensions: List of allowed extensions (e.g., ['.txt', '.pdf']).
        
    Returns:
        True if extension is allowed, False otherwise.
    """
    file_extension = Path(file_path).suffix.lower()
    allowed = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
               for ext in allowed_extensions]
    return file_extension in allowed


def get_file_size(file_path: Union[str, Path]) -> int:
    """
    Get file size in bytes.
    
    Args:
        file_path: Path to the file.
        
    Returns:
        File size in bytes.
        
    Raises:
        FileNotFoundError: If file does not exist.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return file_path.stat().st_size


def read_file_safely(
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
    fallback_encoding: str = 'latin-1',
) -> Optional[str]:
    """
    Read a text file with fallback encoding handling.
    
    Args:
        file_path: Path to the file.
        encoding: Primary encoding to try (default: utf-8).
        fallback_encoding: Fallback encoding if primary fails (default: latin-1).
        
    Returns:
        File contents as string, or None if read fails.
        
    Raises:
        FileNotFoundError: If file does not exist.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding=fallback_encoding) as f:
                return f.read()
        except Exception as e:
            raise RuntimeError(f"Failed to read file {file_path}: {str(e)}")


def sanitize_text(text: str) -> str:
    """
    Basic text sanitization for safety.
    
    Removes null bytes and other problematic characters.
    
    Args:
        text: Input text.
        
    Returns:
        Sanitized text.
    """
    # Remove null bytes
    text = text.replace('\x00', '')
    # Remove control characters except newlines and tabs
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t\r')
    return text


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> List[str]:
    """
    Simple text chunking utility for preparing text for RAG processing.
    
    Splits text by character count with optional overlap.
    For production use, consider more sophisticated chunking strategies
    that respect sentence or paragraph boundaries.
    
    Args:
        text: Text to chunk.
        chunk_size: Number of characters per chunk.
        overlap: Number of overlapping characters between chunks.
        
    Returns:
        List of text chunks.
        
    Raises:
        ValueError: If chunk_size or overlap are invalid.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        
        if end >= len(text):
            break
        
        start = end - overlap
    
    return chunks
