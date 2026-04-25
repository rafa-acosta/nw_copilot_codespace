"""
Cisco network device configuration file loader.

Handles loading and preprocessing of Cisco device configuration files.
Parses Cisco IOS and IOS-XE configurations.
"""

from pathlib import Path
from typing import Optional, List

from .base import BaseDataLoader, IngestedData, IngestSource
from .cleaning import TextCleaner
from .utils import validate_file_exists, read_file_safely


class CiscoConfigLoader(BaseDataLoader):
    """
    Loader for Cisco network device configurations.
    
    Parses Cisco IOS/IOS-XE configuration files and organizes
    them by configuration sections. Useful for infrastructure
    documentation and RAG-based network config analysis.
    
    Example:
        >>> loader = CiscoConfigLoader()
        >>> data = loader.load('router_config.txt')
        >>> print(data.content[:100])
    """
    
    # Common Cisco config file extensions
    SUPPORTED_EXTENSIONS = ['.txt', '.conf', '.cfg', '.config']
    
    def __init__(self, cleaner: Optional[TextCleaner] = None):
        """
        Initialize CiscoConfigLoader.
        
        Args:
            cleaner: Optional TextCleaner instance.
        """
        self.cleaner = cleaner or TextCleaner.for_network_config()
    
    def validate_source(self, source: str) -> bool:
        """
        Validate that source is a valid config file.
        
        Args:
            source: File path to validate.
            
        Returns:
            True if file exists and has valid extension, False otherwise.
        """
        if not validate_file_exists(source):
            return False
        
        file_ext = Path(source).suffix.lower()
        return file_ext in self.SUPPORTED_EXTENSIONS
    
    def _extract_sections(self, raw_text: str) -> dict:
        """
        Extract major configuration sections from Cisco config.
        
        Args:
            raw_text: Raw configuration text.
            
        Returns:
            Dictionary of configuration sections.
        """
        sections = {}
        current_section = 'general'
        section_lines = []
        
        # Common Cisco main configuration sections
        main_sections = [
            'interface', 'router', 'line', 'access-list', 'route-map',
            'class-map', 'policy-map', 'service-policy', 'vlan',
            'ip route', 'bgp', 'ospf', 'eigrp', 'isis', 'rip'
        ]
        
        for line in raw_text.split('\n'):
            line_lower = line.lower().strip()
            
            # Check if line starts a new major section
            is_new_section = any(
                line_lower.startswith(section) for section in main_sections
            )
            
            if is_new_section and line.strip():
                # Save previous section
                if section_lines:
                    sections[current_section] = '\n'.join(section_lines)
                
                # Start new section
                current_section = line.strip()[:50]  # Limit section name length
                section_lines = [line]
            else:
                section_lines.append(line)
        
        # Save last section
        if section_lines:
            sections[current_section] = '\n'.join(section_lines)
        
        return sections
    
    def _add_section_markers(self, sections: dict) -> str:
        """
        Convert sections dictionary to marked text format.
        
        Args:
            sections: Configuration sections dictionary.
            
        Returns:
            Formatted text with section markers.
        """
        text_parts = []
        for section_name, section_content in sections.items():
            text_parts.append(f"\n--- Cisco Section: {section_name} ---\n")
            text_parts.append(section_content)
        
        return '\n'.join(text_parts)
    
    def load(self, source: str, **kwargs) -> IngestedData:
        """
        Load and process a Cisco configuration file.
        
        Args:
            source: Path to the configuration file.
            **kwargs: Optional parameters:
                - organize_sections (bool): Organize by sections (default: True).
                - redact_sensitive (bool): Mask passwords/secrets (default: True).
                
        Returns:
            IngestedData with processed configuration text.
            
        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file is not a valid config file.
        """
        if not self.validate_source(source):
            raise ValueError(f"Invalid Cisco config file: {source}")
        
        organize = kwargs.get('organize_sections', True)
        redact = kwargs.get('redact_sensitive', True)
        metadata = {}
        
        try:
            # Read configuration file
            raw_text = read_file_safely(source)
            
            # Redact sensitive information if requested
            if redact:
                raw_text = self._redact_sensitive_data(raw_text)
            
            # Organize by sections if requested
            if organize:
                sections = self._extract_sections(raw_text)
                raw_text = self._add_section_markers(sections)
                metadata['section_count'] = len(sections)
                metadata['sections'] = list(sections.keys())
            
            # Count configuration lines
            config_lines = [l for l in raw_text.split('\n') if l.strip()]
            metadata['line_count'] = len(config_lines)
            
        except Exception as e:
            raise ValueError(f"Failed to read Cisco config {source}: {str(e)}")
        
        # Clean the processed text
        cleaned_text = self.cleaner.clean(raw_text)
        
        # Create metadata
        ingest_source = self._create_ingest_source(
            source=source,
            source_type='cisco_config',
            metadata=metadata
        )
        
        return IngestedData(content=cleaned_text, source=ingest_source)
    
    @staticmethod
    def _redact_sensitive_data(text: str) -> str:
        """
        Redact sensitive information from configuration.
        
        Masks passwords, secrets, and other sensitive credentials.
        
        Args:
            text: Configuration text.
            
        Returns:
            Text with sensitive data redacted.
        """
        import re
        
        # Patterns for sensitive data
        patterns = [
            (r'(?i)(password\s+)([^\s]+)', r'\1[REDACTED]'),
            (r'(?i)(secret\s+)([^\s]+)', r'\1[REDACTED]'),
            (r'(?i)(user\s+\S+\s+password\s+)([^\s]+)', r'\1[REDACTED]'),
            (r'(?i)(enable password\s+)([^\s]+)', r'\1[REDACTED]'),
            (r'(?i)(snmp-server\s+community\s+)([^\s]+)', r'\1[REDACTED]'),
        ]
        
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
        
        return text
