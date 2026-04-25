"""
Web content loader.

Handles loading text content from URLs and preprocessing.
"""

from typing import Optional
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

from .base import BaseDataLoader, IngestedData, IngestSource
from .cleaning import TextCleaner


class WebLoader(BaseDataLoader):
    """
    Loader for web content from URLs.
    
    Fetches HTML content and extracts text using BeautifulSoup.
    Handles SSL verification and request headers.
    
    Example:
        >>> loader = WebLoader()
        >>> data = loader.load('https://example.com')
        >>> print(data.content[:100])
    """
    
    def __init__(
        self,
        cleaner: Optional[TextCleaner] = None,
        timeout: int = 10,
        verify_ssl: bool = True,
    ):
        """
        Initialize WebLoader.
        
        Args:
            cleaner: Optional TextCleaner instance.
            timeout: Request timeout in seconds (default: 10).
            verify_ssl: Whether to verify SSL certificates (default: True).
            
        Raises:
            ImportError: If requests or BeautifulSoup are not installed.
        """
        if requests is None or BeautifulSoup is None:
            raise ImportError(
                "requests and BeautifulSoup4 are required for web loading. "
                "Install with: pip install requests beautifulsoup4"
            )
        
        self.cleaner = cleaner or TextCleaner.for_prose()
        self.timeout = timeout
        self.verify_ssl = verify_ssl
    
    def validate_source(self, source: str) -> bool:
        """
        Validate that source is a valid URL.
        
        Args:
            source: URL to validate.
            
        Returns:
            True if valid URL format, False otherwise.
        """
        try:
            result = urlparse(source)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except Exception:
            return False
    
    def load(self, source: str, **kwargs) -> IngestedData:
        """
        Load and extract text from a web URL.
        
        Args:
            source: URL to fetch content from.
            **kwargs: Optional parameters:
                - headers (dict): Custom HTTP headers.
                - extract_links (bool): Include links in output (default: False).
                
        Returns:
            IngestedData with extracted and cleaned text.
            
        Raises:
            ValueError: If URL is invalid or request fails.
        """
        if not self.validate_source(source):
            raise ValueError(f"Invalid URL: {source}")
        
        extract_links = kwargs.get('extract_links', False)
        headers = kwargs.get('headers', {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        metadata = {}
        
        try:
            response = requests.get(
                source,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers=headers
            )
            response.raise_for_status()
            
            metadata['status_code'] = response.status_code
            metadata['content_type'] = response.headers.get('Content-Type', 'Unknown')
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to fetch URL {source}: {str(e)}")
        
        # Parse HTML and extract text
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'footer']):
                element.decompose()
            
            # Extract text
            raw_text = soup.get_text(separator='\n')
            
            # Optionally extract links
            if extract_links:
                links = [a.get('href') for a in soup.find_all('a', href=True)]
                links_text = '\n'.join([f"Link: {link}" for link in links if link])
                raw_text = f"{raw_text}\n\n--- Links ---\n{links_text}"
            
        except Exception as e:
            raise ValueError(f"Failed to parse HTML from {source}: {str(e)}")
        
        # Clean the extracted text
        cleaned_text = self.cleaner.clean(raw_text)
        
        # Create metadata
        ingest_source = self._create_ingest_source(
            source=source,
            source_type='url',
            metadata=metadata
        )
        
        return IngestedData(content=cleaned_text, source=ingest_source)
