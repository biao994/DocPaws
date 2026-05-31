"""UsageRecord 一期：chat 流式问答用量落库"""
from docpaws.infra.repos.usage_repo import record_chat_stream_usage, get_usage_by_request_id


def test_record_chat_stream_usage_persists(db_session):
    row = record_chat_stream_usage(
        db_session,
        request_id="req-usage-1",
        kb_id="kb1",
        user_id="u1",
        chat_mode="fast",
        model_name="deepseek-v4-flash",
        latency_ms=1234,
        error_code=None,
    )
    assert row is not None
    assert row.id
    assert row.action == "chat.stream.fast"
    assert row.latency_ms == 1234
    assert row.tokens_in == 0
    assert row.cost == 0.0
    assert row.error_code is None

    loaded = get_usage_by_request_id(db_session, "req-usage-1")
    assert loaded is not None
    assert loaded.id == row.id


def test_record_chat_stream_usage_with_error(db_session):
    row = record_chat_stream_usage(
        db_session,
        request_id="req-usage-2",
        kb_id="kb1",
        user_id="u1",
        chat_mode="deep",
        model_name="deepseek-v4-flash",
        latency_ms=500,
        error_code="INSUFFICIENT_RETRIEVAL",
    )
    assert row is not None
    assert row.action == "chat.stream.deep"
    assert row.error_code == "INSUFFICIENT_RETRIEVAL"
