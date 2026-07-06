from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    description = Column(Text, default="")
    extracted_text = Column(Text, default="")
    group_id = Column(String(36), nullable=True, index=True)
    group_order = Column(Integer, default=0)
    thumbnail_path = Column(String(500), nullable=True)
    upload_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SiteConfig(Base):
    __tablename__ = "site_config"

    id = Column(Integer, primary_key=True, default=1)
    header = Column(String(255), default="Architecture Document Showcase")
    subheader = Column(String(500), default="Professional portfolio & interactive document repository")
    owner_name = Column(String(255), default="Samir Kumar Verma")
    role = Column(String(255), default="Solutions Architect")
    experience = Column(Text, default="Experienced solutions architect specializing in cloud-native systems, enterprise integration, and scalable application design.")
    contact_email = Column(String(255), default="")
    contact_phone = Column(String(50), default="")
    contact_linkedin = Column(String(500), default="")
    profile_picture = Column(String(500), default="/static/profile/default.jpg")

