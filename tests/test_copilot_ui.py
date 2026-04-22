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
from evaluation import RagasEvaluationResult, RagasMetricResult
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
        class MissingPdfLoader:
            def load(self, source: str, **kwargs):
                del source, kwargs
                raise ImportError("PyPDF2 is required for PDF loading. Install with: pip install PyPDF2")

        with patch("copilot_ui.loaders.PDFLoader", return_value=MissingPdfLoader()):
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

    def test_inspect_vector_records_returns_chunk_documents_and_embeddings(self) -> None:
        self.service.add_uploaded_files(
            [encode_text_payload("notes.txt", "Project note about hurricane evacuation procedures.")]
        )

        inspection = self.service.inspect_vector_records(limit=5, include_embeddings=True)

        self.assertEqual(inspection["collection_name"], "nw_copilot_chunks")
        self.assertGreaterEqual(inspection["total"], 1)
        self.assertTrue(inspection["records"])
        self.assertIn("hurricane evacuation procedures", inspection["records"][0]["document"])
        self.assertTrue(inspection["records"][0]["embedding"])

    def test_ragas_evaluation_is_demand_only(self) -> None:
        class FakeRagasEvaluator:
            def __init__(self) -> None:
                self.calls = []

            def evaluate(self, payload, *, metrics=None):
                self.calls.append((payload, metrics))
                return RagasEvaluationResult(
                    metrics=(RagasMetricResult(name="faithfulness", score=0.91),),
                    provider="fake",
                    model="fake-judge",
                    retrieved_context_count=len(payload.retrieved_contexts),
                )

        fake_evaluator = FakeRagasEvaluator()
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CopilotApplicationService(
                storage_dir=temp_dir,
                embedding_model=HashingEmbeddingModel(),
                answer_generator=GroundedAnswerGenerator(),
                ragas_evaluator=fake_evaluator,
            )
            service.add_uploaded_files(
                [encode_text_payload("notes.txt", "Project note about vlan 10 and interface status.")]
            )

            state = service.ask("What does the note mention?", QueryOptions(mode="hybrid", top_k=2))
            assistant_message = state.messages[-1]

            self.assertEqual(fake_evaluator.calls, [])
            self.assertTrue(assistant_message.meta["ragas_available"])
            self.assertFalse(assistant_message.meta["ragas_evaluated"])

            evaluated = service.evaluate_message(assistant_message.message_id)

        self.assertEqual(len(fake_evaluator.calls), 1)
        payload, metrics = fake_evaluator.calls[0]
        self.assertIsNone(metrics)
        self.assertEqual(payload.user_input, "What does the note mention?")
        self.assertIn("vlan 10", payload.retrieved_contexts[0])
        self.assertTrue(evaluated.messages[-1].meta["ragas_evaluated"])
        self.assertEqual(evaluated.messages[-1].meta["ragas"]["metrics"][0]["score"], 0.91)

    def test_ragas_evaluation_passes_reference_and_metric_selection(self) -> None:
        class FakeRagasEvaluator:
            def __init__(self) -> None:
                self.calls = []

            def evaluate(self, payload, *, metrics=None):
                self.calls.append((payload, metrics))
                return RagasEvaluationResult(
                    metrics=(RagasMetricResult(name="context_recall", score=1.0),),
                    provider="fake",
                    model="fake-judge",
                    reference_provided=bool(payload.reference),
                    retrieved_context_count=len(payload.retrieved_contexts),
                )

        fake_evaluator = FakeRagasEvaluator()
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CopilotApplicationService(
                storage_dir=temp_dir,
                embedding_model=HashingEmbeddingModel(),
                answer_generator=GroundedAnswerGenerator(),
                ragas_evaluator=fake_evaluator,
            )
            service.add_uploaded_files([encode_text_payload("notes.txt", "The interface status is up.")])
            state = service.ask("What is the interface status?", QueryOptions(mode="hybrid", top_k=1))

            evaluated = service.evaluate_message(
                state.messages[-1].message_id,
                reference="The interface status is up.",
                metrics=("context_recall",),
            )

        payload, metrics = fake_evaluator.calls[0]
        self.assertEqual(payload.reference, "The interface status is up.")
        self.assertEqual(metrics, ("context_recall",))
        self.assertTrue(evaluated.messages[-1].meta["ragas"]["reference_provided"])

    def test_ragas_env_config_takes_precedence_over_active_ollama_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CopilotApplicationService(
                storage_dir=temp_dir,
                ollama_client=FakeOllamaClient(
                    chat_model="qwen2.5-coder:7b-instruct",
                    embedding_model="nomic-embed-text",
                ),
            )

            with patch.dict(
                os.environ,
                {
                    "RAGAS_API_KEY": "test-key",
                    "RAGAS_LLM_MODEL": "gpt-4o-mini",
                    "RAGAS_EMBED_MODEL": "text-embedding-3-small",
                },
                clear=False,
            ), patch("copilot_ui.services.RagasEvaluator") as evaluator_cls:
                service._resolve_ragas_evaluator_locked()

        config = evaluator_cls.call_args.args[0]
        self.assertEqual(config.llm_model, "gpt-4o-mini")
        self.assertEqual(config.embedding_model, "text-embedding-3-small")
        self.assertEqual(config.api_key, "test-key")


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
        self.available_models = list(
            available_models
            or (
                FIXED_OLLAMA_MODEL,
                "qwen2.5-coder:7b-instruct",
                "mxbai-embed-large",
            )
        )
        self.pulled_models: list[str] = []

    def with_models(self, *, chat_model: str | None = None, embedding_model: str | None = None):
        clone = FakeOllamaClient(
            base_url=self.base_url,
            chat_model=chat_model or self.chat_model,
            embedding_model=embedding_model or self.embedding_model,
            available_models=tuple(self.available_models),
        )
        clone.pulled_models = list(self.pulled_models)
        return clone

    def list_models(self) -> tuple[str, ...]:
        return tuple(sorted(self.available_models))

    def pull_model(self, model_name: str) -> None:
        if model_name not in self.available_models:
            self.available_models.append(model_name)
        self.pulled_models.append(model_name)

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
    def test_from_env_uses_configured_models(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OLLAMA_CHAT_MODEL": "phi4-mini-reasoning:latest",
                "OLLAMA_EMBED_MODEL": "qwen2.5-coder:7b-instruct",
            },
            clear=False,
        ):
            client = OllamaClient.from_env()

        self.assertEqual(client.chat_model, "phi4-mini-reasoning:latest")
        self.assertEqual(client.embedding_model, "qwen2.5-coder:7b-instruct")

    def test_snapshot_exposes_available_ollama_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CopilotApplicationService(
                storage_dir=temp_dir,
                ollama_client=FakeOllamaClient(),
            )

            snapshot = service.snapshot()

        self.assertIsNotNone(snapshot.ollama)
        self.assertIn(FIXED_OLLAMA_MODEL, snapshot.ollama.available_models)
        self.assertIn("qwen2.5-coder:7b-instruct", snapshot.ollama.available_models)
        self.assertEqual(snapshot.ollama.chat_model, FIXED_OLLAMA_MODEL)
        self.assertEqual(snapshot.ollama.embedding_model, FIXED_OLLAMA_MODEL)

    def test_update_ollama_settings_reindexes_existing_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CopilotApplicationService(
                storage_dir=temp_dir,
                ollama_client=FakeOllamaClient(),
            )
            snapshot = service.add_uploaded_files(
                [encode_text_payload("notes.txt", "private note about vlan 10 and interface status")]
            )
            before_embedding = service._records[0].embedding
            document_id = snapshot.documents[0].document_id

            updated = service.update_ollama_settings(
                chat_model="qwen2.5-coder:7b-instruct",
                embedding_model="mxbai-embed-large",
            )

            after_embedding = service._records[0].embedding

        self.assertEqual(updated.documents[0].document_id, document_id)
        self.assertNotEqual(before_embedding, after_embedding)
        self.assertEqual(updated.ollama.chat_model, "qwen2.5-coder:7b-instruct")
        self.assertEqual(updated.ollama.embedding_model, "mxbai-embed-large")
        self.assertTrue(updated.retrieval_ready)

    def test_update_ollama_settings_pulls_missing_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CopilotApplicationService(
                storage_dir=temp_dir,
                ollama_client=FakeOllamaClient(available_models=(FIXED_OLLAMA_MODEL,)),
            )

            updated = service.update_ollama_settings(
                chat_model="phi4-mini-reasoning:latest",
                embedding_model=FIXED_OLLAMA_MODEL,
            )

        self.assertEqual(updated.ollama.chat_model, "phi4-mini-reasoning:latest")
        self.assertIn("phi4-mini-reasoning:latest", updated.ollama.available_models)

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

    def test_ollama_pull_model_uses_pull_endpoint(self) -> None:
        session = Mock()
        session.request.return_value = FakeResponse({"status": "success"})
        client = OllamaClient(session=session)

        client.pull_model("phi4-mini-reasoning:latest")

        session.request.assert_called_once()
        self.assertEqual(session.request.call_args.args[0], "POST")
        self.assertTrue(session.request.call_args.args[1].endswith("/api/pull"))
        self.assertEqual(
            session.request.call_args.kwargs["json"],
            {"model": "phi4-mini-reasoning:latest", "stream": False},
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
                return (
                    "<think>Reasoning about the interface status.</think>\n"
                    "The interface is GigabitEthernet1/0/24 and it is up. [device.json • device.interfaces]"
                )

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
        self.assertNotIn("<think>", answer.content)
        self.assertEqual(answer.meta["answer_provider"], "ollama")
        self.assertEqual(answer.meta["answer_model"], FIXED_OLLAMA_MODEL)
        self.assertEqual(answer.citations[0].label, "device.json • device.interfaces")
        self.assertEqual(client.messages[0]["role"], "system")
        self.assertIn("Question: What interface is up?", client.messages[1]["content"])

    def test_ollama_answer_generator_applies_domain_specific_prompting(self) -> None:
        class FakeChatClient:
            chat_model = FIXED_OLLAMA_MODEL

            def __init__(self) -> None:
                self.messages = ()

            def chat(self, messages, *, temperature: float = 0.1) -> str:
                self.messages = tuple(messages)
                return "Allowed VLANs are 10,20,30. [switch.cfg • interface GigabitEthernet1/0/24]"

        retrieval_response = RetrievalResponse(
            original_query="Which VLANs are allowed on interface GigabitEthernet1/0/24?",
            normalized_query="which vlans are allowed on interface gigabitethernet1/0/24",
            retrieval_mode="hybrid",
            top_k_results=1,
            results=(
                RetrievedChunk(
                    chunk_id="chunk_cisco_1",
                    text="interface GigabitEthernet1/0/24\n switchport trunk allowed vlan 10,20,30",
                    score=0.99,
                    metadata={
                        "filename": "switch.cfg",
                        "cisco_feature": "interface",
                        "cisco_section": "GigabitEthernet1/0/24",
                        "domain": "cisco",
                    },
                    source_type="cisco_config",
                ),
            ),
            timings=RetrievalTiming(total_ms=9.1),
            domain="cisco",
            domain_confidence=0.94,
            domain_reason="cisco selected from weighted signals",
            domain_mode="automatic",
            domain_filter_applied=True,
        )
        client = FakeChatClient()
        generator = OllamaAnswerGenerator(client=client)

        answer = generator.generate(
            "Which VLANs are allowed on interface GigabitEthernet1/0/24?",
            retrieval_response,
        )

        self.assertEqual(answer.meta["domain"], "cisco")
        self.assertIn("Cisco networking material", client.messages[0]["content"])
        self.assertIn("Routed domain: cisco", client.messages[1]["content"])
        self.assertIn("Domain filter applied: yes", client.messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
