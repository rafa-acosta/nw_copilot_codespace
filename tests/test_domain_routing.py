import base64
import tempfile
import unittest

from copilot_ui.answers import GroundedAnswerGenerator
from copilot_ui.embeddings import HashingEmbeddingModel
from copilot_ui.models import UploadedFilePayload
from copilot_ui.services import CopilotApplicationService, QueryOptions
from domain_routing import DomainClassifier
from rag_processing.models import CleanDocument
from rag_processing.pipeline import DocumentPipeline


def encode_payload(name: str, content: str) -> UploadedFilePayload:
    return UploadedFilePayload(
        name=name,
        content_base64=base64.b64encode(content.encode("utf-8")).decode("utf-8"),
    )


class DomainClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = DomainClassifier()

    def test_classifies_legal_document_from_filename_and_clauses(self) -> None:
        result = self.classifier.classify_document(
            source_type="docx",
            file_path="/tmp/nda_agreement.docx",
            content=(
                "CONFIDENTIALITY AGREEMENT\n"
                "WHEREAS the parties wish to exchange confidential information.\n"
                "Section 1. Term.\n"
                "Section 2. Governing Law.\n"
            ),
            metadata={"filename": "nda_agreement.docx"},
        )

        self.assertEqual(result.domain, "legal")
        self.assertGreater(result.confidence, 0.55)
        self.assertIn("governing law", result.reason.casefold())

    def test_classifies_medical_document_from_clinical_language(self) -> None:
        result = self.classifier.classify_document(
            source_type="text",
            file_path="/tmp/patient_note.txt",
            content=(
                "Chief Complaint: chest pain\n"
                "History of Present Illness: patient reports intermittent pain.\n"
                "Assessment: likely musculoskeletal.\n"
                "Plan: prescribe ibuprofen 400 mg and follow-up in 3 days.\n"
            ),
            metadata={"filename": "patient_note.txt"},
        )

        self.assertEqual(result.domain, "medical")
        self.assertGreater(result.confidence, 0.55)
        self.assertIn("chief complaint", result.reason.casefold())

    def test_classifies_cisco_document_from_config_structure(self) -> None:
        result = self.classifier.classify_document(
            source_type="text",
            file_path="/tmp/edge-switch.txt",
            content=(
                "hostname EDGE-SW1\n"
                "interface GigabitEthernet1/0/24\n"
                " switchport trunk allowed vlan 10,20,30\n"
                " spanning-tree portfast trunk\n"
                "router ospf 100\n"
            ),
            metadata={"filename": "edge-switch.txt"},
        )

        self.assertEqual(result.domain, "cisco")
        self.assertGreater(result.confidence, 0.60)
        self.assertIn("interface", result.reason.casefold())

    def test_classifies_general_document_when_specialist_signals_are_absent(self) -> None:
        result = self.classifier.classify_document(
            source_type="text",
            file_path="/tmp/project_update.txt",
            content=(
                "Project Update\n"
                "The team finished the migration checklist and shared next week's milestones.\n"
                "Outstanding work includes onboarding notes, budget tracking, and meeting follow-ups.\n"
            ),
            metadata={"filename": "project_update.txt"},
        )

        self.assertEqual(result.domain, "general")
        self.assertGreaterEqual(result.confidence, 0.55)
        self.assertIn("general", result.reason.casefold())


class DomainPipelinePropagationTests(unittest.TestCase):
    def test_pipeline_propagates_domain_metadata_to_chunks(self) -> None:
        pipeline = DocumentPipeline(max_size=240, overlap=20)
        document = CleanDocument(
            document_id="doc-legal-1",
            source_type="text",
            source="/tmp/mortgage_terms.txt",
            content=(
                "Mortgage Agreement\n"
                "WHEREAS the Borrower agrees to the terms below.\n"
                "Section 1. Payment Obligations.\n"
                "Section 2. Governing Law.\n"
            ),
            metadata={"filename": "mortgage_terms.txt"},
        )

        chunks = pipeline.run(document)

        self.assertTrue(chunks)
        self.assertEqual(document.metadata["domain"], "legal")
        self.assertTrue(all(chunk.metadata.extra["domain"] == "legal" for chunk in chunks))
        self.assertTrue(all("domain_reason" in chunk.metadata.extra for chunk in chunks))


class DomainRoutingIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = CopilotApplicationService(
            storage_dir=self.temp_dir.name,
            embedding_model=HashingEmbeddingModel(),
            answer_generator=GroundedAnswerGenerator(),
        )
        self.service.add_uploaded_files(
            [
                encode_payload(
                    "lease_agreement.txt",
                    (
                        "Lease Agreement\n"
                        "WHEREAS Tenant agrees to the payment schedule.\n"
                        "Section 4. Governing Law.\n"
                    ),
                ),
                encode_payload(
                    "patient_note.txt",
                    (
                        "Chief Complaint: headache\n"
                        "Blood pressure: 120/80\n"
                        "Assessment: mild dehydration.\n"
                        "Plan: increase fluids and prescribe acetaminophen 500 mg.\n"
                    ),
                ),
                encode_payload(
                    "core_switch.cfg",
                    (
                        "hostname CORE-SW1\n"
                        "interface GigabitEthernet1/0/24\n"
                        " switchport trunk allowed vlan 10,20,30\n"
                        " spanning-tree portfast trunk\n"
                    ),
                ),
                encode_payload(
                    "project_update.txt",
                    (
                        "Project Update\n"
                        "The migration checklist is complete.\n"
                        "Next we will review rollout timing, training notes, and open action items.\n"
                    ),
                ),
            ]
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_manual_override_restricts_retrieval_to_selected_domain(self) -> None:
        snapshot = self.service.ask(
            "What blood pressure is recorded?",
            QueryOptions(mode="hybrid", top_k=2, domain="medical"),
        )

        assistant_message = snapshot.messages[-1]
        self.assertEqual(assistant_message.meta["domain"], "medical")
        self.assertEqual(assistant_message.meta["domain_mode"], "manual")
        self.assertTrue(assistant_message.meta["domain_filter_applied"])
        self.assertTrue(assistant_message.citations)
        self.assertTrue(all(citation.metadata["domain"] == "medical" for citation in assistant_message.citations))

    def test_auto_routing_detects_cisco_query(self) -> None:
        snapshot = self.service.ask(
            "Which VLANs are allowed on interface GigabitEthernet1/0/24?",
            QueryOptions(mode="hybrid", top_k=2, domain="auto"),
        )

        assistant_message = snapshot.messages[-1]
        self.assertEqual(assistant_message.meta["domain"], "cisco")
        self.assertEqual(assistant_message.meta["domain_mode"], "automatic")
        self.assertTrue(assistant_message.meta["domain_filter_applied"])
        self.assertTrue(assistant_message.citations)
        self.assertTrue(all(citation.metadata["domain"] == "cisco" for citation in assistant_message.citations))

    def test_auto_routing_detects_general_query(self) -> None:
        snapshot = self.service.ask(
            "What does the project update say about the next steps?",
            QueryOptions(mode="hybrid", top_k=2, domain="auto"),
        )

        assistant_message = snapshot.messages[-1]
        self.assertEqual(assistant_message.meta["domain"], "general")
        self.assertEqual(assistant_message.meta["domain_mode"], "automatic")
        self.assertTrue(assistant_message.meta["domain_filter_applied"])
        self.assertTrue(assistant_message.citations)
        self.assertTrue(all(citation.metadata["domain"] == "general" for citation in assistant_message.citations))

    def test_manual_override_supports_general_domain(self) -> None:
        snapshot = self.service.ask(
            "Summarize the project update.",
            QueryOptions(mode="hybrid", top_k=2, domain="general"),
        )

        assistant_message = snapshot.messages[-1]
        self.assertEqual(assistant_message.meta["domain"], "general")
        self.assertEqual(assistant_message.meta["domain_mode"], "manual")
        self.assertTrue(assistant_message.meta["domain_filter_applied"])
        self.assertTrue(assistant_message.citations)
        self.assertTrue(all(citation.metadata["domain"] == "general" for citation in assistant_message.citations))


if __name__ == "__main__":
    unittest.main()
