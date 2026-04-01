from pathlib import Path

from rag_data_ingestion import (
    TextFileLoader,
    TextCleaner,
    PDFLoader,
    DocxLoader,
    WebLoader,
    CiscoConfigLoader,
)
from rag_processing import CleanDocument, DocumentPipeline


print("This is a simple example of a Python script that prints 'Hello, World!' to the console.\n\n")


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
    
    data = loader.load(str(_testing_file("huracan.txt")), encoding='utf-8')
    print(f"Cleaned content:\n\n{data.content}")
    print('='*100)
    print("Example: Custom text cleaning")
    print("Uncomment code above with actual file path to run")
    return data.content

def procesadorPDF():
    try:
        loader = PDFLoader()
    except ImportError as e:
        print("ERROR: PDF support dependency missing:", e)
        print("Install it in your active environment with: python -m pip install PyPDF2")
        return

    data = loader.load(str(_testing_file("HIPOTECA 90 MILLONES.pdf")), extract_metadata=True)
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

def ciscoPassRedactor():
    """Demonstrate sensitive data redaction in Cisco configs."""
    loader = CiscoConfigLoader()
    
    # Passwords and secrets are redacted by default
    data = loader.load(str(_testing_file("Configuration Template 2.txt")), redact_sensitive=True)
    # Passwords will appear as:
    # enable password [REDACTED]
    # snmp-server community [REDACTED]
    # print("Configuration with redacted sensitive data")
    print(data.content)
    print("Example: Cisco config with sensitive data redaction")
    print("Uncomment code above with actual config to run")

# ===========================================================================================================================================
# ===========================================================================================================================================


def _testing_file(filename: str) -> Path:
    base_dir = Path(__file__).resolve().parent
    return base_dir / "testing_files" / filename


def procesadorTextoConRag() -> None:
    loader = TextFileLoader()
    ingested = loader.load(str(_testing_file("gibson.txt")))
    clean_doc = CleanDocument.from_ingested(ingested)
    pipeline = DocumentPipeline(max_size=1200, overlap=150)
    chunks = pipeline.run(clean_doc)
    print(f"Total chunks: {len(chunks)}\n")
    print("="*100)
    print("="*100)
    print(f"First chunk preview: {chunks[0].content[:500]}\n")
    print("="*100)
    print("="*100)
    print(f"Metadata: {chunks[0].metadata}\n")
    print(f'Largo de la lista chunks: {len(chunks)}\n')
    print("="*100)
    print("="*100)
    print(chunks[3001].content)
    
def procesadorDocx():
    loader = DocxLoader()
    ingested = loader.load(str(_testing_file("EvMateo.docx")))
    clean_doc = CleanDocument.from_ingested(ingested)
    pipeline = DocumentPipeline(max_size=1200, overlap=150)
    chunks = pipeline.run(clean_doc)
    print(f"Total chunks: {len(chunks)}\n")
    print("="*100)
    print("="*100)
    print(f"First chunk preview: {chunks[50].content[:500]}\n")
    print("="*100)
    print("="*100)
    print(f"Metadata: {chunks[0].metadata}\n")

def procesadorPDF():
    loader = PDFLoader()
    ingested = loader.load(str(_testing_file("HIPOTECA 90 MILLONES.pdf")), extract_metadata=True)
    clean_doc = CleanDocument.from_ingested(ingested)
    pipeline = DocumentPipeline(max_size=1200, overlap=150)
    chunks = pipeline.run(clean_doc)
    print(f"Total chunks: {len(chunks)}\n")
    print("="*100)
    print("="*100)
    print(f"First chunk preview: {chunks[0].content[:500]}\n")
    print("="*100)
    print("="*100)
    print(f"Metadata: {chunks[0].metadata}\n")

def procesadorCiscoConfig():
    loader = CiscoConfigLoader()
    ingested = loader.load(str(_testing_file("Configuration Template 2.txt")), redact_sensitive=True)
    clean_doc = CleanDocument.from_ingested(ingested)
    pipeline = DocumentPipeline(max_size=1200, overlap=150)
    chunks = pipeline.run(clean_doc)
    print(f"Total chunks: {len(chunks)}\n")
    print("="*100)
    print("="*100)
    print(f"First chunk preview: {chunks[0].content[:500]}\n")
    print("="*100)
    print("="*100)
    print(f"Metadata: {chunks[0].metadata}\n")

if __name__ == "__main__":
    # example_custom_text_cleaning()
    # procesadorPDF()
    # procesadorURLs()
    # ciscoPassRedactor()
    #procesadorTextoConRag()
    #procesadorDocx()
    #procesadorPDF()
    procesadorCiscoConfig()