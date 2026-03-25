"""
PDF file loader.

Handles loading and preprocessing of PDF documents.
"""

from pathlib import Path
from typing import Optional

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from .base import BaseDataLoader, IngestedData, IngestSource
from .cleaning import TextCleaner
from .utils import validate_file_exists, validate_file_extension


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
        
        self.cleaner = cleaner or TextCleaner()
    
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
                    page_text = page.extract_text()
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
