"""
store.py — flat-file JSON persistence layer with Supabase cloud backup.

Two JSON files are maintained:
  DATA_DIR/documents.json   — list of document records
  DATA_DIR/config.json      — single site-config record

When Supabase is configured, every write also uploads the JSON file
to the Supabase Storage bucket under a `_data/` prefix. On startup
(or when local files are missing), the app downloads them from Supabase
so data survives Render's ephemeral filesystem.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any

import requests as http_requests

from config import DATA_DIR, SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET
from models import DocumentRecord, SiteConfigRecord

logger = logging.getLogger(__name__)

_lock = threading.Lock()

DOCUMENTS_FILE = DATA_DIR / "documents.json"
CONFIG_FILE = DATA_DIR / "config.json"

# Remote keys inside the Supabase bucket
_REMOTE_DOCS_KEY = "_data/documents.json"
_REMOTE_CONFIG_KEY = "_data/config.json"


# ── Supabase cloud sync ─────────────────────────────────────────────────────

def _has_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _supabase_headers(content_type: str = "application/json") -> dict:
    return {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
    }


def _upload_json_to_supabase(remote_key: str, data: Any) -> None:
    """Upload a JSON blob to Supabase Storage (upsert)."""
    if not _has_supabase():
        return
    try:
        payload = json.dumps(data, indent=2, default=str).encode("utf-8")
        url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}/{remote_key}"
        # Try POST first (create), fall back to PUT (update)
        resp = http_requests.post(url, headers=_supabase_headers(), data=payload)
        if resp.status_code == 400 and "Duplicate" in resp.text:
            resp = http_requests.put(url, headers=_supabase_headers(), data=payload)
        if resp.status_code not in (200, 201):
            logger.warning("Supabase upload %s failed (%s): %s", remote_key, resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Supabase upload %s error: %s", remote_key, exc)


def _download_json_from_supabase(remote_key: str) -> Any | None:
    """Download a JSON blob from Supabase Storage. Returns None on failure."""
    if not _has_supabase():
        return None
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/{remote_key}"
        resp = http_requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.warning("Supabase download %s error: %s", remote_key, exc)
    return None


# ── local file helpers ───────────────────────────────────────────────────────

def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _read_with_cloud_fallback(path: Path, remote_key: str, default: Any) -> Any:
    """Read local file; if missing/empty, try downloading from Supabase first."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data:
                return data
        except (json.JSONDecodeError, OSError):
            pass

    # Local file missing or empty — try Supabase
    cloud_data = _download_json_from_supabase(remote_key)
    if cloud_data is not None:
        logger.info("Restored %s from Supabase cloud backup", path.name)
        _write_json(path, cloud_data)
        return cloud_data

    return default


def _write_with_cloud_sync(path: Path, remote_key: str, data: Any) -> None:
    """Write to local file AND upload to Supabase for persistence."""
    _write_json(path, data)
    _upload_json_to_supabase(remote_key, data)


# ── documents ────────────────────────────────────────────────────────────────

def load_documents() -> list[DocumentRecord]:
    with _lock:
        raw = _read_with_cloud_fallback(DOCUMENTS_FILE, _REMOTE_DOCS_KEY, [])
    return [DocumentRecord(**d) for d in raw]


def save_documents(docs: list[DocumentRecord]) -> None:
    data = [d.model_dump(mode="json") for d in docs]
    with _lock:
        _write_with_cloud_sync(DOCUMENTS_FILE, _REMOTE_DOCS_KEY, data)


def get_document_by_id(doc_id: int) -> DocumentRecord | None:
    return next((d for d in load_documents() if d.id == doc_id), None)


def get_documents_by_group(group_id: str) -> list[DocumentRecord]:
    docs = load_documents()
    return sorted(
        [d for d in docs if d.group_id == group_id],
        key=lambda d: (d.group_order, d.id),
    )


def add_document(doc: DocumentRecord) -> DocumentRecord:
    with _lock:
        raw = _read_with_cloud_fallback(DOCUMENTS_FILE, _REMOTE_DOCS_KEY, [])
        existing_ids = [d.get("id", 0) for d in raw]
        doc.id = max(existing_ids, default=0) + 1
        raw.append(doc.model_dump(mode="json"))
        _write_with_cloud_sync(DOCUMENTS_FILE, _REMOTE_DOCS_KEY, raw)
    return doc


def update_documents(docs: list[DocumentRecord]) -> None:
    """Upsert/replace a list of documents by id."""
    all_docs = load_documents()
    updated_ids = {d.id for d in docs}
    remaining = [d for d in all_docs if d.id not in updated_ids]
    save_documents(remaining + docs)


def delete_documents_by_ids(ids: list[int]) -> None:
    docs = load_documents()
    save_documents([d for d in docs if d.id not in ids])


# ── site config ──────────────────────────────────────────────────────────────

_DEFAULT_CONFIG = {
    "header": "Architecture Document Showcase",
    "subheader": "Professional portfolio & interactive document repository",
    "owner_name": "Samir Kumar Verma",
    "role": "Solutions Architect",
    "experience": "Experienced solutions architect specializing in cloud-native systems, enterprise integration, and scalable application design.",
    "contact_email": "",
    "contact_phone": "",
    "contact_linkedin": "",
    "profile_picture": "/static/profile/default.jpg",
}


def load_config() -> SiteConfigRecord:
    with _lock:
        raw = _read_with_cloud_fallback(CONFIG_FILE, _REMOTE_CONFIG_KEY, _DEFAULT_CONFIG)
    merged = {**_DEFAULT_CONFIG, **raw}
    return SiteConfigRecord(**merged)


def save_config(cfg: SiteConfigRecord) -> None:
    data = cfg.model_dump(mode="json")
    with _lock:
        _write_with_cloud_sync(CONFIG_FILE, _REMOTE_CONFIG_KEY, data)
