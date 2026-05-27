"""Pacote RAG: indexação e recuperação dos protocolos clínicos."""

from assistant.rag.retriever import ProtocolRetriever, RetrievedChunk, default_retriever

__all__ = ["ProtocolRetriever", "RetrievedChunk", "default_retriever"]
