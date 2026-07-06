import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from auth import verify_admin
from config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE, UPLOAD_DIR
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

    if group_order == 0:
        thumbnail_path = create_thumbnail(dest, ext, extracted)

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
        remove_thumbnail(item.thumbnail_path)
        db.delete(item)
    db.commit()
    return {"message": "Document group deleted"}

