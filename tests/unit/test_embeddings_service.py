from kogniterm.core.embeddings_service import EmbeddingAdapter, EmbeddingsService


class DummyAdapter(EmbeddingAdapter):
    def embed_documents(self, texts):
        return [[float(len(text))] for text in texts]


def test_embed_documents_uses_generate_embeddings(monkeypatch):
    service = EmbeddingsService.__new__(EmbeddingsService)

    def fake_generate_embeddings(texts):
        assert texts == ["hola", "mundo"]
        return [[1.0], [2.0]]

    monkeypatch.setattr(service, "generate_embeddings", fake_generate_embeddings)

    assert service.embed_documents(["hola", "mundo"]) == [[1.0], [2.0]]


def test_embed_query_delegates_to_adapter():
    service = EmbeddingsService.__new__(EmbeddingsService)
    service.adapter = DummyAdapter()

    assert service.embed_query("hola") == [4.0]


def test_embedding_adapter_embed_query_falls_back_to_embed_documents():
    adapter = DummyAdapter()

    assert adapter.embed_query("consulta") == [8.0]
