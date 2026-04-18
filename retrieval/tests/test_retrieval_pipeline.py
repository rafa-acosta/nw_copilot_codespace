import unittest
import tempfile

from retrieval import (
    CallableQueryEmbedder,
    ChunkMetadata,
    MetadataFilterSpec,
    RetrievalConfig,
    RetrievalMode,
    RetrievalRequest,
    StoredChunk,
)
from retrieval.models import NumericRange
from retrieval.services import build_retrieval_service


VOCABULARY = (
    "hurricane",
    "evacuation",
    "policy",
    "page",
    "section",
    "revenue",
    "sheet",
    "customer",
    "status",
    "interface",
    "switchport",
    "vlan",
    "gigabitethernet1/0/24",
    "10.0.0.1",
    "device.interfaces[0].name",
)


def embed_text(text: str) -> list[float]:
    lowered = text.casefold()
    return [float(lowered.count(term)) for term in VOCABULARY]


class RetrievalPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        records = [
            StoredChunk(
                text="Hurricane preparedness checklist and evacuation procedures for coastal regions.",
                embedding=tuple(embed_text("hurricane evacuation coastal checklist")),
                metadata=ChunkMetadata(
                    document_id="doc-text-1",
                    source_type="text",
                    file_path="/data/docs/hurricane.txt",
                    filename="hurricane.txt",
                    chunk_id="chunk-text-1",
                    tags=("weather", "safety"),
                ),
            ),
            StoredChunk(
                text="Revenue by quarter for LATAM operations.\nQuarter | Revenue | Region\nQ1 | 120000 | LATAM",
                embedding=tuple(embed_text("revenue sheet quarter latam")),
                metadata=ChunkMetadata(
                    document_id="doc-xlsx-1",
                    source_type="excel",
                    file_path="/data/docs/finance.xlsx",
                    filename="finance.xlsx",
                    chunk_id="chunk-xlsx-1",
                    sheet_name="QuarterlySummary",
                    row_start=1,
                    row_end=2,
                    column_names=("Quarter", "Revenue", "Region"),
                    tags=("finance",),
                ),
            ),
            StoredChunk(
                text="device.interfaces[0].name: GigabitEthernet1/0/24\ndevice.interfaces[0].status: up",
                embedding=tuple(embed_text("customer device.interfaces[0].name status interface")),
                metadata=ChunkMetadata(
                    document_id="doc-json-1",
                    source_type="json",
                    file_path="/data/docs/device.json",
                    filename="device.json",
                    chunk_id="chunk-json-1",
                    json_key_path="device.interfaces[0]",
                    tags=("inventory",),
                ),
            ),
            StoredChunk(
                text="Page 12 describes the security policy escalation path for privileged access.",
                embedding=tuple(embed_text("page policy access")),
                metadata=ChunkMetadata(
                    document_id="doc-pdf-1",
                    source_type="pdf",
                    file_path="/data/docs/security.pdf",
                    filename="security.pdf",
                    chunk_id="chunk-pdf-1",
                    page_number=12,
                    tags=("security",),
                ),
            ),
            StoredChunk(
                text="Incident Response Section\nEscalation policy and responsibilities for NOC operators.",
                embedding=tuple(embed_text("section policy noc operators")),
                metadata=ChunkMetadata(
                    document_id="doc-docx-1",
                    source_type="docx",
                    file_path="/data/docs/runbook.docx",
                    filename="runbook.docx",
                    chunk_id="chunk-docx-1",
                    section="Incident Response",
                    tags=("runbook",),
                ),
            ),
            StoredChunk(
                text="interface GigabitEthernet1/0/24\n switchport trunk allowed vlan 10,20,30\n spanning-tree portfast trunk",
                embedding=tuple(embed_text("interface switchport vlan gigabitethernet1/0/24")),
                metadata=ChunkMetadata(
                    document_id="doc-cisco-1",
                    source_type="cisco_config",
                    file_path="/data/configs/switch.cfg",
                    filename="switch.cfg",
                    chunk_id="chunk-cisco-1",
                    cisco_feature="interface",
                    cisco_section="GigabitEthernet1/0/24",
                    tags=("network", "switch"),
                ),
            ),
        ]

        config = RetrievalConfig()
        config.observability.debug = True
        embedder = CallableQueryEmbedder(embed_text, expected_dimension=len(VOCABULARY))
        self.service = build_retrieval_service(
            records,
            query_embedder=embedder,
            config=config,
            chroma_path=f"{self.temp_dir.name}/chroma",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_query_processor_preserves_technical_terms(self) -> None:
        processed = self.service.query_processor.process(
            "Check device.interfaces[0].name for GigabitEthernet1/0/24 and IP 10.0.0.1"
        )
        self.assertIn("device.interfaces[0].name", processed.technical_terms)
        self.assertTrue(any(term.lower().startswith("gigabitethernet1/0/24") for term in processed.technical_terms))
        self.assertIn("10.0.0.1", processed.technical_terms)

    def test_hybrid_prefers_exact_cisco_command_match(self) -> None:
        response = self.service.retrieve(
            RetrievalRequest(
                query="switchport trunk allowed vlan 10,20,30 on interface GigabitEthernet1/0/24",
                mode=RetrievalMode.HYBRID,
                top_k=3,
                debug=True,
            )
        )
        self.assertEqual(response.results[0].metadata["source_type"], "cisco_config")
        self.assertEqual(response.results[0].chunk_id, "chunk-cisco-1")
        self.assertGreaterEqual(response.results[0].keyword_score or 0.0, 0.0)

    def test_metadata_filter_limits_results(self) -> None:
        response = self.service.retrieve(
            RetrievalRequest(
                query="revenue by quarter",
                mode=RetrievalMode.HYBRID,
                top_k=3,
                filters=MetadataFilterSpec(
                    equals={"source_type": "excel"},
                    contains={"sheet_name": "Quarterly"},
                ),
            )
        )
        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].metadata["sheet_name"], "QuarterlySummary")

    def test_json_key_path_retrieval(self) -> None:
        response = self.service.retrieve(
            RetrievalRequest(
                query="device.interfaces[0].name status",
                mode=RetrievalMode.HYBRID,
                top_k=2,
            )
        )
        self.assertEqual(response.results[0].metadata["source_type"], "json")
        self.assertEqual(response.results[0].metadata["json_key_path"], "device.interfaces[0]")

    def test_pdf_page_range_filter(self) -> None:
        response = self.service.retrieve(
            RetrievalRequest(
                query="security policy page 12",
                mode=RetrievalMode.HYBRID,
                top_k=2,
                filters=MetadataFilterSpec(
                    equals={"source_type": "pdf"},
                    numeric_ranges={"page_number": NumericRange(minimum=12, maximum=12)},
                ),
            )
        )
        self.assertEqual(response.results[0].metadata["page_number"], 12)


if __name__ == "__main__":
    unittest.main()
