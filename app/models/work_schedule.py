from sqlalchemy import Column, Integer, String, Time, Date, Boolean, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import time
import enum
from .user import Base


class DayOfWeek(int, enum.Enum):
    SUNDAY = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6


class ExceptionType(str, enum.Enum):
    DAY_OFF = "day_off"           # Día libre completo
    VACATION = "vacation"         # Vacaciones  
    CUSTOM_HOURS = "custom_hours" # Horario personalizado para el día
    HOLIDAY = "holiday"           # Día festivo


class WorkSchedule(Base):
    """
    Horarios semanales base de cada proveedor
    Define la disponibilidad regular por día de la semana
    """
    __tablename__ = "work_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Enum(DayOfWeek), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_active = Column(Boolean, default=True)
    slot_duration_minutes = Column(Integer, nullable=False, default=30)
    
    # Horario de descanso/almuerzo (opcional)
    break_start = Column(Time, nullable=True)
    break_end = Column(Time, nullable=True)
    
    # Relación con el proveedor
    provider = relationship("User", back_populates="work_schedules")
    
    def __repr__(self):
        return f"<WorkSchedule {self.day_of_week.name}: {self.start_time}-{self.end_time}>"


class ScheduleException(Base):
    """
    Excepciones al horario regular: vacaciones, días libres, horarios especiales
    """
    __tablename__ = "schedule_exceptions"
    
    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    exception_type = Column(Enum(ExceptionType), nullable=False)
    
    # Para custom_hours: horario especial del día
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    slot_duration_minutes = Column(Integer, nullable=True)
    
    # Motivo/descripción
    reason = Column(Text, nullable=True)
    
    # Relación con el proveedor
    provider = relationship("User", back_populates="schedule_exceptions")
    
    def __repr__(self):
        return f"<ScheduleException {self.date}: {self.exception_type.value}>"


class ProviderSettings(Base):
    """
    Configuración global de cada proveedor
    """
    __tablename__ = "provider_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Configuración de slots
    default_slot_duration = Column(Integer, nullable=False, default=30)
    
    # Configuración de agendamiento
    advance_booking_days = Column(Integer, nullable=False, default=30)  # Máximo 30 días adelante
    same_day_booking = Column(Boolean, default=True)  # ¿Permite agendar el mismo día?
    
    # Configuración regional
    timezone = Column(String, nullable=False, default="UTC")
    
    # Relación con el proveedor
    provider = relationship("User", back_populates="provider_settings", uselist=False)
    
    def __repr__(self):
        return f"<ProviderSettings provider_id={self.provider_id}>"