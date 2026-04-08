# IMPORTS
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

path_prefix = "/home/rafa/Documents/AIML/Projects/nw-copilot-3-pipelines-v1/nw_copilot_codespace/testing_files/"

# FUNCTIONS DEFINITIONS

def ciscoTester():
    print("Testing Cisco Config Loader...")        
    routerloader = CiscoConfigLoader()
    router_data = routerloader.load('/home/rafa/Documents/AIML/Projects/nw-copilot-3-pipelines-v1/nw_copilot_codespace/testing_files/Cisco 3750 v2.txt')
    print(f"Loaded Cisco config content:\n{router_data.content[:500]}...\n")


def loadFactory():
    print('RUNNING TESTS FOR ALL LOADERS USING FACTORY')
    from rag_data_ingestion import LoaderFactory

    files = [(path_prefix + "gibson.txt",'text'),(path_prefix + "EvMateo.docx",'docx'),(path_prefix + 'Cisco 3750 v2.txt','cisco')]
    result = [ ]

    for path, file_type in files:
        loader = LoaderFactory.get_loader(file_type)
        ingested = loader.load(path)
        clean_doc = CleanDocument.from_ingested(ingested)
        pipeline = DocumentPipeline(max_size=1200, overlap=150)
        chunks = pipeline.run(clean_doc)
        result.append((file_type, len(chunks), chunks[0].metadata))

    for file_type, num_chunks, metadata in result:
        print(f"File type: {file_type}, Number of chunks: {num_chunks}, Metadata: {metadata}")




# MAIN TESTER FILE FOR RAM CODE
if __name__ == "__main__":
    print("Running tests...")
    #ciscoTester()
    loadFactory()