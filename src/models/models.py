# NOTE (v2): despite the Google/ADP-flavoured names, these are shapes
# for rows in the local SQLite database. v1 never called Google or ADP;
# the names are kept for compatibility, not as integration claims.
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class GoogleAdminUser(BaseModel):
    """
    Represents a user from the Google Admin SDK.
    """

    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., description="User full name")
    department: Optional[str] = Field("Not Assigned")
    title: Optional[str] = Field("Not Assigned")
    last_login_time: datetime = Field(..., description="Timestamp of last activity")
    is_suspended: bool = Field(False, description="Account status")
    role: str = Field("Standard", description="Access level: Admin, Supervisor, or Standard")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "test.user@example.com",
                "full_name": "Test User",
                "department": "Engineering",
                "title": "Software Engineer",
                "last_login_time": "2026-03-15T10:00:00Z",
                "is_suspended": False,
            }
        }
    }


class GoogleDriveActivity(BaseModel):
    """
    Represents a file view event from Google Drive.
    """

    document_id: str = Field(..., description="Unique ID of the document")
    document_name: str = Field(..., description="Name of document")
    view_timestamp: datetime = Field(..., description="Time of view activity")
    viewer_email: EmailStr = Field(..., description="Email of documentation viewer")

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "1aBcDeFgHiJkLmNoPqRsTuVwXyZ",
                "document_name": "Q1_Project_Plan.gdoc",
                "view_timestamp": "2026-03-15T11:30:00Z",
                "viewer_email": "test.user@example.com",
            }
        }
    }


class ADPHRWorker(BaseModel):
    """
    Represents a worker profile from an ADP/HR system.
    """

    worker_id: str = Field(..., description="Unique ID for internal HR use")
    primary_email: EmailStr = Field(..., description="Primary contact email")
    clock_in_status: bool = Field(..., description="True if currently clocked in")
    current_pay_cycle_hours: float = Field(0.0, ge=0.0, description="Total hours for current cycle")

    model_config = {
        "json_schema_extra": {
            "example": {
                "worker_id": "WID-12345",
                "primary_email": "test.user@example.com",
                "clock_in_status": True,
                "current_pay_cycle_hours": 24.5,
            }
        }
    }
