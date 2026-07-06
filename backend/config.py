import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "documents")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "sameerverma14337")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# RAG: gemini-2.5-flash supports ~1M tokens; keep a safe character budget.
RAG_MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "600000"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "2000"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "300"))
RAG_MIN_QUERY_TERM_LEN = 3

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png", ".txt"}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

# Data persistence folders
RENDER = os.getenv("RENDER", "false").lower() == "true"
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"

PROFILE_DIR = BASE_DIR / "static" / "profile"
THUMBNAIL_DIR = BASE_DIR / "static" / "thumbnails"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
