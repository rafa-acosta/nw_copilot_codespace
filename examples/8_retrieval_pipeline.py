"""
Example 8: Retrieval Pipeline Integration

Builds a local retrieval service on top of the existing ingestion and processing
pipeline, then executes queries across multiple source types.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from rag_data_ingestion import CiscoConfigLoader, DocxLoader, ExcelLoader, JSONLoader, PDFLoader, TextFileLoader
from rag_processing import CleanDocument, DocumentPipeline
from retrieval import RetrievalConfig, RetrievalMode, RetrievalRequest
from retrieval.embedders import CallableQueryEmbedder
from retrieval.services import build_retrieval_service, build_stored_chunks


class SimpleLocalEmbeddingModel:
    """
    Deterministic local embedder for integration wiring and smoke tests.

    Replace this with your existing local embedding model, for example:
    - SentenceTransformers model.encode
    - InstructorEmbedding model.encode
    - llama.cpp embedding endpoint running locally
    """

    VOCABULARY = (
        "hurricane",
        "policy",
        "revenue",
        "quarter",
        "json",
        "status",
        "interface",
        "switchport",
        "vlan",
        "page",
        "section",
    )

    def embed_query(self, text: str) -> list[float]:
        lowered = text.casefold()
        return [float(lowered.count(term)) for term in self.VOCABULARY]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


def _load_document(file_path: str):
    path = Path(file_path)
    suffix = path.suffix.lower()
    file_name = path.name.casefold()
    if suffix == ".pdf":
        return PDFLoader().load(file_path)
    if suffix == ".docx":
        return DocxLoader().load(file_path)
    if suffix in {".xlsx", ".xls"}:
        return ExcelLoader().load(file_path)
    if suffix == ".json":
        return JSONLoader().load(file_path)
    if suffix in {".cfg", ".conf", ".config"} or "cisco" in file_name or "switch" in file_name:
        return CiscoConfigLoader().load(file_path)
    return TextFileLoader().load(file_path)


def index_documents(file_paths: Iterable[str]):
    embedding_model = SimpleLocalEmbeddingModel()
    processing_pipeline = DocumentPipeline(max_size=900, overlap=120)
    retrieval_records = []

    for file_path in file_paths:
        ingested = _load_document(file_path)
        clean_document = CleanDocument.from_ingested(ingested)
        chunks = processing_pipeline.run(clean_document)
        embeddings = embedding_model.embed_documents([chunk.content for chunk in chunks])
        column_names = []
        for chunk in chunks:
            sheet_name = getattr(chunk.metadata, "sheet", None)
            if sheet_name and "|" in chunk.content.splitlines()[0]:
                headers = [part.strip() for part in chunk.content.splitlines()[0].split("|")]
                column_names.append(headers)
            else:
                column_names.append(())
        retrieval_records.extend(
            build_stored_chunks(
                chunks,
                embeddings,
                column_names=column_names,
            )
        )

    retrieval_config = RetrievalConfig.from_json_file("retrieval/config/retrieval_config.example.json")
    query_embedder = CallableQueryEmbedder(
        embedding_model.embed_query,
        expected_dimension=len(SimpleLocalEmbeddingModel.VOCABULARY),
    )
    return build_retrieval_service(
        retrieval_records,
        query_embedder=query_embedder,
        config=retrieval_config,
    )


def run_example() -> None:
    testing_dir = Path("testing_files")
    file_paths = [
        str(testing_dir / "huracan.txt"),
        str(testing_dir / "HIPOTECA 90 MILLONES.pdf"),
        str(testing_dir / "EvMateo.docx"),
        str(testing_dir / "Cisco 3750.txt"),
    ]

    service = index_documents(file_paths)
    queries = [
        "hurricane evacuation plan",
        "page 1 mortgage policy",
        "section event details",
        "switchport trunk allowed vlan on interface GigabitEthernet1/0/24",
    ]

    for query in queries:
        response = service.retrieve(
            RetrievalRequest(
                query=query,
                mode=RetrievalMode.HYBRID,
                top_k=3,
                debug=True,
            )
        )
        print("=" * 80)
        print(f"Query: {query}")
        print(f"Normalized: {response.normalized_query}")
        print(f"Latency: {response.timings.total_ms:.2f} ms")
        for result in response.results:
            print(f"- {result.metadata['source_type']} | score={result.score:.4f} | chunk={result.chunk_id}")
            print(f"  file={result.metadata['filename']} page={result.metadata['page_number']} section={result.metadata['section']}")
            print(f"  {result.text[:160]}...")


if __name__ == "__main__":
    run_example()
