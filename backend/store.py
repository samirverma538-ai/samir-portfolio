"""
store.py — flat-file JSON persistence layer.

Two JSON files are maintained:
  DATA_DIR/documents.json   — list of document records
  DATA_DIR/config.json      — single site-config record

All reads/writes are protected by a threading.Lock so the app
is safe when uvicorn runs with multiple workers or --reload.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR
from models import DocumentRecord, SiteConfigRecord

_lock = threading.Lock()

DOCUMENTS_FILE = DATA_DIR / "documents.json"
CONFIG_FILE = DATA_DIR / "config.json"


# ── helpers ──────────────────────────────────────────────────────────────────

def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── documents ─────────────────────────────────────────────────────────────────

def load_documents() -> list[DocumentRecord]:
    with _lock:
        raw = _read_json(DOCUMENTS_FILE, [])
    return [DocumentRecord(**d) for d in raw]


def save_documents(docs: list[DocumentRecord]) -> None:
    with _lock:
        _write_json(DOCUMENTS_FILE, [d.model_dump(mode="json") for d in docs])


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
        raw = _read_json(DOCUMENTS_FILE, [])
        # auto-increment id
        existing_ids = [d.get("id", 0) for d in raw]
        doc.id = max(existing_ids, default=0) + 1
        raw.append(doc.model_dump(mode="json"))
        _write_json(DOCUMENTS_FILE, raw)
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


# ── site config ───────────────────────────────────────────────────────────────

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
        raw = _read_json(CONFIG_FILE, _DEFAULT_CONFIG)
    merged = {**_DEFAULT_CONFIG, **raw}
    return SiteConfigRecord(**merged)


def save_config(cfg: SiteConfigRecord) -> None:
    with _lock:
        _write_json(CONFIG_FILE, cfg.model_dump(mode="json"))
