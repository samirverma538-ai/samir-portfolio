import uuid
import mimetypes
from pathlib import Path

import requests as http_requests
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from auth import verify_admin
from config import (
    PROFILE_DIR,
    SUPABASE_URL,
    SUPABASE_KEY,
    SUPABASE_BUCKET,
)
from models import SiteConfigRecord
from schemas import SiteConfigResponse, SiteConfigUpdate
from store import load_config, save_config

router = APIRouter(prefix="/api/config", tags=["config"])


def _upload_profile_to_supabase(local_path: Path, remote_name: str) -> str:
    """Upload profile picture to Supabase Storage and return the public URL."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return f"/static/profile/{remote_name}"

    mime_type, _ = mimetypes.guess_type(str(local_path))
    if not mime_type:
        mime_type = "image/jpeg"

    url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}/_profile/{remote_name}"
    headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": mime_type}

    with open(local_path, "rb") as f:
        data = f.read()

    resp = http_requests.post(url, headers=headers, data=data)
    if resp.status_code == 400 and "Duplicate" in resp.text:
        resp = http_requests.put(url, headers=headers, data=data)
    if resp.status_code not in (200, 201):
        # Fall back to local path if upload fails
        return f"/static/profile/{remote_name}"

    return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/_profile/{remote_name}"


def _delete_profile_from_supabase(profile_url: str) -> None:
    """Delete old profile picture from Supabase Storage."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    if not profile_url.startswith("http"):
        return
    try:
        # Extract the remote filename from the URL
        remote_name = profile_url.split("/_profile/")[-1].split("?")[0]
        url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}"
        headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
        http_requests.delete(url, headers=headers, json={"prefixes": [f"_profile/{remote_name}"]})
    except Exception:
        pass


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

    # Upload to Supabase Storage for persistence
    profile_url = _upload_profile_to_supabase(dest, stored_name)

    cfg = load_config()

    # Clean up old profile picture
    old = cfg.profile_picture
    if old and old != "/static/profile/default.jpg":
        if old.startswith("http"):
            _delete_profile_from_supabase(old)
        elif old.startswith("/static/profile/"):
            old_path = PROFILE_DIR / Path(old).name
            if old_path.exists():
                old_path.unlink(missing_ok=True)

    cfg.profile_picture = profile_url
    save_config(cfg)
    return cfg
