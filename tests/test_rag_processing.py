import unittest

from rag_processing.models import CleanDocument
from rag_processing.pipeline import DocumentPipeline


class TestRagProcessingPipeline(unittest.TestCase):
    def test_text_pipeline(self):
        doc = CleanDocument(
            document_id="doc1",
            source_type="text",
            source="memory://text",
            content="Para one.\n\nPara two with more content.",
            metadata={},
        )
        pipeline = DocumentPipeline(max_size=200, overlap=20)
        chunks = pipeline.run(doc)
        self.assertTrue(len(chunks) >= 1)
        self.assertEqual(chunks[0].metadata.source_type, "text")

    def test_pdf_pipeline(self):
        content = "--- Page 1 ---\nBlock one on page one.\n\nBlock two.\n--- Page 2 ---\nSecond page block."
        doc = CleanDocument(
            document_id="doc2",
            source_type="pdf",
            source="memory://pdf",
            content=content,
            metadata={},
        )
        pipeline = DocumentPipeline(max_size=200, overlap=20)
        chunks = pipeline.run(doc)
        self.assertTrue(any(chunk.metadata.page == 1 for chunk in chunks))
        self.assertTrue(any(chunk.metadata.page == 2 for chunk in chunks))

    def test_web_pipeline(self):
        content = "Title\nThis is an intro.\n\nHeading One\nDetails under heading one."
        doc = CleanDocument(
            document_id="doc3",
            source_type="web",
            source="memory://web",
            content=content,
            metadata={},
        )
        pipeline = DocumentPipeline(max_size=200, overlap=20)
        chunks = pipeline.run(doc)
        self.assertTrue(len(chunks) >= 1)
        self.assertEqual(chunks[0].metadata.content_type, "section")

    def test_docx_pipeline(self):
        content = "Document Title\nParagraph one.\n\nSection One\nParagraph two."
        doc = CleanDocument(
            document_id="doc4",
            source_type="docx",
            source="memory://docx",
            content=content,
            metadata={},
        )
        pipeline = DocumentPipeline(max_size=200, overlap=20)
        chunks = pipeline.run(doc)
        self.assertTrue(len(chunks) >= 1)

    def test_excel_pipeline(self):
        content = "--- Sheet: Sheet1 ---\nA | B | C\n1 | 2 | 3\n--- Sheet: Sheet2 ---\nX | Y | Z"
        doc = CleanDocument(
            document_id="doc5",
            source_type="excel",
            source="memory://excel",
            content=content,
            metadata={},
        )
        pipeline = DocumentPipeline(max_size=200, overlap=0)
        chunks = pipeline.run(doc)
        self.assertTrue(any(chunk.metadata.sheet == "Sheet1" for chunk in chunks))

    def test_json_pipeline(self):
        content = "user.name: Alice\nuser.age: 30\nitems[0].id: 1"
        doc = CleanDocument(
            document_id="doc6",
            source_type="json",
            source="memory://json",
            content=content,
            metadata={},
        )
        pipeline = DocumentPipeline(max_size=200, overlap=20)
        chunks = pipeline.run(doc)
        self.assertTrue(any(chunk.metadata.json_path for chunk in chunks))

    def test_cisco_pipeline(self):
        content = "hostname TEST\ninterface GigabitEthernet1\n description WAN\nrouter bgp 65001\n neighbor 1.1.1.1 remote-as 65002"
        doc = CleanDocument(
            document_id="doc7",
            source_type="cisco",
            source="memory://cisco",
            content=content,
            metadata={},
        )
        pipeline = DocumentPipeline(max_size=200, overlap=10)
        chunks = pipeline.run(doc)
        self.assertTrue(any(chunk.metadata.cisco_block_type for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
