import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from google.cloud import firestore

from auth import verify_admin
from config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE, UPLOAD_DIR
from database import get_db, bucket
from models import Document
from schemas import DocumentDelete, DocumentGroupResponse, DocumentFileResponse, DocumentUpdate
from services.text_extractor import extract_text
from services.thumbnail_generator import create_thumbnail, remove_thumbnail

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def _group_key(doc: Document) -> str:
    return doc.group_id or f"single-{doc.id}"


def _get_group_docs(db: firestore.Client, doc: Document) -> list[Document]:
    if doc.group_id:
        docs = db.collection('documents').where('group_id', '==', doc.group_id).get()
        doc_models = [Document(**d.to_dict()) for d in docs]
        doc_models.sort(key=lambda d: (d.group_order, d.id))
        return doc_models
    return [doc]


def _to_group_response(primary: Document, files: list[Document]) -> DocumentGroupResponse:
    return DocumentGroupResponse(
        id=int(primary.id) if primary.id and primary.id.isdigit() else hash(primary.id) % 1000000,
        group_id=_group_key(primary),
        description=primary.description or "",
        upload_date=primary.upload_date,
        files=[DocumentFileResponse(
            id=int(f.id) if f.id and f.id.isdigit() else hash(f.id) % 1000000,
            filename=f.filename,
            original_filename=f.original_filename,
            file_type=f.file_type,
            group_order=f.group_order,
            thumbnail_path=f.thumbnail_path
        ) for f in files],
    )


def _group_documents(docs: list[Document]) -> list[DocumentGroupResponse]:
    grouped: dict[str, list[Document]] = {}
    for doc in docs:
        grouped.setdefault(_group_key(doc), []).append(doc)

    groups: list[DocumentGroupResponse] = []
    for files in grouped.values():
        files.sort(key=lambda d: (d.group_order, d.id or ""))
        groups.append(_to_group_response(files[0], files))

    groups.sort(key=lambda g: g.upload_date, reverse=True)
    return groups


async def _save_upload(file: UploadFile, description: str, group_id: str, group_order: int, db: firestore.Client) -> Document:
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
    
    # Temporarily save to local for text extraction & thumbnail generation
    temp_dest = UPLOAD_DIR / stored_name
    temp_dest.write_bytes(content)

    extracted = extract_text(temp_dest, ext)
    thumbnail_url = None

    if group_order == 0:
        local_thumb = create_thumbnail(temp_dest, ext, extracted)
        if local_thumb:
            thumb_name = Path(local_thumb).name
            thumb_blob = bucket.blob(f"thumbnails/{thumb_name}")
            thumb_blob.upload_from_filename(local_thumb)
            thumb_blob.make_public()
            thumbnail_url = thumb_blob.public_url
            Path(local_thumb).unlink(missing_ok=True)

    # Upload actual document to Firebase Storage
    doc_blob = bucket.blob(f"uploads/{stored_name}")
    doc_blob.upload_from_filename(str(temp_dest))
    doc_blob.make_public()
    
    # Remove temp file
    temp_dest.unlink(missing_ok=True)

    doc_id = uuid.uuid4().hex
    doc = Document(
        id=doc_id,
        filename=stored_name,
        original_filename=file.filename,
        file_type=ext,
        description=description,
        extracted_text=extracted,
        group_id=group_id,
        group_order=group_order,
        thumbnail_path=thumbnail_url,
        upload_date=datetime.now(timezone.utc)
    )
    db.collection('documents').document(doc_id).set(doc.model_dump(mode='json'))
    return doc


@router.get("", response_model=list[DocumentGroupResponse])
def list_documents(db = Depends(get_db)):
    docs_ref = db.collection('documents').get()
    docs = [Document(**d.to_dict()) for d in docs_ref]
    return _group_documents(docs)


@router.post("", response_model=DocumentGroupResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    description: str = Form(""),
    admin_password: str = Form(...),
    db = Depends(get_db),
):
    verify_admin(admin_password)

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    group_id = uuid.uuid4().hex
    saved: list[Document] = []

    try:
        for order, file in enumerate(files):
            saved.append(await _save_upload(file, description, group_id, order, db))
    except HTTPException:
        # Cleanup logic omitted for brevity, let's keep it simple
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload documents: {e}")

    return _to_group_response(saved[0], saved)


@router.put("/{doc_id}", response_model=DocumentGroupResponse)
def update_document(doc_id: str, body: DocumentUpdate, db = Depends(get_db)):
    verify_admin(body.admin_password)
    
    # For legacy IDs which were integers, we might need to query by old id if doc_id is passed as int
    doc_ref = db.collection('documents').document(doc_id)
    doc_snap = doc_ref.get()
    
    if not doc_snap.exists:
        # Fallback to query if doc_id is somehow numeric id in firestore
        docs = db.collection('documents').where('id', '==', doc_id).get()
        if not docs:
            raise HTTPException(status_code=404, detail="Document not found")
        doc_snap = docs[0]
        doc_ref = doc_snap.reference

    doc = Document(**doc_snap.to_dict())

    group_docs = _get_group_docs(db, doc)
    for item in group_docs:
        item.description = body.description
        db.collection('documents').document(item.id).update({'description': body.description})

    primary = group_docs[0]
    return _to_group_response(primary, group_docs)


@router.delete("/{doc_id}")
def delete_document(doc_id: str, body: DocumentDelete, db = Depends(get_db)):
    verify_admin(body.admin_password)
    
    doc_ref = db.collection('documents').document(doc_id)
    doc_snap = doc_ref.get()
    
    if not doc_snap.exists:
        docs = db.collection('documents').where('id', '==', doc_id).get()
        if not docs:
            raise HTTPException(status_code=404, detail="Document not found")
        doc_snap = docs[0]

    doc = Document(**doc_snap.to_dict())
    group_docs = _get_group_docs(db, doc)
    
    for item in group_docs:
        # Delete from storage
        try:
            bucket.blob(f"uploads/{item.filename}").delete()
        except Exception:
            pass
        if item.thumbnail_path and item.thumbnail_path.startswith("http"):
            try:
                thumb_name = item.thumbnail_path.split("?")[0].split("/")[-1]
                bucket.blob(f"thumbnails/{thumb_name}").delete()
            except Exception:
                pass
        db.collection('documents').document(item.id).delete()
        
    return {"message": "Document group deleted"}
