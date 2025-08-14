from pydantic import BaseModel, Field, validator
from datetime import time, date
from typing import Optional, List
from app.models.work_schedule import DayOfWeek, ExceptionType


class TimeSlotBase(BaseModel):
    start_time: time
    end_time: time
    
    @validator('end_time')
    def end_time_after_start_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be after start_time')
        return v


class WorkScheduleBase(TimeSlotBase):
    day_of_week: DayOfWeek
    slot_duration_minutes: int = Field(30, ge=15, le=120)  # Entre 15 minutos y 2 horas
    is_active: bool = True
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    
    @validator('break_end')
    def validate_break_times(cls, v, values):
        if v is not None and values.get('break_start') is None:
            raise ValueError('break_end requires break_start to be set')
        if v is not None and values.get('break_start') is not None:
            if v <= values['break_start']:
                raise ValueError('break_end must be after break_start')
        return v


class WorkScheduleCreate(WorkScheduleBase):
    provider_id: int


class WorkScheduleUpdate(BaseModel):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    slot_duration_minutes: Optional[int] = Field(None, ge=15, le=120)
    is_active: Optional[bool] = None
    break_start: Optional[time] = None
    break_end: Optional[time] = None


class WorkSchedule(WorkScheduleBase):
    id: int
    provider_id: int
    
    class Config:
        from_attributes = True


class ScheduleExceptionBase(BaseModel):
    date: date
    exception_type: ExceptionType
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    slot_duration_minutes: Optional[int] = Field(None, ge=15, le=120)
    reason: Optional[str] = None
    
    @validator('start_time')
    def validate_custom_hours_times(cls, v, values):
        if values.get('exception_type') == ExceptionType.CUSTOM_HOURS and v is None:
            raise ValueError('start_time is required for custom_hours exceptions')
        return v
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        if values.get('exception_type') == ExceptionType.CUSTOM_HOURS:
            if v is None:
                raise ValueError('end_time is required for custom_hours exceptions')
            if values.get('start_time') and v <= values['start_time']:
                raise ValueError('end_time must be after start_time')
        return v


class ScheduleExceptionCreate(ScheduleExceptionBase):
    provider_id: int


class ScheduleExceptionUpdate(BaseModel):
    exception_type: Optional[ExceptionType] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    slot_duration_minutes: Optional[int] = Field(None, ge=15, le=120)
    reason: Optional[str] = None


class ScheduleException(ScheduleExceptionBase):
    id: int
    provider_id: int
    
    class Config:
        from_attributes = True


class ProviderSettingsBase(BaseModel):
    default_slot_duration: int = Field(30, ge=15, le=120)
    advance_booking_days: int = Field(30, ge=1, le=365)
    same_day_booking: bool = True
    timezone: str = "UTC"


class ProviderSettingsCreate(ProviderSettingsBase):
    provider_id: int


class ProviderSettingsUpdate(BaseModel):
    default_slot_duration: Optional[int] = Field(None, ge=15, le=120)
    advance_booking_days: Optional[int] = Field(None, ge=1, le=365)
    same_day_booking: Optional[bool] = None
    timezone: Optional[str] = None


class ProviderSettings(ProviderSettingsBase):
    id: int
    provider_id: int
    
    class Config:
        from_attributes = True


class WeeklyScheduleResponse(BaseModel):
    """Respuesta completa del horario semanal de un proveedor"""
    provider_id: int
    schedules: List[WorkSchedule]
    settings: ProviderSettings
    
    class Config:
        from_attributes = True


class ProviderAvailabilityResponse(BaseModel):
    """Disponibilidad de un proveedor para una fecha específica"""
    provider_id: int
    date: date
    is_available: bool
    reason: Optional[str] = None  # Si no está disponible, el motivo
    available_slots: List[dict] = []  # Lista de horarios disponibles
    
    class Config:
        from_attributes = True