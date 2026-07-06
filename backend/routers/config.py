import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from auth import verify_admin
from config import PROFILE_DIR
from models import SiteConfigRecord
from schemas import SiteConfigResponse, SiteConfigUpdate
from store import load_config, save_config

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=SiteConfigResponse)
def get_config():
    return load_config()


@router.put("", response_model=SiteConfigResponse)
def update_config(body: SiteConfigUpdate):
    verify_admin(body.admin_password)
    cfg = load_config()

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
            setattr(cfg, field, value)

    save_config(cfg)
    return cfg


@router.post("/profile-picture", response_model=SiteConfigResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    admin_password: str = Form(...),
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

    cfg = load_config()

    old = cfg.profile_picture
    if old and old.startswith("/static/profile/"):
        old_path = PROFILE_DIR / Path(old).name
        if old_path.exists() and old_path.name != "default.jpg":
            old_path.unlink(missing_ok=True)

    cfg.profile_picture = f"/static/profile/{stored_name}"
    save_config(cfg)
    return cfg
