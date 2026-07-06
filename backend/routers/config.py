import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from google.cloud import firestore

from auth import verify_admin
from config import PROFILE_DIR
from database import get_db, bucket
from models import SiteConfig
from schemas import SiteConfigResponse, SiteConfigUpdate

router = APIRouter(prefix="/api/config", tags=["config"])


def _get_or_create_config(db: firestore.Client) -> SiteConfig:
    doc_ref = db.collection('site_config').document('1')
    doc = doc_ref.get()
    if not doc.exists:
        config = SiteConfig(id="1")
        doc_ref.set(config.model_dump(mode='json'))
        return config
    return SiteConfig(**doc.to_dict())


@router.get("", response_model=SiteConfigResponse)
def get_config(db = Depends(get_db)):
    return _get_or_create_config(db)


@router.put("", response_model=SiteConfigResponse)
def update_config(body: SiteConfigUpdate, db = Depends(get_db)):
    verify_admin(body.admin_password)
    config = _get_or_create_config(db)

    for field in (
        "header",
        "subheader",
        "owner_name",
        "role",
        "experience",
        "contact_email",
        "contact_phone",
        "contact_linkedin",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(config, field, value)

    db.collection('site_config').document('1').set(config.model_dump(mode='json'))
    return config


@router.post("/profile-picture", response_model=SiteConfigResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    admin_password: str = Form(...),
    db = Depends(get_db),
):
    verify_admin(admin_password)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="Only JPG and PNG images are allowed")

    stored_name = f"profile_{uuid.uuid4().hex}{ext}"
    
    # Upload to Firebase Storage
    blob = bucket.blob(f"profile/{stored_name}")
    content = await file.read()
    blob.upload_from_string(content, content_type=file.content_type)
    # Make it publicly accessible
    blob.make_public()

    config = _get_or_create_config(db)
    
    old = config.profile_picture
    if old and old.startswith("http"):
        try:
            # Attempt to delete old picture if it was in the bucket
            old_blob_name = old.split("?")[0].split("/")[-1]
            old_blob = bucket.blob(f"profile/{old_blob_name}")
            if old_blob.exists():
                old_blob.delete()
        except Exception:
            pass

    config.profile_picture = blob.public_url
    db.collection('site_config').document('1').set(config.model_dump(mode='json'))
    return config
