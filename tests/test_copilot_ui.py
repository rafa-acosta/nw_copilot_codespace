import base64
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from copilot_ui.answers import GroundedAnswerGenerator, OllamaAnswerGenerator
from copilot_ui.embeddings import HashingEmbeddingModel, OllamaEmbeddingModel
from copilot_ui.models import UploadedFilePayload
from copilot_ui.ollama import FIXED_OLLAMA_MODEL, OllamaClient
from copilot_ui.services import CopilotApplicationService, QueryOptions
from retrieval.models import RetrievalResponse, RetrievedChunk, RetrievalTiming


def encode_text_payload(name: str, content: str) -> UploadedFilePayload:
    return UploadedFilePayload(
        name=name,
        content_base64=base64.b64encode(content.encode("utf-8")).decode("utf-8"),
    )


class CopilotApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = CopilotApplicationService(
            storage_dir=self.temp_dir.name,
            embedding_model=HashingEmbeddingModel(),
            answer_generator=GroundedAnswerGenerator(),
        )

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

    def test_upload_keeps_text_files_when_pdf_dependency_is_missing(self) -> None:
        snapshot = self.service.add_uploaded_files(
            [
                encode_text_payload("notes.txt", "Project note about hurricane evacuation procedures."),
                UploadedFilePayload(
                    name="missing_dependency.pdf",
                    content_base64=base64.b64encode(b"%PDF-1.4\n% test pdf").decode("utf-8"),
                ),
            ]
        )

        self.assertEqual(len(snapshot.documents), 1)
        self.assertEqual(snapshot.documents[0].filename, "notes.txt")
        self.assertTrue(snapshot.retrieval_ready)
        self.assertIsNotNone(self.service.last_upload_message())
        self.assertIn("missing_dependency.pdf", self.service.last_upload_message())
        self.assertIn("PyPDF2 is required for PDF loading", self.service.last_upload_message())


class FakeResponse:
    def __init__(self, payload: dict, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)

    def json(self) -> dict:
        return self._payload


class FakeOllamaClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        chat_model: str = FIXED_OLLAMA_MODEL,
        embedding_model: str = FIXED_OLLAMA_MODEL,
        available_models: tuple[str, ...] | None = None,
    ) -> None:
        self.base_url = base_url
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.timeout_seconds = 30.0
        self.available_models = available_models or (
            FIXED_OLLAMA_MODEL,
            "phi3.5:latest",
        )

    def with_models(self, *, chat_model: str | None = None, embedding_model: str | None = None):
        return FakeOllamaClient(
            base_url=self.base_url,
            chat_model=chat_model or self.chat_model,
            embedding_model=embedding_model or self.embedding_model,
            available_models=self.available_models,
        )

    def list_models(self) -> tuple[str, ...]:
        return tuple(self.available_models)

    def embed_documents(self, texts):
        seed = float(sum(ord(char) for char in self.embedding_model) % 11 + 1)
        return [
            (seed, float(len(text) % 7 + 1), float(index + 1))
            for index, text in enumerate(texts)
        ]

    def embed_query(self, text: str):
        return self.embed_documents([text])[0]

    def chat(self, messages, *, temperature: float = 0.1) -> str:
        del messages, temperature
        return f"Answer generated by {self.chat_model}."


