import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.database import DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    status: DocumentStatus
    char_count: int
    confidence: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    has_txt: bool = False
    has_pdf: bool = False


class DocumentDetail(DocumentOut):
    extracted_text: Optional[str] = None


class StatsOut(BaseModel):
    total_documents: int
    total_done: int
    total_failed: int
    total_characters_extracted: int
    average_confidence: Optional[float] = None
