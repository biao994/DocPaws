"""Agent 工具：范围内文档统计与列表"""
from docpaws.domain.models.document import Document
from docpaws.domain.models.folder import KbFolder
from docpaws.usecases.chat_scope import (
    count_documents_in_scope,
    list_document_titles_in_scope,
    SCOPE_FOLDER,
    SCOPE_KB,
)


def test_count_and_list_documents_in_folder_scope(db_session):
    kb_id = "kb-agent-tools"
    root = KbFolder(kb_id=kb_id, name="root", parent_id=None)
    db_session.add(root)
    db_session.flush()
    sub = KbFolder(kb_id=kb_id, name="sub", parent_id=root.id)
    db_session.add(sub)
    db_session.flush()

    db_session.add(Document(kb_id=kb_id, title="a.pdf", folder_id=root.id))
    db_session.add(Document(kb_id=kb_id, title="b.pdf", folder_id=sub.id))
    db_session.add(Document(kb_id=kb_id, title="outside.pdf", folder_id=None))
    db_session.commit()

    n = count_documents_in_scope(
        db_session, kb_id=kb_id, scope_type=SCOPE_FOLDER, scope_id=root.id
    )
    assert n == 2

    titles = list_document_titles_in_scope(
        db_session, kb_id=kb_id, scope_type=SCOPE_FOLDER, scope_id=root.id, limit=10
    )
    assert set(titles) == {"a.pdf", "b.pdf"}

    kb_total = count_documents_in_scope(
        db_session, kb_id=kb_id, scope_type=SCOPE_KB, scope_id=None
    )
    assert kb_total == 3