class OllamaIntegrationTests(unittest.TestCase):
    def test_from_env_uses_fixed_llama_model(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OLLAMA_CHAT_MODEL": "should-not-be-used",
                "OLLAMA_EMBED_MODEL": "should-not-be-used",
            },
            clear=False,
        ):
            client = OllamaClient.from_env()

        self.assertEqual(client.chat_model, FIXED_OLLAMA_MODEL)
        self.assertEqual(client.embedding_model, FIXED_OLLAMA_MODEL)

    def test_snapshot_reports_missing_fixed_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CopilotApplicationService(
                storage_dir=temp_dir,
                ollama_client=FakeOllamaClient(available_models=("phi3.5:latest",)),
            )

            snapshot = service.snapshot()

        self.assertIsNotNone(snapshot.ollama)
        self.assertEqual(snapshot.ollama.chat_model, FIXED_OLLAMA_MODEL)
        self.assertEqual(snapshot.ollama.embedding_model, FIXED_OLLAMA_MODEL)
        self.assertIn(FIXED_OLLAMA_MODEL, snapshot.ollama.last_error)

    def test_txt_upload_and_answer_uses_fixed_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CopilotApplicationService(
                storage_dir=temp_dir,
                ollama_client=FakeOllamaClient(),
            )
            snapshot = service.add_uploaded_files(
                [
                    encode_text_payload(
                        "notes.txt",
                        "Backup window starts every Sunday at 02:00 and ends at 03:00.",
                    )
                ]
            )
            answer_state = service.ask("When does the backup window start?")

        self.assertTrue(snapshot.retrieval_ready)
        self.assertEqual(snapshot.documents[0].source_type, "text_file")
        self.assertEqual(answer_state.messages[-1].meta["answer_model"], FIXED_OLLAMA_MODEL)
        self.assertTrue(answer_state.messages[-1].citations)
        self.assertEqual(answer_state.messages[-1].citations[0].source_type, "text_file")

    def test_ollama_embedding_model_uses_batch_embed_endpoint(self) -> None:
        session = Mock()
        session.request.return_value = FakeResponse(
            {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}
        )
        client = OllamaClient(session=session)
        model = OllamaEmbeddingModel(client=client)

        embeddings = model.embed_documents(["alpha", "beta"])

        self.assertEqual(
            embeddings,
            [(0.1, 0.2, 0.3), (0.4, 0.5, 0.6)],
        )
        session.request.assert_called_once()
        self.assertEqual(
            session.request.call_args.kwargs["json"],
            {"model": client.embedding_model, "input": ["alpha", "beta"]},
        )

    def test_ollama_embedding_model_falls_back_to_legacy_endpoint(self) -> None:
        session = Mock()
        session.request.side_effect = [
            FakeResponse({"error": "missing endpoint"}, status_code=404),
            FakeResponse({"embedding": [1.0, 0.0]}),
            FakeResponse({"embedding": [0.0, 1.0]}),
        ]
        client = OllamaClient(session=session)

        embeddings = client.embed_documents(["first", "second"])

        self.assertEqual(embeddings, [(1.0, 0.0), (0.0, 1.0)])
        self.assertEqual(session.request.call_count, 3)
        self.assertEqual(
            session.request.call_args_list[1].kwargs["json"],
            {"model": client.embedding_model, "prompt": "first"},
        )
        self.assertEqual(
            session.request.call_args_list[2].kwargs["json"],
            {"model": client.embedding_model, "prompt": "second"},
        )

    def test_ollama_answer_generator_uses_grounded_context_and_attaches_citations(self) -> None:
        class FakeChatClient:
            chat_model = FIXED_OLLAMA_MODEL

            def __init__(self) -> None:
                self.messages = ()

            def chat(self, messages, *, temperature: float = 0.1) -> str:
                self.messages = tuple(messages)
                return "The interface is GigabitEthernet1/0/24 and it is up. [device.json • device.interfaces]"

        retrieval_response = RetrievalResponse(
            original_query="What interface is up?",
            normalized_query="what interface is up",
            retrieval_mode="hybrid",
            top_k_results=1,
            results=(
                RetrievedChunk(
                    chunk_id="chunk_1",
                    text='{"device":{"interfaces":[{"name":"GigabitEthernet1/0/24","status":"up"}]}}',
                    score=0.98,
                    metadata={
                        "filename": "device.json",
                        "json_key_path": "device.interfaces",
                    },
                    source_type="json",
                ),
            ),
            timings=RetrievalTiming(total_ms=12.5),
        )
        client = FakeChatClient()
        generator = OllamaAnswerGenerator(client=client)

        answer = generator.generate("What interface is up?", retrieval_response)

        self.assertIn("GigabitEthernet1/0/24", answer.content)
        self.assertEqual(answer.meta["answer_provider"], "ollama")
        self.assertEqual(answer.meta["answer_model"], FIXED_OLLAMA_MODEL)
        self.assertEqual(answer.citations[0].label, "device.json • device.interfaces")
        self.assertEqual(client.messages[0]["role"], "system")
        self.assertIn("Question: What interface is up?", client.messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
