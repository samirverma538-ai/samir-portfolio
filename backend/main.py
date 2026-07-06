import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import BASE_DIR, PROFILE_DIR, UPLOAD_DIR
from database import Base, SessionLocal, engine
from models import Document, SiteConfig
from routers import chat, config, documents

app = FastAPI(title="Architecture Document Showcase", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(config.router)
app.include_router(chat.router)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/js", StaticFiles(directory=str(BASE_DIR / "frontend" / "js")), name="js")
app.mount("/css", StaticFiles(directory=str(BASE_DIR / "frontend" / "css")), name="css")


def _migrate_documents():
    import uuid

    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "documents" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("documents")}
    with engine.begin() as conn:
        if "group_id" not in columns:
            conn.execute(text("ALTER TABLE documents ADD COLUMN group_id VARCHAR(36)"))
        if "group_order" not in columns:
            conn.execute(text("ALTER TABLE documents ADD COLUMN group_order INTEGER DEFAULT 0"))
        if "thumbnail_path" not in columns:
            conn.execute(text("ALTER TABLE documents ADD COLUMN thumbnail_path VARCHAR(500)"))

    db = SessionLocal()
    try:
        from services.thumbnail_generator import create_thumbnail

        missing = db.query(Document).filter(Document.group_id.is_(None)).all()
        for doc in missing:
            doc.group_id = uuid.uuid4().hex
            doc.group_order = 0
        if missing:
            db.commit()

        primary_docs = db.query(Document).filter(Document.group_order == 0).all()
        updated = False
        for doc in primary_docs:
            if doc.thumbnail_path:
                continue
            source = UPLOAD_DIR / doc.filename
            if not source.exists():
                continue
            doc.thumbnail_path = create_thumbnail(source, doc.file_type, doc.extracted_text or "")
            updated = True
        if updated:
            db.commit()
    finally:
        db.close()


def _seed_defaults():
    db = SessionLocal()
    try:
        if not db.query(SiteConfig).first():
            db.add(SiteConfig(id=1))
            db.commit()

        default_profile = PROFILE_DIR / "default.jpg"
        beach = BASE_DIR / "beach.jpeg"
        if not default_profile.exists() and beach.exists():
            shutil.copy(beach, default_profile)
    finally:
        db.close()


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    _migrate_documents()
    _seed_defaults()


@app.get("/", response_class=HTMLResponse)
async def root():
    return Path(BASE_DIR / "frontend" / "index.html").read_text()


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return Path(BASE_DIR / "frontend" / "admin.html").read_text()

