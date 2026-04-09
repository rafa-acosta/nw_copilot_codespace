"""Local copilot GUI package."""

from .answers import AnswerGenerator, GroundedAnswerGenerator, OllamaAnswerGenerator
from .embeddings import HashingEmbeddingModel, OllamaEmbeddingModel
from .ollama import OllamaClient, OllamaError
from .server import run_server
from .services import CopilotApplicationService, QueryOptions

__all__ = [
    "AnswerGenerator",
    "CopilotApplicationService",
    "GroundedAnswerGenerator",
    "HashingEmbeddingModel",
    "OllamaAnswerGenerator",
    "OllamaClient",
    "OllamaEmbeddingModel",
    "OllamaError",
    "QueryOptions",
    "run_server",
]
