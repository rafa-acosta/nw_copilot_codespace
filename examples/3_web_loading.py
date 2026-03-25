"""
Example 3: Loading Web Content

Demonstrates how to fetch and parse web content from URLs
for RAG preprocessing.
"""

from rag_data_ingestion import WebLoader, TextCleaner


def example_basic_web_loading():
    """Basic web content loading from URL."""
    loader = WebLoader(timeout=10, verify_ssl=True)
    
    # Example with a real URL
    # data = loader.load('https://example.com')
    # print(f"Content extracted (first 300 chars):\n{data.content[:300]}")
    # print(f"Status code: {data.source.metadata['status_code']}")
    # print(f"Content-Type: {data.source.metadata['content_type']}")
    print("Example: Basic web loading")
    print("Uncomment code above with actual URL to run")


def example_web_with_link_extraction():
    """Extract both content and links from webpage."""
    loader = WebLoader()
    
    # Extract links along with content
    # data = loader.load('https://example.com', extract_links=True)
    # print(f"Content with links:\n{data.content[:500]}")
    print("Example: Web loading with link extraction")
    print("Uncomment code above with actual URL to run")


def example_web_with_custom_headers():
    """Use custom headers for web requests."""
    custom_headers = {
        'User-Agent': 'Mozilla/5.0 (Custom Bot)',
        'Accept-Language': 'en-US',
    }
    
    loader = WebLoader()
    
    # data = loader.load(
    #     'https://example.com',
    #     headers=custom_headers,
    #     extract_links=True
    # )
    # print(f"Loaded with custom headers")
    # print(f"Response headers: {data.source.metadata}")
    print("Example: Web loading with custom headers")
    print("Uncomment code above with actual URL to run")


def example_error_handling():
    """Demonstrate error handling for invalid URLs."""
    loader = WebLoader()
    
    # Invalid URL
    try:
        # data = loader.load('not-a-valid-url')
        pass
    except ValueError as e:
        print(f"Caught error: {e}")
    
    # Network error (simulated)
    try:
        # data = loader.load('https://invalid-domain-that-does-not-exist-12345.com')
        pass
    except ValueError as e:
        print(f"Caught network error: {e}")
    
    print("Example: Error handling for web loading")
    print("Uncomment code above to demonstrate error handling")


if __name__ == "__main__":
    print("=" * 60)
    print("RAG Data Ingestion - Example 3: Web Loading")
    print("=" * 60)
    
    example_basic_web_loading()
    print()
    example_web_with_link_extraction()
    print()
    example_web_with_custom_headers()
    print()
    example_error_handling()
