"""Answer + 助手 Message 同事务落库（一次 commit）"""
from sqlmodel import select

from docpaws.domain.models.chat import Message
from docpaws.domain.models.index import Answer, RetrievalRun
from docpaws.infra.repos.conversation_repo import (
    add_retrieval_run,
    create_conversation,
    create_message,
    persist_assistant_answer_and_message,
)


def test_persist_assistant_answer_and_message_writes_both_in_one_commit(db_session):
    conv = create_conversation(db_session, "kb-persist", "user-1", "persist")
    question = create_message(
        db_session, conversation_id=conv.id, role="user", content="问什么？"
    )

    commit_calls: list[int] = []
    real_commit = db_session.commit

    def _track_commit() -> None:
        commit_calls.append(1)
        real_commit()

    db_session.commit = _track_commit  # type: ignore[method-assign]

    answer, assistant = persist_assistant_answer_and_message(
        db_session,
        conversation_id=conv.id,
        question_message_id=question.id,
        answer_text="答这个。",
        model_name="test-model",
        citations=[{"chunk_id": "c1"}],
    )

    assert len(commit_calls) == 1
    assert answer.id
    assert assistant.id
    assert assistant.role == "assistant"
    assert assistant.content == "答这个。"
    assert assistant.answer_id == answer.id
    assert answer.answer_text == "答这个。"
    assert answer.citations == [{"chunk_id": "c1"}]

    db_session.expire_all()
    assert db_session.get(Answer, answer.id) is not None
    assert db_session.get(Message, assistant.id) is not None


def test_persist_assistant_answer_and_message_includes_pending_retrieval_run(db_session):
    conv = create_conversation(db_session, "kb-persist-run", "user-1", "persist-run")
    question = create_message(
        db_session, conversation_id=conv.id, role="user", content="检索题"
    )
    add_retrieval_run(
        db_session,
        kb_id="kb-persist-run",
        conversation_id=conv.id,
        question_message_id=question.id,
        query_text="检索题",
        top_k=3,
        hit_chunks=[{"chunk_id": "h1"}],
    )

    persist_assistant_answer_and_message(
        db_session,
        conversation_id=conv.id,
        question_message_id=question.id,
        answer_text="有据可依",
        model_name="test-model",
    )

    runs = list(
        db_session.exec(
            select(RetrievalRun).where(RetrievalRun.conversation_id == conv.id)
        ).all()
    )
    assert len(runs) == 1
    assert runs[0].hit_chunks == [{"chunk_id": "h1"}]
