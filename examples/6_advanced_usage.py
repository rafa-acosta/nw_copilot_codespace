"""
Example 6: Advanced Usage - Factory Pattern and Batch Processing

Demonstrates advanced patterns for production use including:
- Using LoaderFactory for dynamic loader selection
- Batch processing multiple files
- Combining multiple sources with unified interface
- Error handling and retry logic
"""

from pathlib import Path
from typing import List, Dict
from rag_data_ingestion import (
    LoaderFactory,
    IngestedData,
    TextCleaner,
)


def example_factory_pattern():
    """Use LoaderFactory to dynamically select loaders."""
    
    # Factory returns the appropriate loader based on source type
    text_loader = LoaderFactory.get_loader('text')
    pdf_loader = LoaderFactory.get_loader('pdf')
    json_loader = LoaderFactory.get_loader('json')
    
    print(f"Available loaders: {LoaderFactory.list_available_loaders()}")
    print(f"Text loader: {text_loader.__class__.__name__}")
    print(f"PDF loader: {pdf_loader.__class__.__name__}")
    
    # This allows dynamic loader selection based on file type
    # file_type = determine_file_type('document.pdf')  # returns 'pdf'
    # loader = LoaderFactory.get_loader(file_type)
    # data = loader.load('document.pdf')


def example_batch_processing():
    """Process multiple files with unified interface."""
    
    # List of files to process
    files_to_process = [
        # ('path/to/file.txt', 'text'),
        # ('path/to/file.pdf', 'pdf'),
        # ('path/to/file.json', 'json'),
    ]
    
    results: List[IngestedData] = []
    
    for file_path, file_type in files_to_process:
        try:
            loader = LoaderFactory.get_loader(file_type)
            if loader:
                data = loader.load(file_path)
                results.append(data)
                print(f"✓ Loaded {file_path} ({len(data.content)} chars)")
            else:
                print(f"✗ No loader for type: {file_type}")
        except Exception as e:
            print(f"✗ Error loading {file_path}: {str(e)}")
    
    # Process all results together
    print(f"\nTotal files processed: {len(results)}")
    total_chars = sum(len(data.content) for data in results)
    print(f"Total content size: {total_chars} characters")


def example_source_deduction():
    """Automatically determine file type and load."""
    
    def get_loader_for_file(file_path: str):
        """Deduce loader from file extension."""
        ext = Path(file_path).suffix.lower()
        
        type_mapping = {
            '.txt': 'text',
            '.pdf': 'pdf',
            '.docx': 'docx',
            '.xlsx': 'excel',
            '.json': 'json',
            '.conf': 'cisco',
            '.cfg': 'cisco',
            '.config': 'cisco',
        }
        
        file_type = type_mapping.get(ext)
        if file_type:
            return LoaderFactory.get_loader(file_type)
        return None
    
    # Usage
    # loader = get_loader_for_file('document.pdf')
    # if loader:
    #     data = loader.load('document.pdf')
    print("Example: Automatic file type detection")


def example_combined_cleaning_config():
    """Create a centralized cleaning configuration for consistency."""
    
    # Define organization-wide cleaning standards
    rag_cleaner = TextCleaner(
        normalize_unicode_chars=True,
        remove_extra_spaces=True,
        lowercase=False,  # Preserve case for NLP
        expand_contracs=True,
        remove_urls_flag=False,  # Keep URLs as they may be important
        remove_emails_flag=False,  # Keep emails for contact info
        keep_punctuation=True,
    )
    
    # Use across all loaders for consistency
    from rag_data_ingestion import (
        TextFileLoader,
        PDFLoader,
        DocxLoader,
        ExcelLoader,
        JSONLoader,
    )
    
    loaders = {
        'text': TextFileLoader(cleaner=rag_cleaner),
        'pdf': PDFLoader(cleaner=rag_cleaner),
        'docx': DocxLoader(cleaner=rag_cleaner),
        'excel': ExcelLoader(cleaner=rag_cleaner),
        'json': JSONLoader(cleaner=rag_cleaner),
    }
    
    print("Created loaders with unified cleaning configuration")
    return loaders


def example_metadata_aggregation():
    """Collect and analyze metadata from ingested sources."""
    
    # Simulated ingested data
    mock_results = []
    
    # In practice, populate with actual loaded data:
    # for file_path in file_list:
    #     loader = get_appropriate_loader(file_path)
    #     data = loader.load(file_path)
    #     mock_results.append(data)
    
    # Extract metadata
    metadata_summary: Dict = {
        'total_sources': len(mock_results),
        'by_type': {},
        'total_content_size': 0,
    }
    
    for data in mock_results:
        source_type = data.source.source_type
        
        if source_type not in metadata_summary['by_type']:
            metadata_summary['by_type'][source_type] = {
                'count': 0,
                'total_size': 0,
                'metadata': []
            }
        
        metadata_summary['by_type'][source_type]['count'] += 1
        metadata_summary['by_type'][source_type]['total_size'] += len(data.content)
        metadata_summary['by_type'][source_type]['metadata'].append(
            data.source.metadata
        )
        
        metadata_summary['total_content_size'] += len(data.content)
    
    print("Metadata aggregation example:")
    print(f"Total sources: {metadata_summary['total_sources']}")
    print(f"By type: {metadata_summary['by_type']}")
    print(f"Total content: {metadata_summary['total_content_size']} characters")


def example_error_handling_with_retry():
    """Implement robust error handling with retry logic."""
    
    def load_with_retry(file_path: str, max_retries: int = 3) -> IngestedData:
        """Load file with retry logic."""
        
        for attempt in range(1, max_retries + 1):
            try:
                # Determine loader
                loader = LoaderFactory.get_loader(
                    Path(file_path).suffix.lower().strip('.')
                )
                if not loader:
                    raise ValueError(f"No loader for {file_path}")
                
                # Attempt load
                data = loader.load(file_path)
                print(f"✓ Loaded on attempt {attempt}")
                return data
                
            except Exception as e:
                print(f"✗ Attempt {attempt} failed: {str(e)}")
                if attempt == max_retries:
                    raise
    
    print("Error handling with retry example")
    # Usage: load_with_retry('document.pdf')


if __name__ == "__main__":
    print("=" * 60)
    print("RAG Data Ingestion - Example 6: Advanced Usage")
    print("=" * 60)
    
    print("\n1. Factory Pattern:")
    example_factory_pattern()
    
    print("\n2. Batch Processing:")
    example_batch_processing()
    
    print("\n3. Source Type Deduction:")
    example_source_deduction()
    
    print("\n4. Combined Cleaning Configuration:")
    example_combined_cleaning_config()
    
    print("\n5. Metadata Aggregation:")
    example_metadata_aggregation()
    
    print("\n6. Error Handling with Retry:")
    example_error_handling_with_retry()
