from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentFileResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    group_order: int
    thumbnail_path: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentGroupResponse(BaseModel):
    id: int
    group_id: str
    title: str = ""
    description: str
    upload_date: datetime
    files: list[DocumentFileResponse]

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    title: str = ""
    description: str
    upload_date: datetime

    class Config:
        from_attributes = True


class DocumentUpdate(BaseModel):
    title: Optional[str] = ""
    description: str
    admin_password: str


class DocumentDelete(BaseModel):
    admin_password: str


class SiteConfigResponse(BaseModel):
    header: str
    subheader: str
    owner_name: str
    role: str
    experience: str
    contact_email: str
    contact_phone: str
    contact_linkedin: str
    profile_picture: str

    class Config:
        from_attributes = True


class SiteConfigUpdate(BaseModel):
    header: Optional[str] = None
    subheader: Optional[str] = None
    owner_name: Optional[str] = None
    role: Optional[str] = None
    experience: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_linkedin: Optional[str] = None
    admin_password: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str


class AdminAuth(BaseModel):
    admin_password: str

