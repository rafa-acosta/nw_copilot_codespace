"""
JSON file loader.

Handles loading and preprocessing of JSON files.
"""

import json
from pathlib import Path
from typing import Optional

from .base import BaseDataLoader, IngestedData, IngestSource
from .cleaning import TextCleaner
from .utils import validate_file_exists, validate_file_extension, read_file_safely


class JSONLoader(BaseDataLoader):
    """
    Loader for JSON files.
    
    Parses JSON and converts nested structures to readable text format.
    Handles both flat and nested JSON structures.
    
    Example:
        >>> loader = JSONLoader()
        >>> data = loader.load('data.json')
        >>> print(data.content[:100])
    """
    
    SUPPORTED_EXTENSIONS = ['.json']
    
    def __init__(self, cleaner: Optional[TextCleaner] = None):
        """
        Initialize JSONLoader.
        
        Args:
            cleaner: Optional TextCleaner instance.
        """
        self.cleaner = cleaner or TextCleaner.for_structured_data()
    
    def validate_source(self, source: str) -> bool:
        """
        Validate that source is a valid JSON file.
        
        Args:
            source: File path to validate.
            
        Returns:
            True if valid JSON file, False otherwise.
        """
        if not validate_file_exists(source):
            return False
        return validate_file_extension(source, self.SUPPORTED_EXTENSIONS)
    
    def _flatten_json(self, obj, parent_key: str = '', sep: str = '.') -> dict:
        """
        Flatten nested JSON structure.
        
        Args:
            obj: JSON object to flatten.
            parent_key: Parent key prefix.
            sep: Separator for nested keys.
            
        Returns:
            Flattened dictionary.
        """
        items = []
        
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, (dict, list)):
                    items.extend(self._flatten_json(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, v))
        
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                new_key = f"{parent_key}[{i}]"
                if isinstance(v, (dict, list)):
                    items.extend(self._flatten_json(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, v))
        
        return dict(items)
    
    def _convert_to_text(self, data: dict) -> str:
        """
        Convert flattened JSON to readable text format.
        
        Args:
            data: Flattened JSON dictionary.
            
        Returns:
            Text representation of JSON data.
        """
        text_lines = []
        for key, value in data.items():
            if value is not None:
                text_lines.append(f"{key}: {str(value)}")
        return '\n'.join(text_lines)
    
    def load(self, source: str, **kwargs) -> IngestedData:
        """
        Load and process a JSON file.
        
        Args:
            source: Path to the JSON file.
            **kwargs: Optional parameters:
                - flatten (bool): Flatten nested structures (default: True).
                
        Returns:
            IngestedData with converted and cleaned text.
            
        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file is not valid JSON.
        """
        if not self.validate_source(source):
            raise ValueError(f"Invalid JSON file: {source}")
        
        flatten = kwargs.get('flatten', True)
        metadata = {}
        
        try:
            # Read JSON file
            json_text = read_file_safely(source)
            data = json.loads(json_text)
            
            # Flatten if requested
            if flatten:
                data = self._flatten_json(data)
            
            # Convert to text
            raw_text = self._convert_to_text(data)
            metadata['json_type'] = type(data).__name__
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in file {source}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to read JSON file {source}: {str(e)}")
        
        # Clean the converted text
        cleaned_text = self.cleaner.clean(raw_text)
        
        # Create metadata
        ingest_source = self._create_ingest_source(
            source=source,
            source_type='json',
            metadata=metadata
        )
        
        return IngestedData(content=cleaned_text, source=ingest_source)
