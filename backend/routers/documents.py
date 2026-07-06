import uuid
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

