from docpaws.domain.models.document import Document, Chunk
from docpaws.domain.models.index import IndexArtifact
from docpaws.infra.repos.index_repo import create_kb_index_artifact
from sqlmodel import Session, select

def test_create_kb_index_artifact_sets_ready_and_indexed_fields(db_session):
    kb_id = "kb1"
    doc = Document(kb_id=kb_id, title="t", status="indexing")
    db_session.add(doc)
    db_session.commit()

    db_session.add(Chunk(document_id=doc.id, content="hello"))
    db_session.commit()

    create_kb_index_artifact(
        db_session,
        kb_id,
        version=1,
        index_path="dummy",
        job_id="job1",
        new_content_hashes={doc.id: "sha1"},
    )
    db_session.commit()

    doc2 = db_session.get(Document, doc.id)
    assert doc2.status == "ready"
    assert doc2.indexed_artifact_id is not None