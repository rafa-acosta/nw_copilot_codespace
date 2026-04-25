# IMPORTS
from pathlib import Path

from rag_data_ingestion import (
    TextFileLoader,
    PDFLoader,
    DocxLoader,
    WebLoader,
    CiscoConfigLoader,
)

from rag_processing import (
    # add imports as needed for testing
    DocumentPipeline,
    CleanDocument,

)

# UTILS

TESTING_FILES_DIR = Path(__file__).resolve().parent / "testing_files"

# FUNCTIONS DEFINITIONS

def ciscoTester():
    print("Testing Cisco Config Loader...")        
    routerloader = CiscoConfigLoader()
    router_data = routerloader.load('/home/rafa/Documents/AIML/Projects/nw-copilot-3-pipelines-v1/nw_copilot_codespace/testing_files/Cisco/Cisco 3750 v2.txt')
    print(f"Loaded Cisco config content:\n{router_data.content[:500]}...\n")



def loadFactory():
    print('RUNNING TESTS FOR ALL LOADERS USING FACTORY')
    from rag_data_ingestion import LoaderFactory

    files = [
        (TESTING_FILES_DIR / "txt" / "gibson.txt", "text"),
        (TESTING_FILES_DIR / "Word" / "EvMateo.docx", "docx"),
        (TESTING_FILES_DIR / "Cisco" / "Cisco 3750 v2.txt", "cisco"),
    ]
    result = [ ]

    for path, file_type in files:
        print(f"Testing loader for file: {path} of type: {file_type}\n\n")
        loader = LoaderFactory.get_loader(file_type)
        ingested = loader.load(str(path))
        clean_doc = CleanDocument.from_ingested(ingested)
        pipeline = DocumentPipeline(max_size=1200, overlap=150)
        chunks = pipeline.run(clean_doc)
        result.append((file_type, len(chunks), chunks[0].metadata, chunks[0].content[:500]))

    for file_type, num_chunks, metadata, content_sample in result:
        print(f"File type: {file_type}\n\n, Number of chunks: {num_chunks}\n\n, Metadata: {metadata}\n\n, Content sample:\n\n {content_sample}...\n\n")




# MAIN TESTER FILE FOR RAM CODE
if __name__ == "__main__":
    print("Running tests...")
    #ciscoTester()
    loadFactory()
