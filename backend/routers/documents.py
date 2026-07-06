import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import requests
import mimetypes
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
from database import get_db
from models import Document
from schemas import DocumentDelete, DocumentGroupResponse, DocumentFileResponse, DocumentUpdate
from services.text_extractor import extract_text
from services.thumbnail_generator import create_thumbnail, remove_thumbnail

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def _group_key(doc: Document) -> str:
    return doc.group_id or f"single-{doc.id}"


def _get_group_docs(db: Session, doc: Document) -> list[Document]:
    if doc.group_id:
        return (
            db.query(Document)
            .filter(Document.group_id == doc.group_id)
            .order_by(Document.group_order, Document.id)
            .all()
        )
    return [doc]


def _to_group_response(primary: Document, files: list[Document]) -> DocumentGroupResponse:
    return DocumentGroupResponse(
        id=primary.id,
        group_id=_group_key(primary),
        description=primary.description or "",
        upload_date=primary.upload_date,
        files=[DocumentFileResponse.model_validate(f) for f in files],
    )



def _group_documents(docs: list[Document]) -> list[DocumentGroupResponse]:
    grouped: dict[str, list[Document]] = {}
    for doc in docs:
        grouped.setdefault(_group_key(doc), []).append(doc)

    groups: list[DocumentGroupResponse] = []
    for files in grouped.values():
        files.sort(key=lambda d: (d.group_order, d.id or 0))
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
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": mime_type
    }

    with open(local_file_path, "rb") as f:
        file_bytes = f.read()

    response = requests.post(url, headers=headers, data=file_bytes)
    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Supabase upload failed: {response.text}"
        )

    return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/{remote_filename}"


def _delete_from_supabase(remote_filename: str):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    body = {"prefixes": [remote_filename]}

    try:
        requests.delete(url, headers=headers, json=body)
    except Exception:
        pass


async def _save_upload(file: UploadFile, description: str, group_id: str, group_order: int, db: Session) -> Document:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed for '{file.filename}'. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File '{file.filename}' exceeds 50 MB limit")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / stored_name
    dest.write_bytes(content)

    extracted = extract_text(dest, ext)
    thumbnail_path = None

    has_supabase = bool(SUPABASE_URL and SUPABASE_KEY)

    if group_order == 0:
        local_thumb_path = create_thumbnail(dest, ext, extracted)
        if local_thumb_path:
            if has_supabase:
                local_file = THUMBNAIL_DIR / Path(local_thumb_path).name
                if local_file.exists():
                    thumbnail_path = _upload_to_supabase(local_file, Path(local_thumb_path).name)
                    local_file.unlink(missing_ok=True)
                else:
                    thumbnail_path = local_thumb_path
            else:
                thumbnail_path = local_thumb_path
        else:
            thumbnail_path = None

    if has_supabase:
        _upload_to_supabase(dest, stored_name)
        dest.unlink(missing_ok=True)

    doc = Document(
        filename=stored_name,
        original_filename=file.filename,
        file_type=ext,
        description=description,
        extracted_text=extracted,
        group_id=group_id,
        group_order=group_order,
        thumbnail_path=thumbnail_path,
        upload_date=datetime.now(timezone.utc)
    )
    db.add(doc)
    return doc


@router.get("", response_model=list[DocumentGroupResponse])
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).all()
    return _group_documents(docs)


@router.post("", response_model=DocumentGroupResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    description: str = Form(""),
    admin_password: str = Form(...),
    db: Session = Depends(get_db),
):
    verify_admin(admin_password)

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    group_id = uuid.uuid4().hex
    saved: list[Document] = []

    try:
        for order, file in enumerate(files):
            saved.append(await _save_upload(file, description, group_id, order, db))
        db.commit()
        for doc in saved:
            db.refresh(doc)
    except HTTPException:
        db.rollback()
        for doc in saved:
            (UPLOAD_DIR / doc.filename).unlink(missing_ok=True)
        raise
    except Exception:
        db.rollback()
        for doc in saved:
            (UPLOAD_DIR / doc.filename).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to upload documents")

    return _to_group_response(saved[0], saved)


@router.put("/{doc_id}", response_model=DocumentGroupResponse)
def update_document(doc_id: int, body: DocumentUpdate, db: Session = Depends(get_db)):
    verify_admin(body.admin_password)
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    group_docs = _get_group_docs(db, doc)
    for item in group_docs:
        item.description = body.description
    db.commit()

    primary = group_docs[0]
    db.refresh(primary)
    return _to_group_response(primary, group_docs)


@router.delete("/{doc_id}")
def delete_document(doc_id: int, body: DocumentDelete, db: Session = Depends(get_db)):
    verify_admin(body.admin_password)
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    group_docs = _get_group_docs(db, doc)
    for item in group_docs:
        file_path = UPLOAD_DIR / item.filename
        if file_path.exists():
            file_path.unlink()
        _delete_from_supabase(item.filename)

        if item.thumbnail_path:
            if item.thumbnail_path.startswith("http"):
                thumb_filename = Path(item.thumbnail_path).name
                _delete_from_supabase(thumb_filename)
            else:
                remove_thumbnail(item.thumbnail_path)

        db.delete(item)
    db.commit()
    return {"message": "Document group deleted"}

