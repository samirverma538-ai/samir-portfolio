import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import BASE_DIR, PROFILE_DIR, UPLOAD_DIR, SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET
from routers import chat, config, documents
from store import load_config, load_documents

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


@app.get("/uploads/{filename}")
async def get_upload(filename: str):
    local_path = UPLOAD_DIR / filename
    if local_path.exists():
        return FileResponse(local_path)
    if SUPABASE_URL and SUPABASE_KEY:
        return RedirectResponse(
            f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"
        )
    raise HTTPException(status_code=404, detail="File not found")


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/js", StaticFiles(directory=str(BASE_DIR / "frontend" / "js")), name="js")
app.mount("/css", StaticFiles(directory=str(BASE_DIR / "frontend" / "css")), name="css")


@app.on_event("startup")
def startup():
    # Seed default profile picture if missing
    default_profile = PROFILE_DIR / "default.jpg"
    beach = BASE_DIR / "beach.jpeg"
    if not default_profile.exists() and beach.exists():
        shutil.copy(beach, default_profile)

    # Restore data from Supabase cloud backup (if local files were wiped)
    load_config()
    load_documents()


@app.get("/", response_class=HTMLResponse)
async def root():
    return Path(BASE_DIR / "frontend" / "index.html").read_text()


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return Path(BASE_DIR / "frontend" / "admin.html").read_text()
