"""
RAG-Optimized Data Ingestion Library

A modular, scalable Python library for ingesting and preprocessing
various data formats for Retrieval-Augmented Generation (RAG) systems.

Supports:
    - Plain text files (.txt)
    - PDF documents (.pdf)
    - Web content (URLs)
    - Microsoft Word (.docx)
    - Microsoft Excel (.xlsx)
    - JSON files (.json)
    - Cisco configurations (.conf, .cfg, .config)

Example:
    >>> from rag_data_ingestion import TextFileLoader, PDFLoader
    >>> 
    >>> # Load a text file
    >>> loader = TextFileLoader()
    >>> data = loader.load('document.txt')
    >>> print(data.content)
    >>> print(data.source.metadata)
"""

__version__ = "1.0.0"
__author__ = "RAG Development Team"

from .base import BaseDataLoader, IngestedData, IngestSource, LoaderFactory
from .text_loader import TextFileLoader
from .pdf_loader import PDFLoader
from .web_loader import WebLoader
from .docx_loader import DocxLoader
from .excel_loader import ExcelLoader
from .json_loader import JSONLoader
from .cisco_loader import CiscoConfigLoader
from .cleaning import TextCleaner
from .utils import (
    validate_file_exists,
    validate_file_extension,
    chunk_text,
)

# Register loaders with factory
LoaderFactory.register('text', TextFileLoader)
LoaderFactory.register('pdf', PDFLoader)
LoaderFactory.register('url', WebLoader)
LoaderFactory.register('docx', DocxLoader)
LoaderFactory.register('excel', ExcelLoader)
LoaderFactory.register('json', JSONLoader)
LoaderFactory.register('cisco', CiscoConfigLoader)

__all__ = [
    # Base classes
    'BaseDataLoader',
    'IngestedData',
    'IngestSource',
    'LoaderFactory',
    
    # Loaders
    'TextFileLoader',
    'PDFLoader',
    'WebLoader',
    'DocxLoader',
    'ExcelLoader',
    'JSONLoader',
    'CiscoConfigLoader',
    
    # Cleaning and utilities
    'TextCleaner',
    'validate_file_exists',
    'validate_file_extension',
    'chunk_text',
]
