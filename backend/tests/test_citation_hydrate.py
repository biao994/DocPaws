"""引用来源：持久化与加载还原"""
from docpaws.domain.models.document import Chunk, Document
from docpaws.usecases.chat_service import hydrate_citations_from_stored


def test_hydrate_from_chunk_id_only(db_session):
    doc = Document(kb_id="kb-cite", title="2023_PDF3")
    db_session.add(doc)
    db_session.flush()
    chunk = Chunk(
        document_id=doc.id,
        content="国务院办公厅政府信息公开目录 第20页",
        page_no=22,
    )
    db_session.add(chunk)
    db_session.commit()

    out = hydrate_citations_from_stored(db_session, [{"chunk_id": chunk.id}])
    assert len(out) == 1
    assert out[0]["chunk_id"] == chunk.id
    assert out[0]["source"] == "2023_PDF3"
    assert out[0]["page_no"] == 22
    assert "信息公开目录" in out[0]["snippet"]


def test_hydrate_from_full_stored_payload(db_session):
    stored = [
        {
            "chunk_id": "c-old",
            "document_id": "d-old",
            "page_no": 2,
            "snippet": "已保存的摘要",
            "source": "2023_PDF3",
        }
    ]
    out = hydrate_citations_from_stored(db_session, stored)
    assert out[0]["snippet"] == "已保存的摘要"
    assert out[0]["source"] == "2023_PDF3"
