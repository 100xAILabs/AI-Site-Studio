"""
Pydantic schemas for Deployment entity.
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DeploymentBase(BaseModel):
    project_name: str
    provider: str  # vercel, netlify, github_pages
    template_id: Optional[uuid.UUID] = None
    branch: str = "main"
    build_command: str = "npm run build"
    output_dir: str = "dist"


class DeploymentCreate(DeploymentBase):
    pass


class DeploymentResponse(DeploymentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str  # building, success, failed
    subdomain: str
    live_url: Optional[str] = None
    custom_domain: Optional[str] = None
    logs: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
