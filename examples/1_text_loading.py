"""
Example 1: Loading Plain Text Files

Demonstrates how to load, clean, and process plain text files
for RAG preprocessing.
"""

from rag_data_ingestion import TextFileLoader, TextCleaner


def example_basic_text_loading():
    """Basic text file loading with default settings."""
    loader = TextFileLoader()
    
    # Assumes 'document.txt' exists in the workspace
    data = loader.load('/workspaces/nw_copilot_codespace/testing_files/gibson.txt')
    print(f"Content preview: {data.content[:200]}")
    print(f"Source type: {data.source.source_type}")
    print(f"Metadata: {data.source.metadata}")
    print("Example: Basic text loading")
    print("Uncomment code above with actual file path to run")


def example_custom_text_cleaning():
    """Text loading with custom cleaning configuration."""
    # Create a custom cleaner that keeps structure
    cleaner = TextCleaner(
        normalize_unicode_chars=True,
        remove_extra_spaces=True,
        lowercase=False,  # Keep original case
        expand_contracs=True,
        remove_urls_flag=True,
        remove_emails_flag=True,
        keep_punctuation=True,
    )
    
    loader = TextFileLoader(cleaner=cleaner)
    
    data = loader.load('/workspaces/nw_copilot_codespace/testing_files/gibson.txt', encoding='utf-8')
    print(f"Cleaned content:\n{data.content}")
    print("Example: Custom text cleaning")
    print("Uncomment code above with actual file path to run")


def example_text_chunking():
    """Demonstrate text chunking for RAG preprocessing."""
    from rag_data_ingestion import chunk_text
    
    loader = TextFileLoader() # instance for text loader

    #sample_text = "This is a sample text that will be chunked. " * 50
    sample_text = loader.load('/workspaces/nw_copilot_codespace/testing_files/gibson.txt', encoding='utf-8')
    
    # Chunk into 300-character pieces with 50-character overlap
    chunks = chunk_text(sample_text, chunk_size=300, overlap=50)
    print(f"Number of chunks: {len(chunks)}")
    print(f"First chunk: {chunks[0][:100]}...")
    print(f"Last chunk: {chunks[-1][:100]}...")


if __name__ == "__main__":
    print("=" * 60)
    print("RAG Data Ingestion - Example 1: Text Files")
    print("=" * 60)
    
    #example_basic_text_loading()
    #print()
    #example_custom_text_cleaning()
    #print()
    example_text_chunking()
