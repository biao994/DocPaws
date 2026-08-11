"""历史拼进 prompt：近几轮原样 + 更早压缩 + 超预算再裁"""
from docpaws.domain.models.chat import Message
from docpaws.domain.services.chat_history import format_history_for_prompt
from docpaws.infra.repos.conversation_repo import (
    create_conversation,
    get_recent_history_text,
)


def test_format_history_keeps_all_when_under_budget():
    lines = ["用户: A", "助手: B", "用户: C"]
    text = format_history_for_prompt(lines, max_chars=500)
    assert text == "用户: A\n助手: B\n用户: C"
    assert "【更早对话】" not in text


def test_format_history_keeps_recent_full_and_folds_older_when_over_budget():
    lines = [
        "用户: " + ("OLD1" * 40),
        "助手: " + ("OLD2" * 40),
        "用户: mid_q",
        "助手: mid_a",
        "用户: recent_q",
        "助手: recent_a",
    ]
    text = format_history_for_prompt(
        lines, max_chars=220, recent_keep=2, older_line_max=24
    )

    assert "recent_q" in text
    assert "recent_a" in text
    assert "【最近对话】" in text
    assert "【更早对话】" in text
    assert "OLD1" * 40 not in text
    assert len(text) <= 220


def test_get_recent_history_text_drops_oldest_recent_when_still_over_budget(db_session):
    """无「更早」可折时（全落在 recent 窗），仍从最旧裁到预算内。"""
    conv = create_conversation(db_session, "kb-hist", "user-1", "hist")
    for i, content in enumerate(["OLD_TURN", "MID_TURN", "NEW_TURN"]):
        db_session.add(
            Message(
                id=f"{i:03d}",
                conversation_id=conv.id,
                role="user",
                content=content,
            )
        )
    db_session.commit()

    text = get_recent_history_text(
        db_session, conv.id, limit=10, max_chars=25, recent_keep=10
    )

    assert "NEW_TURN" in text
    assert "OLD_TURN" not in text
    assert len(text) <= 25


def test_get_recent_history_text_keeps_all_when_under_char_budget(db_session):
    conv = create_conversation(db_session, "kb-hist-ok", "user-1", "hist-ok")
    for i, content in enumerate(["A_TURN", "B_TURN", "C_TURN"]):
        db_session.add(
            Message(
                id=f"{i:03d}",
                conversation_id=conv.id,
                role="user",
                content=content,
            )
        )
    db_session.commit()

    text = get_recent_history_text(db_session, conv.id, limit=10, max_chars=500)

    assert "A_TURN" in text
    assert "B_TURN" in text
    assert "C_TURN" in text
