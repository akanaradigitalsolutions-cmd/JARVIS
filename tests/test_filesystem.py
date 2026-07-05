import pytest
from docx import Document as DocxDocument
from reportlab.pdfgen.canvas import Canvas

from jarvis.skills.filesystem import (
    PathOutsideWorkspaceError,
    read_document_text,
    read_text_file,
    resolve_in_workspace,
    write_text_file,
)


def test_write_then_read_roundtrip():
    result = write_text_file("notes/hello.txt", "hello jarvis")
    assert result["bytes_written"] == len("hello jarvis")

    read_result = read_text_file("notes/hello.txt")
    assert read_result["content"] == "hello jarvis"


def test_refuses_to_overwrite_without_flag():
    write_text_file("dupe.txt", "first")
    result = write_text_file("dupe.txt", "second")
    assert "error" in result


def test_overwrite_flag_replaces_content():
    write_text_file("dupe2.txt", "first")
    write_text_file("dupe2.txt", "second", overwrite=True)
    assert read_text_file("dupe2.txt")["content"] == "second"


def test_path_traversal_is_blocked():
    with pytest.raises(PathOutsideWorkspaceError):
        resolve_in_workspace("../../etc/passwd")


def test_missing_file_reports_error_not_exception():
    result = read_text_file("does/not/exist.txt")
    assert "error" in result


def test_read_document_text_extracts_pdf():
    path = resolve_in_workspace("sample.pdf")
    canvas = Canvas(str(path))
    canvas.drawString(100, 700, "Hello from a PDF")
    canvas.save()

    result = read_document_text("sample.pdf")
    assert "Hello from a PDF" in result["content"]


def test_read_document_text_extracts_docx():
    path = resolve_in_workspace("sample.docx")
    document = DocxDocument()
    document.add_paragraph("Hello from a Word document")
    document.save(str(path))

    result = read_document_text("sample.docx")
    assert "Hello from a Word document" in result["content"]


def test_read_document_text_rejects_unsupported_type():
    write_text_file("sample.csv", "a,b\n1,2\n", overwrite=True)
    result = read_document_text("sample.csv")
    assert "error" in result
