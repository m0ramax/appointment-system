from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from app.models.appointment import AppointmentStatus


class AppointmentBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    date_time: datetime
    duration_minutes: int = Field(60, ge=15, le=480)  # Entre 15 minutos y 8 horas


class AppointmentCreate(AppointmentBase):
    provider_id: int


class AppointmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    date_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=15, le=480)
    status: Optional[AppointmentStatus] = None


class AppointmentInDB(AppointmentBase):
    id: int
    status: AppointmentStatus
    client_id: int
    provider_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Appointment(AppointmentInDB):
    pass
