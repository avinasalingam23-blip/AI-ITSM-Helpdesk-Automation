"""Optional real MiniLM + on-disk Chroma test; never contacts Atlas or loads Qwen."""
import os
from dataclasses import replace

import pytest

from helpdesk.config import Settings
from helpdesk.rag import LocalAI


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_MODEL_TESTS") != "1", reason="Set RUN_MODEL_TESTS=1 for real cached MiniLM / Chroma tests")
def test_real_semantic_retrieval_and_persistent_index(tmp_path):
    cfg = replace(Settings(mongo_uri=""), chroma_path=tmp_path / "chroma")
    ai = LocalAI(cfg)
    ai._index()
    assert ai.chunk_count >= 16
    for query, expected in [("My VPN is not connecting.", "KB-VPN"),
                            ("My password has expired.", "KB-PASSWORD"),
                            ("How do I troubleshoot Outlook synchronisation?", "KB-OUTLOOK"),
                            ("I need Visual Studio Code.", "KB-SOFTWARE")]:
        result = ai.search(query)
        assert result[0]["article_id"] == expected, result
        assert result[0]["similarity"] >= cfg.retrieval_threshold
    # A second client opens the same on-disk collection without re-embedding.
    reopened = LocalAI(cfg)
    reopened.embedder = ai.embedder
    reopened.client = ai.client
    reopened.collection = reopened.client.get_collection("approved-itsm-minilm-v1", embedding_function=None)
    reopened.chunk_count = reopened.collection.count()
    assert reopened.chunk_count == ai.chunk_count
    assert reopened.search("Outlook synchronisation")[0]["article_id"] == "KB-OUTLOOK"
