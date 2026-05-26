"""对话检索范围：scope 解析与 FAISS filter"""
from sqlmodel import Session

from langchain_core.documents import Document as LCD
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import FakeEmbeddings

from docpaws.domain.models.document import Document
from docpaws.domain.models.folder import KbFolder
from docpaws.infra.repos.folder_repo import collect_folder_ids_with_descendants
from docpaws.usecases.chat_scope import (
    SCOPE_FILE,
    SCOPE_FOLDER,
    SCOPE_KB,
    build_faiss_filter,
    document_ids_for_scope,
    resolve_document_id_from_question,
    resolve_effective_scope,
    retrieval_filter_for_question,
    scope_from_request,
)


def test_scope_from_request_priority():
    assert scope_from_request(document_id="d1", folder_id="f1") == (SCOPE_FILE, "d1")
    assert scope_from_request(document_id=None, folder_id="f1") == (SCOPE_FOLDER, "f1")
    assert scope_from_request(document_id=None, folder_id=None) == (SCOPE_KB, None)


def test_resolve_effective_scope_uses_conversation():
    class _Conv:
        scope_type = SCOPE_FILE
        scope_id = "saved-doc"

    st, sid = resolve_effective_scope(
        conversation=_Conv(),
        document_id="other",
        folder_id="f2",
    )
    assert st == SCOPE_FILE
    assert sid == "saved-doc"


def test_build_faiss_filter_single_and_multi():
    assert build_faiss_filter(None) is None
    assert build_faiss_filter(["d1"]) == {"document_id": "d1"}
    flt = build_faiss_filter(["d1", "d2"])
    assert callable(flt)
    assert flt({"document_id": "d1"})
    assert not flt({"document_id": "d3"})


def test_collect_folder_ids_with_descendants(db_session: Session):
    kb_id = "kb-tree"
    root = KbFolder(kb_id=kb_id, name="root", parent_id=None)
    db_session.add(root)
    db_session.flush()
    child = KbFolder(kb_id=kb_id, name="child", parent_id=root.id)
    db_session.add(child)
    db_session.flush()
    grand = KbFolder(kb_id=kb_id, name="grand", parent_id=child.id)
    db_session.add(grand)
    db_session.commit()

    ids = collect_folder_ids_with_descendants(db_session, kb_id, root.id)
    assert set(ids) == {root.id, child.id, grand.id}


def test_document_ids_for_folder_includes_subfolders(db_session: Session):
    kb_id = "kb-docs"
    root = KbFolder(kb_id=kb_id, name="a", parent_id=None)
    db_session.add(root)
    db_session.flush()
    sub = KbFolder(kb_id=kb_id, name="b", parent_id=root.id)
    db_session.add(sub)
    db_session.flush()
    d_root = Document(kb_id=kb_id, title="r1", folder_id=root.id)
    d_sub = Document(kb_id=kb_id, title="s1", folder_id=sub.id)
    db_session.add(d_root)
    db_session.add(d_sub)
    db_session.commit()

    doc_ids = document_ids_for_scope(
        db_session, kb_id=kb_id, scope_type=SCOPE_FOLDER, scope_id=root.id
    )
    assert set(doc_ids) == {d_root.id, d_sub.id}


def test_resolve_document_id_from_question_longest_match(db_session: Session):
    kb_id = "kb-title-match"
    d2 = Document(kb_id=kb_id, title="2023_PDF2")
    d3 = Document(kb_id=kb_id, title="2023_PDF3")
    other = Document(kb_id=kb_id, title="信息公开目录")
    db_session.add(d2)
    db_session.add(d3)
    db_session.add(other)
    db_session.commit()

    q = "需要，你讲一下2023_PDF3文档内容，回答不超过20个字"
    got = resolve_document_id_from_question(
        db_session,
        kb_id=kb_id,
        scope_type=SCOPE_KB,
        scope_id=None,
        text=q,
    )
    assert got == d3.id

    flt, matched = retrieval_filter_for_question(
        db_session,
        kb_id=kb_id,
        scope_type=SCOPE_KB,
        scope_id=None,
        base_filter=None,
        text=q,
    )
    assert matched == d3.id
    assert flt == {"document_id": d3.id}


def test_faiss_filter_limits_search():
    docs = [
        LCD(page_content="in d1", metadata={"document_id": "d1"}),
        LCD(page_content="in d2", metadata={"document_id": "d2"}),
        LCD(page_content="in d3", metadata={"document_id": "d3"}),
    ]
    vs = FAISS.from_documents(docs, FakeEmbeddings(size=8))
    out = vs.similarity_search("in", k=2, filter={"document_id": "d1"})
    assert len(out) == 1
    assert out[0].metadata["document_id"] == "d1"
