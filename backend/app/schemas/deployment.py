"""
Pydantic schemas for Deployment, Version, Domain, and Log entities.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DeploymentBase(BaseModel):
    project_name: str
    provider: str = "local"  # local, vercel, netlify, docker
    template_id: Optional[uuid.UUID] = None
    branch: str = "main"
    build_command: str = "npm run build"
    output_dir: str = "dist"
    env_vars: Optional[Dict[str, str]] = None


class DeploymentCreate(DeploymentBase):
    pass


class DeploymentLogResponse(BaseModel):
    id: uuid.UUID
    deployment_id: uuid.UUID
    level: str
    message: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class DeploymentVersionResponse(BaseModel):
    id: uuid.UUID
    deployment_id: uuid.UUID
    version: str
    build_reference: str
    status: str
    commit_message: str
    build_logs: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DomainCreate(BaseModel):
    domain: str


class DomainResponse(BaseModel):
    id: uuid.UUID
    deployment_id: uuid.UUID
    user_id: uuid.UUID
    domain: str
    domain_type: str
    verification_status: str
    ssl_status: str
    verification_token: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeploymentResponse(DeploymentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    site_id: Optional[str] = None
    status: str  # created, queued, building, live, failed, suspended, stopped
    current_version: str = "v1.0"
    deployment_type: str = "static"
    health_status: str = "healthy"
    subdomain: str
    live_url: Optional[str] = None
    custom_domain: Optional[str] = None
    logs: Optional[str] = None
    env_vars: Optional[Dict[str, Any]] = None
    is_suspended: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeploymentDetailResponse(DeploymentResponse):
    versions: List[DeploymentVersionResponse] = []
    domains: List[DomainResponse] = []
    recent_logs: List[DeploymentLogResponse] = []


class RollbackRequest(BaseModel):
    target_version: str


class EnvironmentVariableUpdate(BaseModel):
    env_vars: Dict[str, str]


class ClientTelemetryPayload(BaseModel):
    level: str = "INFO"  # INFO, WARN, ERROR, SUCCESS
    message: str
    url: Optional[str] = None
    pathname: Optional[str] = None
    timestamp: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

