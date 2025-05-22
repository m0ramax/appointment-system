from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .user import Base


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    date_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=60)
    status = Column(
        Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.PENDING
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign keys
    client_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relaciones bidireccionales usando strings
    client = relationship(
        "User", foreign_keys=[client_id], back_populates="client_appointments"
    )
    provider = relationship(
        "User", foreign_keys=[provider_id], back_populates="provider_appointments"
    )

    def __repr__(self):
        return f"<Appointment {self.title} at {self.date_time}>"
