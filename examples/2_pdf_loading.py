"""
Example 2: Loading PDF Documents

Demonstrates how to extract text from PDF files and prepare
them for RAG processing.
"""

from rag_data_ingestion import PDFLoader, TextCleaner



def example_basic_pdf_loading():
    """Basic PDF loading with metadata extraction."""
    loader = PDFLoader()
    
    # Assumes 'document.pdf' exists in the workspace
    # data = loader.load('document.pdf', extract_metadata=True)
    # print(f"Content preview: {data.content[:300]}")
    # print(f"PDF Metadata: {data.source.metadata}")
    print("Example: Basic PDF loading")
    print("Uncomment code above with actual PDF path to run")


def example_pdf_with_custom_cleaner():
    """PDF loading with custom text cleaning."""
    cleaner = TextCleaner(
        normalize_unicode_chars=True,
        remove_extra_spaces=True,
        lowercase=False,
        expand_contracs=False,
        remove_urls_flag=False,  # Keep URLs in PDFs
        remove_emails_flag=False,
        keep_punctuation=True,
    )
    
    loader = PDFLoader(cleaner=cleaner)
    
    # data = loader.load('document.pdf')
    # print(f"Cleaned PDF content:\n{data.content[:500]}")
    print("Example: PDF with custom cleaner")
    print("Uncomment code above with actual PDF path to run")


def example_pdf_page_extraction():
    """Demonstrate page-level extraction from PDFs."""
    # PDFLoader automatically includes page markers
    # Each page is marked with "--- Page N ---"
    
    # data = loader.load('document.pdf')
    # pages = data.content.split('--- Page')
    # print(f"Total pages: {len(pages) - 1}")  # -1 for header
    # print(f"First page content: {pages[1][:200]}...")
    print("Example: PDF page extraction")
    print("PDFs are automatically marked by page number")


if __name__ == "__main__":
    print("=" * 60)
    print("RAG Data Ingestion - Example 2: PDF Loading")
    print("=" * 60)
    
    example_basic_pdf_loading()
    print()
    example_pdf_with_custom_cleaner()
    print()
    example_pdf_page_extraction()
