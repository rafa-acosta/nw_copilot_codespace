"""
Plain text file loader.

Handles loading and preprocessing of plain text (.txt) files.
"""

from pathlib import Path
from typing import Optional

from .base import BaseDataLoader, IngestedData, IngestSource
from .cleaning import TextCleaner
from .utils import validate_file_exists, validate_file_extension, read_file_safely


class TextFileLoader(BaseDataLoader):
    """
    Loader for plain text files.
    
    Supports loading, decoding, and basic cleaning of UTF-8 and
    Latin-1 encoded text files.
    
    Example:
        >>> loader = TextFileLoader()
        >>> data = loader.load('document.txt')
        >>> print(data.content)
    """
    
    SUPPORTED_EXTENSIONS = ['.txt']
    
    def __init__(self, cleaner: Optional[TextCleaner] = None):
        """
        Initialize TextFileLoader.
        
        Args:
            cleaner: Optional TextCleaner instance. If None, creates default cleaner.
        """
        self.cleaner = cleaner or TextCleaner.for_ocr_prose()
    
    def validate_source(self, source: str) -> bool:
        """
        Validate that source is a valid text file.
        
        Args:
            source: File path to validate.
            
        Returns:
            True if valid .txt file, False otherwise.
        """
        if not validate_file_exists(source):
            return False
        return validate_file_extension(source, self.SUPPORTED_EXTENSIONS)
    
    def load(self, source: str, **kwargs) -> IngestedData:
        """
        Load and clean a text file.
        
        Args:
            source: Path to the text file.
            **kwargs: Optional encoding parameter.
                - encoding (str): Encoding to use (default: 'utf-8').
            
        Returns:
            IngestedData with cleaned text content.
            
        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file is not a .txt file.
        """
        if not self.validate_source(source):
            raise ValueError(f"Invalid text file: {source}")
        
        encoding = kwargs.get('encoding', 'utf-8')
        
        # Read file with encoding handling
        raw_text = read_file_safely(source, encoding=encoding)
        
        # Clean the text
        cleaned_text = self.cleaner.clean(raw_text)
        
        # Create metadata
        ingest_source = self._create_ingest_source(
            source=source,
            source_type='text_file',
            metadata={'encoding': encoding}
        )
        
        return IngestedData(content=cleaned_text, source=ingest_source)
