print("This is a simple example of a Python script that prints 'Hello, World!' to the console.\n\n")

from rag_data_ingestion import TextFileLoader, TextCleaner,PDFLoader, DocxLoader,WebLoader


def example_custom_text_cleaning():
    """Text loading with custom cleaning configuration."""
    # Create a custom cleaner that keeps structure
    cleaner = TextCleaner(
        normalize_unicode_chars=True,
        remove_extra_spaces=True,
        lowercase=True,  # Keep original case
        expand_contracs=True,
        remove_urls_flag=True,
        remove_emails_flag=True,
        keep_punctuation=True,
    )
    
    loader = TextFileLoader(cleaner=cleaner)
    
    data = loader.load('/workspaces/nw_copilot_codespace/testing_files/huracan.txt', encoding='utf-8')
    print(f"Cleaned content:\n\n{data.content}")
    print('='*100)
    print("Example: Custom text cleaning")
    print("Uncomment code above with actual file path to run")

def procesadorPDF():
    try:
        loader = PDFLoader()
    except ImportError as e:
        print("ERROR: PDF support dependency missing:", e)
        print("Install it in your active environment with: python -m pip install PyPDF2")
        return

    data = loader.load('/workspaces/nw_copilot_codespace/testing_files/HIPOTECA 90 MILLONES.pdf', extract_metadata=True)
    print(f"Content preview: {data.content[:1000]}")
    print(f"PDF Metadata: {data.source.metadata}")




def procesadorURLs():
    try:
        loader = WebLoader()
    except ImportError as e:
        print("ERROR: Web support dependency missing:", e)
        print("Install it in your active environment with: python -m pip install requests beautifulsoup4")
        return

    data = loader.load('https://rafa-acosta.com/')
    print(f"Content preview: {data.content[:1000]}")
    print(f"Metadata: {data.source.metadata}")

# ===========================================================================================================================================
# ===========================================================================================================================================


if __name__ == "__main__":
    #example_custom_text_cleaning()
    procesadorURLs()