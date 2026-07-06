from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class DocumentRecord(BaseModel):
    """Persisted document metadata (stored as JSON)."""
    id: int = 0
    filename: str
    original_filename: str
    file_type: str
    description: str = ""
    extracted_text: str = ""
    group_id: Optional[str] = None
    group_order: int = 0
    thumbnail_path: Optional[str] = None
    upload_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SiteConfigRecord(BaseModel):
    """Persisted site configuration (stored as JSON)."""
    header: str = "Architecture Document Showcase"
    subheader: str = "Professional portfolio & interactive document repository"
    owner_name: str = "Samir Kumar Verma"
    role: str = "Solutions Architect"
    experience: str = (
        "Experienced solutions architect specializing in cloud-native systems, "
        "enterprise integration, and scalable application design."
    )
    contact_email: str = ""
    contact_phone: str = ""
    contact_linkedin: str = ""
    profile_picture: str = "/static/profile/default.jpg"
