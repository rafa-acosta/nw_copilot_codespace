"""
Example 4: Loading Microsoft Office Documents

Demonstrates loading DOCX (Word) and XLSX (Excel) files
for RAG preprocessing.
"""

from rag_data_ingestion import DocxLoader, ExcelLoader


def example_docx_basic_loading():
    """Load text from Word documents."""
    loader = DocxLoader()
    
    # Assumes 'document.docx' exists
    # data = loader.load('document.docx', extract_tables=True)
    # print(f"Content preview: {data.content[:300]}")
    # print(f"Metadata: {data.source.metadata}")
    print("Example: Basic DOCX loading")
    print("Uncomment code above with actual DOCX path to run")


def example_docx_table_handling():
    """Extract tables from Word documents."""
    loader = DocxLoader()
    
    # With table extraction (default)
    # data = loader.load('document.docx', extract_tables=True)
    # Check for table markers in content
    # if '--- Table' in data.content:
    #     print("Tables found in document")
    
    # Without table extraction
    # data = loader.load('document.docx', extract_tables=False)
    # print("Loaded without table content")
    print("Example: DOCX table handling")
    print("Uncomment code above with actual DOCX path to run")


def example_excel_sheet_loading():
    """Load all sheets from Excel workbook."""
    loader = ExcelLoader()
    
    # Load all sheets
    # data = loader.load('spreadsheet.xlsx')
    # print(f"Content preview:\n{data.content[:300]}")
    # print(f"Sheet count: {data.source.metadata['sheet_count']}")
    # print(f"Sheets: {data.source.metadata['sheets']}")
    print("Example: Excel sheet loading")
    print("Uncomment code above with actual XLSX path to run")


def example_excel_specific_sheets():
    """Load specific sheets from Excel workbook."""
    loader = ExcelLoader()
    
    # Load only specific sheets
    # data = loader.load(
    #     'spreadsheet.xlsx',
    #     sheet_names=['Sheet1', 'Summary']
    # )
    # print("Loaded specific sheets")
    # print(f"Sheets loaded: {data.source.metadata['sheets']}")
    print("Example: Excel specific sheet loading")
    print("Uncomment code above with actual XLSX path to run")


def example_excel_with_empty_cells():
    """Include or exclude empty cells in Excel processing."""
    loader = ExcelLoader()
    
    # Include empty cells (marked as [EMPTY])
    # data_with_empty = loader.load(
    #     'spreadsheet.xlsx',
    #     include_empty_cells=True
    # )
    
    # Exclude empty cells (default)
    # data_without_empty = loader.load(
    #     'spreadsheet.xlsx',
    #     include_empty_cells=False
    # )
    print("Example: Excel empty cell handling")
    print("Uncomment code above with actual XLSX path to run")


if __name__ == "__main__":
    print("=" * 60)
    print("RAG Data Ingestion - Example 4: Office Documents")
    print("=" * 60)
    
    example_docx_basic_loading()
    print()
    example_docx_table_handling()
    print()
    example_excel_sheet_loading()
    print()
    example_excel_specific_sheets()
    print()
    example_excel_with_empty_cells()
