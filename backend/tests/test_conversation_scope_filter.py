"""会话列表按 scope_type / scope_id 筛选"""
from docpaws.infra.repos.conversation_repo import create_conversation, list_conversations


def test_list_conversations_filters_by_scope(db_session):
    kb_id = "kb-scope-list"
    user_id = "user-1"
    create_conversation(db_session, kb_id, user_id, "kb chat", scope_type="kb", scope_id=None)
    create_conversation(
        db_session, kb_id, user_id, "folder chat", scope_type="folder", scope_id="folder-a"
    )
    create_conversation(
        db_session, kb_id, user_id, "file chat", scope_type="file", scope_id="doc-1"
    )

    kb_items, kb_total = list_conversations(
        db_session, kb_id, user_id, scope_type="kb", scope_id=None
    )
    assert kb_total == 1
    assert kb_items[0].title == "kb chat"

    folder_items, folder_total = list_conversations(
        db_session, kb_id, user_id, scope_type="folder", scope_id="folder-a"
    )
    assert folder_total == 1
    assert folder_items[0].title == "folder chat"

    file_items, file_total = list_conversations(
        db_session, kb_id, user_id, scope_type="file", scope_id="doc-1"
    )
    assert file_total == 1
    assert file_items[0].title == "file chat"

    all_items, all_total = list_conversations(db_session, kb_id, user_id)
    assert all_total == 3
