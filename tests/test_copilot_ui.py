import base64
import json
import tempfile
import unittest

from copilot_ui.services import CopilotApplicationService, QueryOptions
from copilot_ui.models import UploadedFilePayload


def encode_text_payload(name: str, content: str) -> UploadedFilePayload:
    return UploadedFilePayload(
        name=name,
        content_base64=base64.b64encode(content.encode("utf-8")).decode("utf-8"),
    )


class CopilotApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = CopilotApplicationService(storage_dir=self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_upload_and_retrieve_json_document(self) -> None:
        payloads = [
            encode_text_payload(
                "network.txt",
                "interface GigabitEthernet1/0/24\n switchport trunk allowed vlan 10,20,30\n spanning-tree portfast trunk\n",
            ),
            encode_text_payload(
                "device.json",
                json.dumps(
                    {
                        "device": {
                            "interfaces": [
                                {"name": "GigabitEthernet1/0/24", "status": "up"},
                            ]
                        }
                    }
                ),
            ),
        ]

        snapshot = self.service.add_uploaded_files(payloads)
        self.assertTrue(snapshot.retrieval_ready)
        self.assertEqual(len(snapshot.documents), 2)
        self.assertGreater(snapshot.chunk_count, 0)

        state = self.service.ask(
            "What is device.interfaces[0].name?",
            QueryOptions(mode="hybrid", top_k=3, source_types=("json",)),
        )
        self.assertEqual(state.messages[-1].role, "assistant")
        self.assertTrue(state.messages[-1].citations)
        self.assertEqual(state.messages[-1].citations[0].source_type, "json")

    def test_remove_document_updates_index(self) -> None:
        snapshot = self.service.add_uploaded_files(
            [encode_text_payload("notes.txt", "Project note about hurricane evacuation procedures.")]
        )
        document_id = snapshot.documents[0].document_id
        updated = self.service.remove_document(document_id)
        self.assertFalse(updated.documents)
        self.assertEqual(updated.chunk_count, 0)
        self.assertFalse(updated.retrieval_ready)


if __name__ == "__main__":
    unittest.main()
