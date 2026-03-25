"""
Base classes and interfaces for data ingestion.

Defines abstract base class for all data loaders to ensure
consistent interface and behavior across different data sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class IngestSource:
    """
    Metadata about an ingested data source.
    
    Attributes:
        source_type: Type of the data source (e.g., 'pdf', 'url', 'text_file').
        source_path: Location/URL of the source.
        timestamp: When the data was ingested.
        metadata: Additional context about the source.
    """
    source_type: str
    source_path: str
    timestamp: datetime = None
    metadata: Optional[dict] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class IngestedData:
    """
    Result of data ingestion.
    
    Contains cleaned and normalized text along with source metadata.
    
    Attributes:
        content: The cleaned and normalized text content.
        source: Metadata about the data source.
    """
    content: str
    source: IngestSource


class BaseDataLoader(ABC):
    """
    Abstract base class for all data loaders.
    
    Defines the interface that all loader implementations must follow.
    This ensures consistent behavior and allows for polymorphic usage.
    """
    
    @abstractmethod
    def load(self, source: str, **kwargs) -> IngestedData:
        """
        Load and preprocess data from a source.
        
        Args:
            source: Path or location of the data source.
            **kwargs: Additional loader-specific arguments.
            
        Returns:
            IngestedData containing cleaned content and metadata.
            
        Raises:
            FileNotFoundError: If source does not exist.
            ValueError: If source format is invalid.
            Exception: For loader-specific errors.
        """
        pass
    
    @abstractmethod
    def validate_source(self, source: str) -> bool:
        """
        Validate that a source is compatible with this loader.
        
        Args:
            source: Path or location to validate.
            
        Returns:
            True if source is compatible, False otherwise.
        """
        pass
    
    def _create_ingest_source(
        self,
        source: str,
        source_type: str,
        metadata: Optional[dict] = None,
    ) -> IngestSource:
        """
        Helper method to create IngestSource metadata.
        
        Args:
            source: Source path/location.
            source_type: Type of source.
            metadata: Additional metadata.
            
        Returns:
            IngestSource object.
        """
        return IngestSource(
            source_type=source_type,
            source_path=source,
            metadata=metadata or {},
        )


class LoaderFactory:
    """
    Factory for creating appropriate data loaders.
    
    Provides a registry pattern to manage loader types and
    enables automatic selection based on source type.
    """
    
    _loaders: dict = {}
    
    @classmethod
    def register(cls, source_type: str, loader_class: type) -> None:
        """
        Register a loader for a specific source type.
        
        Args:
            source_type: The type identifier (e.g., 'pdf', 'url').
            loader_class: The loader class to register.
        """
        cls._loaders[source_type] = loader_class
    
    @classmethod
    def get_loader(cls, source_type: str) -> Optional[BaseDataLoader]:
        """
        Get a loader instance for a specific source type.
        
        Args:
            source_type: The type identifier.
            
        Returns:
            Loader instance or None if not registered.
        """
        loader_class = cls._loaders.get(source_type)
        return loader_class() if loader_class else None
    
    @classmethod
    def list_available_loaders(cls) -> list:
        """
        List all registered loader types.
        
        Returns:
            List of registered source type identifiers.
        """
        return list(cls._loaders.keys())
