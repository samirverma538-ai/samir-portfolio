import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from auth import verify_admin
from config import PROFILE_DIR
from database import get_db
from models import SiteConfig
from schemas import SiteConfigResponse, SiteConfigUpdate

router = APIRouter(prefix="/api/config", tags=["config"])


def _get_or_create_config(db: Session) -> SiteConfig:
    config = db.query(SiteConfig).first()
    if not config:
        config = SiteConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("", response_model=SiteConfigResponse)
def get_config(db: Session = Depends(get_db)):
    return _get_or_create_config(db)


@router.put("", response_model=SiteConfigResponse)
def update_config(body: SiteConfigUpdate, db: Session = Depends(get_db)):
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

    db.commit()
    db.refresh(config)
    return config


@router.post("/profile-picture", response_model=SiteConfigResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    admin_password: str = Form(...),
    db: Session = Depends(get_db),
):
    verify_admin(admin_password)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="Only JPG and PNG images are allowed")

    stored_name = f"profile_{uuid.uuid4().hex}{ext}"
    dest = PROFILE_DIR / stored_name
    content = await file.read()
    dest.write_bytes(content)

    config = _get_or_create_config(db)

    old = config.profile_picture
    if old and old.startswith("/static/profile/"):
        old_path = PROFILE_DIR / Path(old).name
        if old_path.exists() and old_path.name != "default.jpg":
            old_path.unlink(missing_ok=True)

    config.profile_picture = f"/static/profile/{stored_name}"
    db.commit()
    db.refresh(config)
    return config

