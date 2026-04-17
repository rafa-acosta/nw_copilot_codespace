import unittest
from pathlib import Path

from rag_data_ingestion.pdf_loader import PDFLoader


class PDFLoaderTests(unittest.TestCase):
    def test_load_recovers_spacing_for_pdfs_with_tight_tj_offsets(self) -> None:
        source = (
            Path(__file__).resolve().parent.parent
            / "testing_files"
            / "PDF"
            / "EvMateo.pdf"
        )

        data = PDFLoader().load(str(source))

        self.assertIn("llenos de huesos de muertos y de podredumbre", data.content)
        self.assertIn("por fuera la copa y el plato", data.content.casefold())
        self.assertIn("que os he mandado", data.content.casefold())
        self.assertNotIn("llenosdehuesosdemuertosydepodredumbre", data.content)


if __name__ == "__main__":
    unittest.main()
