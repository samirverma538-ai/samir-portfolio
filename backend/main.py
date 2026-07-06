import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from firebase_functions import https_fn
from a2wsgi import ASGIMiddleware

from config import BASE_DIR, PROFILE_DIR, UPLOAD_DIR
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

# Note: In production (Firebase), these will be served via Firebase Hosting
# But keeping them for local development convenience.
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/js", StaticFiles(directory=str(BASE_DIR / "frontend" / "js")), name="js")
app.mount("/css", StaticFiles(directory=str(BASE_DIR / "frontend" / "css")), name="css")

@app.on_event("startup")
def startup():
    pass

@app.get("/", response_class=HTMLResponse)
async def root():
    return Path(BASE_DIR / "frontend" / "index.html").read_text()

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return Path(BASE_DIR / "frontend" / "admin.html").read_text()

# Export as a Firebase Function
wsgi_app = ASGIMiddleware(app)

@https_fn.on_request(timeout_sec=300, memory=512)
def api_backend(req: https_fn.Request) -> https_fn.Response:
    # Under the hood, firebase-functions python uses Werkzeug Request/Response objects
    # a2wsgi can handle standard WSGI environments.
    # However, since firebase-functions passes a custom request object that inherits from Request, 
    # we need to extract the environ.
    
    # Alternatively, we can just use the provided request dispatcher.
    # We will use Flask to bridge it or run it using WSGI wrapper.
    import io
    environ = req.environ
    
    def start_response(status, response_headers, exc_info=None):
        req._status = status
        req._headers = response_headers
        return req._response_body.write

    req._response_body = io.BytesIO()
    
    result = wsgi_app(environ, start_response)
    
    # Exhaust the iterator if it returns one
    for data in result:
        req._response_body.write(data)
        
    import werkzeug
    # Parse status
    status_code = int(req._status.split(' ')[0])
    
    return https_fn.Response(
        response=req._response_body.getvalue(),
        status=status_code,
        headers=dict(req._headers)
    )
