import uuid
import mimetypes
import requests
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from auth import verify_admin
from config import (
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_SIZE,
    UPLOAD_DIR,
    THUMBNAIL_DIR,
    SUPABASE_URL,
    SUPABASE_KEY,
    SUPABASE_BUCKET,
)
from models import DocumentRecord
from schemas import DocumentDelete, DocumentGroupResponse, DocumentFileResponse, DocumentUpdate
from services.text_extractor import extract_text
from services.thumbnail_generator import create_thumbnail, remove_thumbnail
from store import (
    load_documents,
    add_document,
    get_document_by_id,
    get_documents_by_group,
    update_documents,
    delete_documents_by_ids,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def _group_key(doc: DocumentRecord) -> str:
    return doc.group_id or f"single-{doc.id}"


def _to_group_response(primary: DocumentRecord, files: list[DocumentRecord]) -> DocumentGroupResponse:
    return DocumentGroupResponse(
        id=primary.id,
        group_id=_group_key(primary),
        description=primary.description or "",
        upload_date=primary.upload_date,
        files=[
            DocumentFileResponse(
                id=f.id,
                filename=f.filename,
                original_filename=f.original_filename,
                file_type=f.file_type,
                group_order=f.group_order,
                thumbnail_path=f.thumbnail_path,
            )
            for f in files
        ],
    )


def _group_documents(docs: list[DocumentRecord]) -> list[DocumentGroupResponse]:
    grouped: dict[str, list[DocumentRecord]] = {}
    for doc in docs:
        grouped.setdefault(_group_key(doc), []).append(doc)

    groups: list[DocumentGroupResponse] = []
    for files in grouped.values():
        files.sort(key=lambda d: (d.group_order, d.id))
        groups.append(_to_group_response(files[0], files))

    groups.sort(key=lambda g: g.upload_date, reverse=True)
    return groups


def _upload_to_supabase(local_file_path: Path, remote_filename: str) -> str:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return f"/uploads/{remote_filename}"

    mime_type, _ = mimetypes.guess_type(str(local_file_path))
    if not mime_type:
        mime_type = "application/octet-stream"

    url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}/{remote_filename}"
    headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": mime_type}

    with open(local_file_path, "rb") as f:
        file_bytes = f.read()

    response = requests.post(url, headers=headers, data=file_bytes)
    if response.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Supabase upload failed: {response.text}")

    return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/{remote_filename}"


def _delete_from_supabase(remote_filename: str) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}"
    headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    try:
        requests.delete(url, headers=headers, json={"prefixes": [remote_filename]})
    except Exception:
        pass


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DocumentGroupResponse])
def list_documents():
    return _group_documents(load_documents())


@router.post("", response_model=DocumentGroupResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    description: str = Form(""),
    admin_password: str = Form(...),
):
    verify_admin(admin_password)

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    group_id = uuid.uuid4().hex
    has_supabase = bool(SUPABASE_URL and SUPABASE_KEY)
    saved: list[DocumentRecord] = []

    try:
        for order, file in enumerate(files):
            if not file.filename:
                raise HTTPException(status_code=400, detail="No filename provided")

            ext = _get_extension(file.filename)
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{ext}' not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                )

            content = await file.read()
            if len(content) > MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=400, detail=f"File '{file.filename}' exceeds 50 MB limit")

            stored_name = f"{uuid.uuid4().hex}{ext}"
            dest = UPLOAD_DIR / stored_name
            dest.write_bytes(content)

            extracted = extract_text(dest, ext)
            thumbnail_path = None

            if order == 0:
                local_thumb = create_thumbnail(dest, ext, extracted)
                if local_thumb:
                    if has_supabase:
                        local_file = THUMBNAIL_DIR / Path(local_thumb).name
                        if local_file.exists():
                            thumbnail_path = _upload_to_supabase(local_file, Path(local_thumb).name)
                            local_file.unlink(missing_ok=True)
                        else:
                            thumbnail_path = local_thumb
                    else:
                        thumbnail_path = local_thumb

            if has_supabase:
                _upload_to_supabase(dest, stored_name)
                dest.unlink(missing_ok=True)

            doc = DocumentRecord(
                filename=stored_name,
                original_filename=file.filename,
                file_type=ext,
                description=description,
                extracted_text=extracted,
                group_id=group_id,
                group_order=order,
                thumbnail_path=thumbnail_path,
                upload_date=datetime.now(timezone.utc),
            )
            saved.append(add_document(doc))

    except HTTPException:
        for doc in saved:
            (UPLOAD_DIR / doc.filename).unlink(missing_ok=True)
        raise
    except Exception as exc:
        for doc in saved:
            (UPLOAD_DIR / doc.filename).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload documents: {exc}")

    return _to_group_response(saved[0], saved)


@router.put("/{doc_id}", response_model=DocumentGroupResponse)
def update_document(doc_id: int, body: DocumentUpdate):
    verify_admin(body.admin_password)
    doc = get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    group_docs = get_documents_by_group(doc.group_id) if doc.group_id else [doc]
    for item in group_docs:
        item.description = body.description
    update_documents(group_docs)

    primary = group_docs[0]
    return _to_group_response(primary, group_docs)


@router.delete("/{doc_id}")
def delete_document(doc_id: int, body: DocumentDelete):
    verify_admin(body.admin_password)
    doc = get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    group_docs = get_documents_by_group(doc.group_id) if doc.group_id else [doc]
    ids_to_delete = [d.id for d in group_docs]

    for item in group_docs:
        file_path = UPLOAD_DIR / item.filename
        if file_path.exists():
            file_path.unlink()
        _delete_from_supabase(item.filename)

        if item.thumbnail_path:
            if item.thumbnail_path.startswith("http"):
                _delete_from_supabase(Path(item.thumbnail_path).name)
            else:
                remove_thumbnail(item.thumbnail_path)

    delete_documents_by_ids(ids_to_delete)
    return {"message": "Document group deleted"}
