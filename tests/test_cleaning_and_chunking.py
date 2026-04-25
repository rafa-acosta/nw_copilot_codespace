import unittest

from rag_data_ingestion.cleaning import TextCleaner
from rag_processing.models import CleanDocument
from rag_processing.pipeline import DocumentPipeline
from rag_processing.utils import chunk_units


class TestCleaningAndChunking(unittest.TestCase):
    def test_cleaner_preserves_rag_relevant_technical_syntax(self):
        cleaner = TextCleaner()

        cleaned = cleaner.clean(
            "Interface Gi1/0/24 -> VLAN 10, IP 10.10.0.0/24, "
            "json path device.interfaces[0].name, price=$10 #tag"
        )

        self.assertIn("Gi1/0/24", cleaned)
        self.assertIn("10.10.0.0/24", cleaned)
        self.assertIn("device.interfaces[0].name", cleaned)
        self.assertIn("$10", cleaned)
        self.assertIn("#tag", cleaned)

    def test_ocr_prose_cleaner_repairs_common_digit_letter_errors(self):
        cleaner = TextCleaner.for_ocr_prose()

        cleaned = cleaner.clean("Gibs0n m0del spec shee t may inc1ude sca1e fin1sh")

        self.assertIn("Gibson", cleaned)
        self.assertIn("model", cleaned)
        self.assertIn("spec sheet", cleaned.casefold())
        self.assertIn("include", cleaned)
        self.assertIn("scale", cleaned)
        self.assertIn("finish", cleaned)

    def test_network_cleaner_does_not_repair_technical_numbers(self):
        cleaner = TextCleaner.for_network_config()

        cleaned = cleaner.clean("interface Gi1/0/24\n ip address 10.10.0.1 255.255.255.0")

        self.assertIn("Gi1/0/24", cleaned)
        self.assertIn("10.10.0.1", cleaned)

    def test_chunk_overlap_uses_complete_units_when_possible(self):
        chunks = chunk_units(
            [
                "Paragraph one has enough text to matter.",
                "Paragraph two should become the overlap.",
                "Paragraph three starts the next chunk.",
            ],
            max_size=90,
            overlap=45,
        )

        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(chunks[1].startswith("Paragraph two should become the overlap."))

    def test_cisco_section_markers_do_not_become_chunk_content(self):
        document = CleanDocument(
            document_id="doc-cisco",
            source_type="cisco_config",
            source="memory://cisco",
            content=(
                "--- Cisco Section: general ---\n"
                "hostname Switch\n"
                "--- Cisco Section: interface GigabitEthernet1/0/1 ---\n"
                "interface GigabitEthernet1/0/1\n"
                " description Uplink\n"
            ),
            metadata={},
        )

        chunks = DocumentPipeline(max_size=200, overlap=0).run(document)

        self.assertTrue(chunks)
        self.assertNotIn("Cisco Section", chunks[0].content)
        self.assertNotEqual(chunks[0].content.splitlines()[0], "general")


if __name__ == "__main__":
    unittest.main()
