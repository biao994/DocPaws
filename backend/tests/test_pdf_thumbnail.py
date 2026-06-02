from pathlib import Path


def _make_sample_pdf(path: Path) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=560)
    page.insert_text((72, 72), "DocPaws thumbnail test")
    doc.save(str(path))
    doc.close()


def test_render_first_page_webp(tmp_path: Path):
    pdf_path = tmp_path / "sample.pdf"
    _make_sample_pdf(pdf_path)

    from docpaws.infra.parsers.pdf_thumbnail import render_first_page_webp

    data = render_first_page_webp(str(pdf_path), max_width=200)
    assert isinstance(data, bytes)
    assert len(data) > 100
    assert data[:4] == b"RIFF"
