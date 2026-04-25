"""
PDF file loader.

Handles loading and preprocessing of PDF documents.
"""

from contextlib import contextmanager
from pathlib import Path
import re
import threading
from typing import Optional

try:
    import PyPDF2
    from PyPDF2 import _page as pypdf_page
except ImportError:
    PyPDF2 = None
    pypdf_page = None

from .base import BaseDataLoader, IngestedData, IngestSource
from .cleaning import TextCleaner
from .utils import validate_file_exists, validate_file_extension


_COLLAPSED_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]{18,}")
_SPACE_RECOVERY_FACTOR = 0.995
_SPACE_RECOVERY_LOCK = threading.Lock()


class PDFLoader(BaseDataLoader):
    """
    Loader for PDF documents.
    
    Extracts text from PDF files and applies preprocessing.
    Uses PyPDF2 for PDF parsing.
    
    Example:
        >>> loader = PDFLoader()
        >>> data = loader.load('document.pdf')
        >>> print(data.content[:100])
    """
    
    SUPPORTED_EXTENSIONS = ['.pdf']
    
    def __init__(self, cleaner: Optional[TextCleaner] = None):
        """
        Initialize PDFLoader.
        
        Args:
            cleaner: Optional TextCleaner instance.
            
        Raises:
            ImportError: If PyPDF2 is not installed.
        """
        if PyPDF2 is None:
            raise ImportError("PyPDF2 is required for PDF loading. Install with: pip install PyPDF2")
        
        self.cleaner = cleaner or TextCleaner.for_ocr_prose()
    
    def validate_source(self, source: str) -> bool:
        """
        Validate that source is a valid PDF file.
        
        Args:
            source: File path to validate.
            
        Returns:
            True if valid PDF file, False otherwise.
        """
        if not validate_file_exists(source):
            return False
        return validate_file_extension(source, self.SUPPORTED_EXTENSIONS)
    
    def load(self, source: str, **kwargs) -> IngestedData:
        """
        Load and extract text from a PDF file.
        
        Args:
            source: Path to the PDF file.
            **kwargs: Optional parameters:
                - extract_metadata (bool): Include PDF metadata (default: True).
                
        Returns:
            IngestedData with extracted and cleaned text.
            
        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file is not a valid PDF.
        """
        if not self.validate_source(source):
            raise ValueError(f"Invalid PDF file: {source}")
        
        extract_metadata = kwargs.get('extract_metadata', True)
        metadata = {}
        
        try:
            with open(source, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                
                # Extract text from all pages
                text_parts = []
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = self._extract_page_text(page)
                    if page_text:
                        text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                
                raw_text = '\n'.join(text_parts)
                
                # Extract metadata if requested
                if extract_metadata and pdf_reader.metadata:
                    metadata['pdf_title'] = pdf_reader.metadata.get('/Title', 'Unknown')
                    metadata['pdf_author'] = pdf_reader.metadata.get('/Author', 'Unknown')
                    metadata['page_count'] = len(pdf_reader.pages)
                
        except Exception as e:
            raise ValueError(f"Failed to read PDF {source}: {str(e)}")
        
        # Clean the extracted text
        cleaned_text = self.cleaner.clean(raw_text)
        
        # Create metadata
        ingest_source = self._create_ingest_source(
            source=source,
            source_type='pdf',
            metadata=metadata
        )
        
        return IngestedData(content=cleaned_text, source=ingest_source)

    def _extract_page_text(self, page) -> str:
        page_text = page.extract_text() or ""
        if not page_text or not self._needs_spacing_recovery(page_text):
            return page_text

        recovered_text = self._extract_text_with_space_recovery(page) or ""
        if self._readability_score(recovered_text) > self._readability_score(page_text):
            return recovered_text
        return page_text

    @staticmethod
    def _needs_spacing_recovery(text: str) -> bool:
        alpha_count = sum(char.isalpha() for char in text)
        if alpha_count < 40:
            return False
        if len(_COLLAPSED_WORD_RE.findall(text)) >= 1:
            return True
        return text.count(" ") / max(alpha_count, 1) < 0.08

    @staticmethod
    def _readability_score(text: str) -> float:
        alpha_count = sum(char.isalpha() for char in text)
        if alpha_count == 0:
            return 0.0
        long_run_penalty = sum(len(match.group(0)) - 17 for match in _COLLAPSED_WORD_RE.finditer(text))
        return (text.count(" ") - (long_run_penalty * 3)) / alpha_count

    def _extract_text_with_space_recovery(self, page) -> str:
        if pypdf_page is None:
            return page.extract_text() or ""

        with self._relaxed_space_widths():
            return page.extract_text() or ""

    @contextmanager
    def _relaxed_space_widths(self):
        if pypdf_page is None:
            yield
            return

        original_build_char_map = pypdf_page.build_char_map

        def patched_build_char_map(font_name, space_width, obj):
            font_type, computed_space_width, encoding, cmap, font = original_build_char_map(
                font_name,
                space_width,
                obj,
            )
            return (
                font_type,
                float(computed_space_width * _SPACE_RECOVERY_FACTOR),
                encoding,
                cmap,
                font,
            )

        with _SPACE_RECOVERY_LOCK:
            pypdf_page.build_char_map = patched_build_char_map
            try:
                yield
            finally:
                pypdf_page.build_char_map = original_build_char_map
