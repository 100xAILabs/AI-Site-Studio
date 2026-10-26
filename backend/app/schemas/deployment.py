"""
Pydantic schemas for Deployment, Version, Domain, and Log entities.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pathlib import PurePosixPath, PureWindowsPath
from pydantic import BaseModel, Field, field_validator, ConfigDict


class DeploymentBase(BaseModel):
    project_name: str = Field(min_length=1, max_length=100)
    provider: Literal["local", "vercel"] = "local"
    template_id: Optional[uuid.UUID] = None
    branch: str = "main"
    build_command: str = "npm run build"
    output_dir: str = "dist"
    env_vars: Optional[Dict[str, str]] = None
    accepted_hosting_terms: bool = False

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank.")
        return value

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, value: str) -> str:
        value = value.strip()
        posix_path = PurePosixPath(value)
        windows_path = PureWindowsPath(value)
        if not value or posix_path.is_absolute() or windows_path.is_absolute() or ".." in posix_path.parts or ".." in windows_path.parts:
            raise ValueError("Output directory must be a safe relative path inside the project.")
        return value


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
    hosting_subscription_status: str = "not_subscribed"
    hosting_subscription_cancel_at_period_end: bool = False
    hosting_subscription_period_end: Optional[datetime] = None
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
    level: str = Field(default="INFO", max_length=16)  # INFO, WARN, ERROR, SUCCESS
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=1000)
    url: Optional[str] = Field(default=None, max_length=2048)
    pathname: Optional[str] = Field(default=None, max_length=512)
    timestamp: Optional[str] = Field(default=None, max_length=64)
    meta: Optional[Dict[str, Any]] = Field(default=None, max_length=20)

