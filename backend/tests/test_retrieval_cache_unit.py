import json


class _FakeDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


class _FakeChunk:
    def __init__(self, content: str):
        self.content = content


class _FakeRedis:
    """
    极简 Redis stub：只实现本项目检索缓存用到的 get/set。
    """

    def __init__(self):
        self._kv: dict[str, bytes] = {}
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, int | None, bool | None]] = []  # (key, ex, nx)

    def get(self, key: str):
        self.get_calls.append(key)
        return self._kv.get(key)

    def set(self, key: str, value: bytes, ex: int | None = None, nx: bool | None = None):
        self.set_calls.append((key, ex, nx))
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        return True


def _consume_sse(resp) -> list[dict]:
    payloads: list[dict] = []
    for line in resp.iter_lines():
        if not line:
            continue
        assert line.startswith("data: ")
        payloads.append(json.loads(line[len("data: ") :]))
        if payloads[-1].get("finished"):
            break
    return payloads


def test_retrieval_cache_hit_skips_similarity_search(db_session, monkeypatch, tmp_path):
    """retrieve_scoped_docs_cached：相同问题第二次命中 Redis，不再 similarity_search。"""
    import docpaws.usecases.chat_service as chat_service

    fake_redis = _FakeRedis()
    search_count = {"n": 0}

    class _VS:
        def similarity_search(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            search_count["n"] += 1
            return [_FakeDoc("文档内容", {"chunk_id": "c1", "document_id": "d1", "source": "t1"})]

        def similarity_search_with_score(self, question, k=5, filter=None, fetch_k=20, **kwargs):
            search_count["n"] += 1
            doc = _FakeDoc("文档内容", {"chunk_id": "c1", "document_id": "d1", "source": "t1"})
            return [(doc, 0.05)]

    vs = _VS()
    kb_id = "kb-cache-unit"
    artifact_id = "art1"
    scope_token = "kb:"

    chat_service.retrieve_scoped_docs_cached(
        kb_id=kb_id,
        question="同一个问题",
        search_k=5,
        metadata_filter=None,
        vectorstore=vs,
        cache_redis=fake_redis,
        artifact_id=artifact_id,
        scope_token=scope_token,
    )
    chat_service.retrieve_scoped_docs_cached(
        kb_id=kb_id,
        question="同一个问题",
        search_k=5,
        metadata_filter=None,
        vectorstore=vs,
        cache_redis=fake_redis,
        artifact_id=artifact_id,
        scope_token=scope_token,
    )

    assert search_count["n"] == 1
    assert len(fake_redis.get_calls) >= 2
    assert len(fake_redis.set_calls) >= 1

