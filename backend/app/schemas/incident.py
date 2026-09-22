"""
Pydantic schemas for Site Failure Incidents, AI Auto-Healing, and Admin Code Editor.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    issue_type: str = "broken_script"
    title: str = Field(..., max_length=255)
    description: str
    error_logs: Optional[str] = None
    page_url: Optional[str] = None
    severity: str = "high"
    reporter_email: Optional[str] = None
    reporter_name: Optional[str] = None
    auto_heal_with_ai: bool = True  # If true, immediately triggers the AI Site Doctor


class IncidentStatusUpdate(BaseModel):
    status: str  # open, investigating, auto_fixing, resolved, dismissed
    resolution_notes: Optional[str] = None


class IncidentResponse(BaseModel):
    id: uuid.UUID
    deployment_id: uuid.UUID
    site_id: str
    project_name: Optional[str] = None
    live_url: Optional[str] = None
    subdomain: Optional[str] = None
    reporter_email: Optional[str] = None
    reporter_name: Optional[str] = None
    issue_type: str
    title: str
    description: str
    error_logs: Optional[str] = None
    page_url: Optional[str] = None
    severity: str
    status: str
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    ai_diagnosis: Optional[str] = None
    ai_patch_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AutoFixRequest(BaseModel):
    incident_id: Optional[uuid.UUID] = None
    issue_description: Optional[str] = None
    error_logs: Optional[str] = None
    target_file: Optional[str] = None


class FilePatch(BaseModel):
    path: str
    content: str


class AutoFixResponse(BaseModel):
    success: bool
    incident_id: Optional[uuid.UUID] = None
    site_id: str
    live_url: Optional[str] = None
    diagnosis: str
    root_cause: Optional[str] = None
    patch_summary: str
    patched_files: List[str]
    health_status: str
    error_message: Optional[str] = None


class FileItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int
    ext: str


class FileContentResponse(BaseModel):
    path: str
    content: str
    size: int
    ext: str


class FileSaveRequest(BaseModel):
    path: str
    content: str
    incident_id: Optional[uuid.UUID] = None
