"""Sandboxed filesystem access: every skill in this file is restricted to
reading/writing inside settings.workspace. Paths that resolve outside the
workspace are rejected, so Claude can never be tricked (or trick itself)
into touching files elsewhere on the machine.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from jarvis.core.config import settings
from jarvis.skills.base import skill


class PathOutsideWorkspaceError(ValueError):
    pass


def resolve_in_workspace(relative_or_absolute: str) -> Path:
    """Resolve a user-supplied path against the workspace, refusing escapes."""
    candidate = Path(relative_or_absolute).expanduser()
    path = candidate if candidate.is_absolute() else settings.workspace / candidate
    resolved = path.resolve()
    workspace_resolved = settings.workspace.resolve()
    if workspace_resolved != resolved and workspace_resolved not in resolved.parents:
        raise PathOutsideWorkspaceError(
            f"'{relative_or_absolute}' resolves outside the Jarvis workspace "
            f"({workspace_resolved}). Only files inside the workspace are accessible."
        )
    return resolved


@skill(
    name="list_workspace_files",
    description=(
        "List files and folders inside the Jarvis workspace (optionally a subfolder). "
        "Use this to see what data/files are available before reading or analyzing them."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "subfolder": {
                "type": "string",
                "description": "Subfolder within the workspace to list. Omit to list the workspace root.",
            }
        },
    },
)
def list_workspace_files(subfolder: str = "") -> dict:
    target = resolve_in_workspace(subfolder) if subfolder else settings.workspace
    if not target.exists():
        return {"error": f"'{subfolder}' does not exist in the workspace."}
    if not target.is_dir():
        return {"error": f"'{subfolder}' is not a folder."}
    entries = []
    for p in sorted(target.iterdir()):
        entries.append({"name": p.name, "type": "dir" if p.is_dir() else "file", "size_bytes": p.stat().st_size if p.is_file() else None})
    return {"workspace": str(settings.workspace), "path": subfolder or ".", "entries": entries}


@skill(
    name="read_text_file",
    description=(
        "Read the contents of a text-based file (csv, tsv, txt, md, json, etc.) inside the "
        "Jarvis workspace. For .pdf or .docx files, use read_document_text instead."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file, relative to the workspace (or absolute)."},
            "max_chars": {"type": "integer", "description": "Maximum characters to return (default 20000)."},
        },
        "required": ["path"],
    },
)
def read_text_file(path: str, max_chars: int = 20000) -> dict:
    resolved = resolve_in_workspace(path)
    if not resolved.exists():
        return {"error": f"File not found: {path}"}
    content = resolved.read_text(errors="replace")
    truncated = len(content) > max_chars
    return {"path": path, "content": content[:max_chars], "truncated": truncated}


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(path: Path) -> str:
    document = DocxDocument(str(path))
    return "\n".join(p.text for p in document.paragraphs)


@skill(
    name="read_document_text",
    description=(
        "Extract the text content of a PDF or Word (.docx) document inside the Jarvis "
        "workspace, so it can be summarized, analyzed, or turned into a report/presentation. "
        "For plain text/csv/json/md files, use read_text_file instead."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the .pdf or .docx file, relative to the workspace."},
            "max_chars": {"type": "integer", "description": "Maximum characters to return (default 20000)."},
        },
        "required": ["path"],
    },
)
def read_document_text(path: str, max_chars: int = 20000) -> dict:
    resolved = resolve_in_workspace(path)
    if not resolved.exists():
        return {"error": f"File not found: {path}"}

    suffix = resolved.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text(resolved)
    elif suffix == ".docx":
        text = _extract_docx_text(resolved)
    else:
        return {
            "error": (
                f"Unsupported document type '{suffix}'. read_document_text handles .pdf/.docx; "
                "use read_text_file for plain text/csv/json/md files."
            )
        }
    truncated = len(text) > max_chars
    return {"path": path, "content": text[:max_chars], "truncated": truncated}


@skill(
    name="write_text_file",
    description="Write text content to a file inside the Jarvis workspace, creating folders as needed.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file, relative to the workspace."},
            "content": {"type": "string", "description": "Text content to write."},
            "overwrite": {"type": "boolean", "description": "Overwrite if the file already exists (default false)."},
        },
        "required": ["path", "content"],
    },
)
def write_text_file(path: str, content: str, overwrite: bool = False) -> dict:
    resolved = resolve_in_workspace(path)
    if resolved.exists() and not overwrite:
        return {"error": f"'{path}' already exists. Pass overwrite=true to replace it."}
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content)
    return {"path": path, "bytes_written": len(content.encode())}
